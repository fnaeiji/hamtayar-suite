"""Transactional SQLite generation catalog for single-host local development.

A shared Postgres/catalog backend is required for multi-instance production.
"""

import asyncio
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from packages.contracts.access import AccessMetadata
from packages.contracts.common import SourceVersion


class LocalSqliteGenerationCatalog:
    def __init__(self, *, database_path: Path) -> None:
        self.path = Path(database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS validated_generations (
                    tenant TEXT NOT NULL, space TEXT NOT NULL,
                    source TEXT NOT NULL, version TEXT NOT NULL,
                    generation TEXT NOT NULL, indexed_count INTEGER NOT NULL CHECK(indexed_count > 0),
                    PRIMARY KEY (tenant,space,source,version,generation)
                );
                CREATE TABLE IF NOT EXISTS active_generations (
                    tenant TEXT NOT NULL, space TEXT NOT NULL,
                    source TEXT NOT NULL, generation TEXT NOT NULL,
                    version TEXT NOT NULL,
                    PRIMARY KEY (tenant,space,source)
                );
            """)

    @contextmanager
    def _connection(self):
        connection = sqlite3.connect(str(self.path), timeout=10, isolation_level=None)
        try:
            connection.execute("PRAGMA busy_timeout=10000")
            yield connection
        finally:
            connection.close()

    @staticmethod
    def _identity(source: SourceVersion, access: AccessMetadata):
        return (
            access.tenant_id,
            source.source.knowledge_space_id,
            source.source.source_id,
            source.version,
        )

    def _mark(
        self,
        source: SourceVersion,
        access: AccessMetadata,
        generation_id: str,
        indexed_count: int,
    ):
        if indexed_count < 1 or not generation_id:
            raise ValueError("Only nonempty verified generations are publishable")
        identity = self._identity(source, access)
        with self._connection() as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                existing = db.execute(
                    """SELECT indexed_count FROM validated_generations
                    WHERE tenant=? AND space=? AND source=? AND version=? AND generation=?""",
                    (*identity, generation_id),
                ).fetchone()
                if existing is not None and existing[0] != indexed_count:
                    raise ValueError("Generation count mismatch")
                db.execute(
                    """INSERT OR IGNORE INTO validated_generations
                    (tenant,space,source,version,generation,indexed_count)
                    VALUES (?,?,?,?,?,?)""",
                    (*identity, generation_id, indexed_count),
                )
                db.commit()
            except BaseException:
                db.rollback()
                raise

    async def mark_validated(
        self,
        *,
        source: SourceVersion,
        access: AccessMetadata,
        generation_id: str,
        indexed_count: int,
    ) -> None:
        await asyncio.to_thread(
            self._mark, source, access, generation_id, indexed_count
        )

    def _publish(
        self, source: SourceVersion, access: AccessMetadata, generation_id: str
    ) -> bool:
        tenant, space, sid, version = self._identity(source, access)
        with self._connection() as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                validated = db.execute(
                    """SELECT indexed_count FROM validated_generations
                    WHERE tenant=? AND space=? AND source=? AND version=? AND generation=?""",
                    (tenant, space, sid, version, generation_id),
                ).fetchone()
                if not validated:
                    db.rollback()
                    return False
                db.execute(
                    """INSERT INTO active_generations
                    (tenant,space,source,generation,version)
                    VALUES (?,?,?,?,?)
                    ON CONFLICT(tenant,space,source) DO UPDATE SET
                    generation=excluded.generation, version=excluded.version""",
                    (tenant, space, sid, generation_id, version),
                )
                db.commit()
                return True
            except BaseException:
                db.rollback()
                raise

    async def publish(
        self,
        *,
        source: SourceVersion,
        access: AccessMetadata,
        generation_id: str,
    ) -> bool:
        return await asyncio.to_thread(self._publish, source, access, generation_id)

    def _active(self, source: SourceVersion, access: AccessMetadata) -> str | None:
        tenant, space, sid, _ = self._identity(source, access)
        with self._connection() as db:
            result = db.execute(
                """SELECT generation FROM active_generations
                WHERE tenant=? AND space=? AND source=?""",
                (tenant, space, sid),
            ).fetchone()
            return result[0] if result else None

    async def active_generation(
        self,
        *,
        source: SourceVersion,
        access: AccessMetadata,
    ) -> str | None:
        return await asyncio.to_thread(self._active, source, access)

    async def active_generations(self, *, scope):
        """Resolve only the active generations in the caller's trusted scope."""
        from packages.contracts.common import SourceRef, SourceVersion
        from packages.contracts.publication import ActiveGeneration

        def read():
            with self._connection() as db:
                rows = db.execute(
                    "SELECT space,source,version,generation FROM active_generations WHERE tenant=?",
                    (scope.tenant_id,),
                ).fetchall()
            return [
                ActiveGeneration(
                    source=SourceVersion(
                        source=SourceRef(
                            source_id=sid,
                            knowledge_space_id=space,
                            source_type="document",
                        ),
                        version=version,
                    ),
                    generation_id=generation,
                )
                for space, sid, version, generation in rows
                if scope.source_ids is None or sid in scope.source_ids
            ]

        return await asyncio.to_thread(read)
