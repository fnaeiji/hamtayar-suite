import { MetadataFields } from '../../components/metadata/MetadataFields';
import { TestDetailsPanel } from '../../components/operations/TestDetailsPanel';
import { useOperation } from '../../services/operations/operationService';
import type { MetadataFieldDefinition } from '../../types/metadata';
import type { DocumentDraft, DocumentResult } from './documentTypes';
export function DocumentFileCard({
  draft,
  definitions,
  onChange,
  disabled,
}: {
  draft: DocumentDraft;
  definitions: MetadataFieldDefinition[];
  onChange: (patch: Partial<DocumentDraft>) => void;
  disabled: boolean;
}) {
  const op = useOperation<DocumentResult>(draft.id);
  return (
    <article className="workspace-card document-card" aria-label={draft.file.name}>
      <h2 dir="ltr">{draft.file.name}</h2>
      <p>
        {draft.file.size} بایت · <bdi>{draft.file.type || 'نوع نامشخص'}</bdi>
      </p>
      <fieldset disabled={disabled}>
        <legend>مشخصات سند</legend>
        <div className="form-grid">
          {(
            [
              ['sourceId', 'شناسه منبع'],
              ['knowledgeSpaceId', 'فضای دانشی'],
              ['version', 'نسخه'],
              ['processingProfile', 'پروفایل پردازش'],
            ] as const
          ).map(([key, label]) => (
            <label key={key}>
              {label}
              <input
                dir="ltr"
                value={draft[key]}
                onChange={(e) =>
                  onChange({
                    [key]: e.target.value,
                  })
                }
              />
            </label>
          ))}
        </div>
        <MetadataFields
          definitions={definitions}
          values={draft.customMetadata}
          group="document"
          onChange={(key, value) =>
            onChange({
              customMetadata: { ...draft.customMetadata, [key]: value },
            })
          }
        />
      </fieldset>
      {op && (
        <div role="status">
          <bdi>{op.status}</bdi>
          {op.result && (
            <>
              <p>{op.result.label}</p>
              <p>{op.result.message}</p>
              {op.result.chunksIndexed !== undefined && (
                <p>
                  تعداد چانک:{' '}
                  {op.result.chunksIndexed === null
                    ? 'گزارش نشده'
                    : op.result.chunksIndexed}
                </p>
              )}
            </>
          )}
          {op.diagnostic && (
            <p>
              {op.mode === 'demo'
                ? 'نمونه این فایل با خطا روبه‌رو شد.'
                : op.diagnostic.message}
            </p>
          )}
        </div>
      )}
      <TestDetailsPanel operation={op} />
    </article>
  );
}
