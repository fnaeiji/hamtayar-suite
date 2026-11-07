import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

PACKAGES = {
    p.name
    for p in (ROOT / "packages").iterdir()
    if p.is_dir() and p.name != "__pycache__"
}
ALLOWED = {
    "contracts": set(),
    "storage": {"contracts"},
    "integrations": {"contracts"},
    "documents": {"contracts"},
    "code_intelligence": {"contracts"},
    "access": {"contracts"},
    "knowledge": {"contracts", "storage"},
    "retrieval": {"contracts", "storage", "access", "knowledge"},
    "answering": {"contracts"},
    "ingestion": {"contracts", "documents", "knowledge"},
}


def imports(path: Path):
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module:
            yield node.module
        if isinstance(node, ast.Import):
            for name in node.names:
                yield name.name


def test_package_dependencies_follow_map():
    assert PACKAGES >= set(ALLOWED)
    for module, allowed in ALLOWED.items():
        for file in (ROOT / "packages" / module).rglob("*.py"):
            for imported in imports(file):
                root = imported.split(".")[0]
                if root == "apps":
                    raise AssertionError(f"{file} imports app {imported}")
                if root == "packages":
                    target = imported.split(".")[1]
                    assert target in allowed or target == module, (
                        f"{file} imports {target}"
                    )


# ---- S-02: the Qdrant SDK stays in one production module, callers use service.py only
PRODUCTION_TREES = (
    "packages",
    "apps",
)  # infra/ and test/ are exempt (dev/test support)
ADAPTER = "packages/storage/qdrant/adapter.py"


def production_files():
    for base in PRODUCTION_TREES:
        root = ROOT / base
        if root.is_dir():
            yield from root.rglob("*.py")


def relative(file: Path) -> str:
    return file.relative_to(ROOT).as_posix()


def test_qdrant_sdk_is_imported_by_the_adapter_and_nothing_else_in_production_code():
    offenders = []
    for file in production_files():
        if relative(file) != ADAPTER and any(
            name == "qdrant_client" or name.startswith("qdrant_client.")
            for name in imports(file)
        ):
            offenders.append(relative(file))
    assert offenders == [], f"qdrant_client imported outside {ADAPTER}: {offenders}"


def test_the_adapter_is_the_one_place_that_owns_the_sdk():
    importers = [
        relative(file)
        for file in production_files()
        if any(
            name == "qdrant_client" or name.startswith("qdrant_client.")
            for name in imports(file)
        )
    ]
    assert importers in ([], [ADAPTER]), f"unexpected SDK importers: {importers}"


def test_storage_internals_are_not_imported_from_outside_the_storage_package():
    public = {"packages.storage", "packages.storage.service"}
    offenders = []
    for file in production_files():
        if relative(file).startswith("packages/storage/"):
            continue
        for imported in imports(file):
            if imported.startswith("packages.storage") and imported not in public:
                offenders.append(f"{relative(file)} -> {imported}")
    assert offenders == [], (
        f"callers must use packages.storage.service only: {offenders}"
    )


def test_storage_does_not_depend_on_retrieval_contracts():
    offenders = []
    for file in (ROOT / "packages" / "storage").rglob("*.py"):
        for imported in imports(file):
            if imported.startswith(
                ("packages.retrieval", "packages.contracts.retrieval")
            ):
                offenders.append(f"{relative(file)} -> {imported}")
    assert offenders == [], f"storage must not depend on retrieval: {offenders}"


def test_retrieval_does_not_import_qdrant_or_storage_internals():
    offenders = []
    for file in (ROOT / "packages" / "retrieval").rglob("*.py"):
        for imported in imports(file):
            if imported == "qdrant_client" or imported.startswith("qdrant_client."):
                offenders.append(f"{relative(file)} -> {imported}")
            if (
                imported.startswith("packages.storage.")
                and imported != "packages.storage.service"
            ):
                offenders.append(f"{relative(file)} -> {imported}")
    assert offenders == [], (
        f"retrieval crossed the approved storage boundary: {offenders}"
    )


def test_runtime_search_does_not_import_index_provisioning():
    offenders = []
    for file in production_files():
        for imported in imports(file):
            if imported.startswith("infra.qdrant.provision_search_indexes"):
                offenders.append(f"{relative(file)} -> {imported}")
    assert offenders == [], f"runtime imports index provisioning: {offenders}"
