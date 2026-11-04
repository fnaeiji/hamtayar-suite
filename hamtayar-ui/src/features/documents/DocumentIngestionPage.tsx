import { useMode } from '../../app/ModeProvider';
import { ModeSelector } from '../../components/common/ModeSelector';
import { MetadataFields } from '../../components/metadata/MetadataFields';
import { useMetadata } from '../../services/metadata/useMetadata';
import {
  metadataConfigService,
  filterActiveMetadataValues,
  validateMetadataValues,
} from '../../services/metadata/metadataConfigService';
import { createWorkspaceStore } from '../../services/operations/workspaceStore';
import { runOperation } from '../../services/operations/operationService';
import {
  hamtayarReadiness,
  ingestDocument,
} from '../../services/api/adapters/hamtayarAdapter';
import {
  documentsService,
  validateDocumentFile,
  validateFixedFields,
} from './documentsService';
import { DocumentFileCard } from './DocumentFileCard';
import type { DocumentDraft } from './documentTypes';
import type { MetadataValues } from '../../types/metadata';
const store = createWorkspaceStore(() => ({
  drafts: [] as DocumentDraft[],
  shared: {} as MetadataValues,
  space: '',
  error: '',
  preview: false,
  reduced: false,
}));
const registeredDrafts = new Set<string>();
store.observe(() => {
  const state = store.get();
  for (const id of registeredDrafts) metadataConfigService.removeDraftValues(id);
  registeredDrafts.clear();
  for (const draft of state.drafts) {
    const owner = `document-store-${draft.id}`;
    registeredDrafts.add(owner);
    metadataConfigService.setDraftValues(owner, draft.customMetadata, (keys) => {
      store.set({
        drafts: store.get().drafts.map((d) =>
          d.id !== draft.id
            ? d
            : {
                ...d,
                customMetadata: Object.fromEntries(
                  Object.entries(d.customMetadata).filter(([key]) => !keys.includes(key)),
                ),
              },
        ),
      });
    });
  }
  metadataConfigService.setDraftValues('document-shared', state.shared, (keys) =>
    store.set({
      shared: Object.fromEntries(
        Object.entries(store.get().shared).filter(([key]) => !keys.includes(key)),
      ),
    }),
  );
});
export function DocumentIngestionPage({ showMode = true }: { showMode?: boolean }) {
  const state = store.use();
  const { mode, canSwitchMode } = useMode();
  const { definitions, warning } = useMetadata();
  const gate = hamtayarReadiness('documents');
  function add(files: File[]) {
    if (!canSwitchMode) return;
    const drafts: DocumentDraft[] = [];
    const errors: string[] = [];
    for (const file of files) {
      const error = validateDocumentFile(file, mode);
      if (error) {
        errors.push(error);
        continue;
      }
      drafts.push({
        id: crypto.randomUUID(),
        file,
        sourceId: crypto.randomUUID(),
        knowledgeSpaceId: state.space,
        version: '1',
        processingProfile: 'default',
        customMetadata: { ...state.shared },
        overrides: [],
      });
    }
    store.set({
      drafts: [...state.drafts, ...drafts],
      error: errors.join(' '),
      preview: false,
    });
  }
  function shared(key: string, value: MetadataValues[string]) {
    store.set({
      shared: { ...state.shared, [key]: value },
      drafts: state.drafts.map((d) =>
        d.overrides.includes(key)
          ? d
          : { ...d, customMetadata: { ...d.customMetadata, [key]: value } },
      ),
    });
  }
  const activeDrafts = state.drafts.map((d) => ({
    ...d,
    customMetadata: filterActiveMetadataValues(definitions, d.customMetadata, 'document'),
  }));
  async function submit() {
    if (!canSwitchMode || !state.drafts.length || (mode === 'api' && !gate.ready)) return;
    const errors = state.drafts
      .flatMap((d) => [
        validateDocumentFile(d.file, mode),
        validateFixedFields(d),
        ...validateMetadataValues(definitions, d.customMetadata, 'document').map(
          (e) => e.message,
        ),
      ])
      .filter(Boolean);
    if (errors.length) {
      store.set({ error: errors.join(' ') });
      return;
    }
    store.set({ error: '' });
    await Promise.all(
      activeDrafts.map((d) =>
        runOperation(
          d.id,
          mode,
          (signal) =>
            mode === 'demo'
              ? documentsService.runDemo(d)
              : ingestDocument(d, state.reduced, signal),
          true,
        ),
      ),
    );
  }
  return (
    <section className="page-content">
      <p className="eyebrow">فضای اسناد</p>
      <h1>ورود اسناد</h1>
      {showMode && <ModeSelector />}
      <p className="notice">
        {mode === 'demo'
          ? 'نمایش محلی؛ فایل‌ها خوانده یا به سرور ارسال نمی‌شوند.'
          : 'آزمون واقعی؛ نتیجه ساختگی جایگزین خطا نمی‌شود.'}
      </p>
      {warning && <p role="alert">{warning}</p>}
      <div
        role="region"
        aria-label="انتخاب یا رها کردن اسناد"
        className="drop-zone"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          add(Array.from(e.dataTransfer.files));
        }}
      >
        <label>
          انتخاب اسناد
          <input
            type="file"
            multiple
            accept=".pdf,.docx,.txt,.md,.markdown"
            disabled={!canSwitchMode}
            onChange={(e) => {
              add(Array.from(e.target.files ?? []));
              e.target.value = '';
            }}
          />
        </label>
        <p>PDF، DOCX، TXT یا Markdown را اینجا رها کنید.</p>
      </div>
      {state.error && <p role="alert">{state.error}</p>}
      {mode === 'api' && !state.error && <p role="alert">{gate.reason}</p>}
      <fieldset disabled={!canSwitchMode}>
        <legend>مقادیر مشترک؛ هر سند قابل ویرایش است</legend>
        <label>
          فضای دانشی مشترک
          <input
            dir="ltr"
            value={state.space}
            onChange={(e) =>
              store.set({
                space: e.target.value,
                drafts: state.drafts.map((d) =>
                  d.overrides.includes('knowledgeSpaceId')
                    ? d
                    : { ...d, knowledgeSpaceId: e.target.value },
                ),
              })
            }
          />
        </label>
        <MetadataFields
          definitions={definitions.map((f) => ({ ...f, labelFa: `${f.labelFa} مشترک` }))}
          values={state.shared}
          group="document"
          onChange={shared}
        />
      </fieldset>
      {state.drafts.length === 0 && <p>هنوز سندی انتخاب نشده است.</p>}
      <div className="document-list">
        {state.drafts.map((d) => (
          <DocumentFileCard
            key={d.id}
            draft={d}
            definitions={definitions}
            disabled={!canSwitchMode}
            onChange={(patch) =>
              store.set({
                drafts: state.drafts.map((item) =>
                  item.id === d.id ? { ...item, ...patch } : item,
                ),
              })
            }
          />
        ))}
      </div>
      {mode === 'api' && (
        <label>
          <input
            type="checkbox"
            checked={state.reduced}
            onChange={(e) => store.set({ reduced: e.target.checked })}
          />
          آزمون کاهش‌یافته بدون ارسال متادیتای سفارشی را تأیید می‌کنم.
        </label>
      )}
      <div className="actions">
        <button
          type="button"
          className="button"
          disabled={
            !canSwitchMode || !state.drafts.length || (mode === 'api' && !gate.ready)
          }
          onClick={() => void submit()}
        >
          {mode === 'demo' ? 'اجرای نمایش' : 'ارسال به سرویس'}
        </button>
        <button
          type="button"
          className="button button--quiet"
          onClick={() => store.set({ preview: !state.preview })}
        >
          پیش‌نمایش درخواست
        </button>
        <button
          type="button"
          className="button button--quiet"
          disabled={!canSwitchMode}
          onClick={() =>
            store.set({ drafts: [], error: '', preview: false, shared: {}, space: '' })
          }
        >
          پاک کردن
        </button>
      </div>
      {state.preview && (
        <section role="region" aria-label="پیش‌نمایش درخواست‌ها">
          <pre dir="ltr">
            {JSON.stringify(
              activeDrafts.map(
                ({
                  file,
                  sourceId,
                  knowledgeSpaceId,
                  version,
                  processingProfile,
                  customMetadata,
                }) => ({
                  file: { name: file.name, size: file.size },
                  sourceId,
                  knowledgeSpaceId,
                  version,
                  processingProfile,
                  customMetadata,
                }),
              ),
              null,
              2,
            )}
          </pre>
        </section>
      )}
    </section>
  );
}
