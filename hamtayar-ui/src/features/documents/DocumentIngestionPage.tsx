import { useMode } from '../../app/ModeProvider';
import {
  documentCatalog,
  prepareLocalDocument,
  type LocalDocument,
} from '../../services/documentCatalog';
import { DEMO_METADATA_FIELDS } from '../../config/demoProfile';
import {
  filterActiveMetadataValues,
  validateMetadataValues,
} from '../../services/metadata/values';
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
const store = createWorkspaceStore(() => ({
  drafts: [] as DocumentDraft[],
  error: '',
  preview: false,
  reduced: false,
}));
export function DocumentIngestionPage() {
  const state = store.use();
  const { mode, canSwitchMode } = useMode();
  const definitions = DEMO_METADATA_FIELDS;
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
        knowledgeSpaceId: 'demo-documents',
        version: '1',
        processingProfile: 'default',
        customMetadata: {},
      });
    }
    store.set({
      drafts: [...state.drafts, ...drafts],
      error: errors.join(' '),
      preview: false,
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
      activeDrafts.map(async (d) => {
        let localDocument: LocalDocument | undefined;
        const result = await runOperation(
          d.id,
          mode,
          async (signal) => {
            if (mode === 'api') return ingestDocument(d, state.reduced, signal);
            const result = await documentsService.runDemo(d);
            localDocument = await prepareLocalDocument(d, signal);
            return result;
          },
          true,
        );
        if (result?.status === 'completed' && localDocument)
          documentCatalog.register(localDocument);
      }),
    );
  }
  return (
    <section className="page-content">
      <p className="eyebrow">فضای اسناد</p>
      <h1>پردازش اسناد سازمانی</h1>
      <p className="notice">
        {mode === 'demo'
          ? 'ثبت در همین نشست دمو؛ فایل به سرور ارسال نمی‌شود. متن TXT و Markdown تا ۲ مگابایت برای جستجوی محلی خوانده می‌شود.'
          : 'آزمون واقعی؛ نتیجه ساختگی جایگزین خطا نمی‌شود.'}
      </p>
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
          پردازش
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
          onClick={() => store.set({ drafts: [], error: '', preview: false })}
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
