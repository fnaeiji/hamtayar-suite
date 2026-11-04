import { useMode } from '../../app/ModeProvider';
import { ModeSelector } from '../../components/common/ModeSelector';
import { TestDetailsPanel } from '../../components/operations/TestDetailsPanel';
import { createWorkspaceStore } from '../../services/operations/workspaceStore';
import { runOperation, useOperation } from '../../services/operations/operationService';
import { cgcReadiness } from '../../services/api/adapters/cgcAdapter';
import { codebaseService } from './codebaseService';
const store = createWorkspaceStore(() => ({
  file: undefined as File | undefined,
  project: '',
  error: '',
}));
export function CodebasePage({ showMode = true }: { showMode?: boolean }) {
  const state = store.use();
  const { mode, canSwitchMode } = useMode();
  const op =
    useOperation<Awaited<ReturnType<typeof codebaseService.runDemo>>>('codebase');
  const gate = cgcReadiness();
  async function submit() {
    if (!canSwitchMode || mode === 'api') return;
    if (!state.file || !state.project.trim()) {
      store.set({ error: 'آرشیو و نام پروژه را وارد کنید.' });
      return;
    }
    store.set({ error: '' });
    await runOperation('codebase', mode, () => codebaseService.runDemo());
  }
  return (
    <section className="page-content">
      <p className="eyebrow">دانش کد</p>
      <h1>پایگاه کد</h1>
      {showMode && <ModeSelector />}
      <p className="notice">
        نمایش مراحل نمونه؛ آرشیو استخراج نمی‌شود و هیچ گراف واقعی ساخته نمی‌شود.
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
      >
        <fieldset disabled={!canSwitchMode}>
          <legend>پروژه کد</legend>
          <label>
            نام پروژه
            <input
              value={state.project}
              onChange={(e) => store.set({ project: e.target.value })}
            />
          </label>
          <label className="drop-zone">
            آرشیو کد
            <input
              type="file"
              accept=".zip,.rar"
              onChange={(e) => {
                const file = e.target.files?.[0];
                const valid = file && /\.(zip|rar)$/i.test(file.name);
                store.set({
                  file: valid ? file : undefined,
                  error: valid ? '' : 'فقط آرشیو ZIP یا RAR انتخاب کنید.',
                });
              }}
            />
          </label>
          {state.file && (
            <p>
              <bdi>{state.file.name}</bdi> · {state.file.size} بایت
            </p>
          )}
        </fieldset>
        {state.error && <p role="alert">{state.error}</p>}
        {mode === 'api' && <p role="status">{gate.reason}</p>}
        <button
          className="button"
          disabled={!canSwitchMode || mode === 'api'}
          type="submit"
        >
          {mode === 'demo' ? 'اجرای نمایش کد' : 'پردازش در سرویس'}
        </button>
      </form>
      {op?.status === 'pending' && <p role="status">در حال اجرای نمونه…</p>}
      {op?.diagnostic && <p role="alert">{op.diagnostic.message}</p>}
      {op?.result && (
        <section className="workspace-card">
          <h2>گزارش مراحل نمایشی</h2>
          <ol>
            {op.result.logs.map((log) => (
              <li key={log}>{log}</li>
            ))}
          </ol>
          <p>
            وضعیت نمونه: <bdi>{op.result.status}</bdi>
          </p>
        </section>
      )}
      <TestDetailsPanel operation={op} />
    </section>
  );
}
