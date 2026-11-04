import { useMode } from '../../app/ModeProvider';
import { ModeSelector } from '../../components/common/ModeSelector';
import { MetadataFields } from '../../components/metadata/MetadataFields';
import { SafeAnswerMarkdown } from '../../components/answers/SafeAnswerMarkdown';
import { TestDetailsPanel } from '../../components/operations/TestDetailsPanel';
import { metadataConfigService } from '../../services/metadata/metadataConfigService';
import { useMetadata } from '../../services/metadata/useMetadata';
import { createWorkspaceStore } from '../../services/operations/workspaceStore';
import { runOperation, useOperation } from '../../services/operations/operationService';
import {
  hamtayarReadiness,
  type AnswerResult,
} from '../../services/api/adapters/hamtayarAdapter';
import type { MetadataValues } from '../../types/metadata';
import { buildQuery, type QueryModel } from './queryModel';
import { qaService } from './qaService';
const store = createWorkspaceStore(() => ({
  question: '',
  user: {} as MetadataValues,
  filters: {} as MetadataValues,
  error: '',
  preview: undefined as QueryModel | undefined,
  confirmed: false,
  history: [] as { question: string; result: AnswerResult; mode: string }[],
}));
store.observe(() => {
  for (const group of ['user', 'filters'] as const)
    metadataConfigService.setDraftValues(
      `qa-store-${group}`,
      store.get()[group],
      (keys) =>
        store.set({
          [group]: Object.fromEntries(
            Object.entries(store.get()[group]).filter(([key]) => !keys.includes(key)),
          ),
        }),
    );
});
export function QAPage({ showMode = true }: { showMode?: boolean }) {
  const state = store.use();
  const { mode, canSwitchMode } = useMode();
  const { definitions, warning } = useMetadata();
  const op = useOperation<AnswerResult>('qa');
  const gate = hamtayarReadiness('qa');
  function query() {
    const q = state.question.trim();
    if (!q || q.includes('\0')) throw new Error('پرسش معتبر و غیرخالی وارد کنید.');
    if (mode === 'api' && Array.from(q).length > 4096)
      throw new Error('پرسش API باید حداکثر ۴۰۹۶ نویسه باشد.');
    return buildQuery(q, state.user, state.filters, definitions);
  }
  function preview() {
    try {
      store.set({ preview: query(), error: '' });
    } catch (error) {
      store.set({ error: (error as Error).message });
    }
  }
  async function submit() {
    if (!canSwitchMode || (mode === 'api' && (!gate.ready || !state.confirmed))) return;
    try {
      const intended = query();
      store.set({ preview: intended, error: '' });
      const result = await runOperation('qa', mode, (signal) =>
        mode === 'demo'
          ? qaService.runDemo()
          : qaService.runApi(intended.question, signal),
      );
      if (result)
        store.set({
          history: [
            ...store.get().history,
            { question: intended.question, result, mode },
          ],
        });
    } catch (error) {
      store.set({ error: (error as Error).message });
    }
  }
  return (
    <section className="page-content">
      <p className="eyebrow">جست‌وجو در دانش</p>
      <h1>پرسش‌وپاسخ</h1>
      {showMode && <ModeSelector />}
      <p className="notice">
        {mode === 'demo'
          ? 'پاسخ و منابع ثابت و نمایشی هستند؛ فیلترها و اطلاعات کاربر روی نتیجه نمونه اعمال نمی‌شوند.'
          : 'فقط سؤال ارسال می‌شود؛ پاسخ غیرشخصی‌سازی‌شده و بدون فیلتر است.'}
      </p>
      {warning && <p role="alert">{warning}</p>}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
      >
        <fieldset disabled={!canSwitchMode}>
          <legend>پرسش و اطلاعات توصیفی</legend>
          <label htmlFor="question">پرسش شما</label>
          <textarea
            id="question"
            rows={4}
            value={state.question}
            onChange={(e) => store.set({ question: e.target.value, preview: undefined })}
            aria-describedby={state.error ? 'qa-error' : undefined}
          />
          <h2>اطلاعات توصیفی کاربر</h2>
          <p>این اطلاعات هویت یا مجوز دسترسی نیستند.</p>
          <MetadataFields
            definitions={definitions}
            group="user"
            values={state.user}
            onChange={(key, value) =>
              store.set({ user: { ...state.user, [key]: value }, preview: undefined })
            }
          />
          <h2>فیلتر اسناد</h2>
          <p>
            شرط‌های فیلدهای مختلف با «و» ترکیب می‌شوند؛ چند مقدار در یک فیلد یعنی «یکی
            از».
          </p>
          <MetadataFields
            definitions={definitions}
            queryFilters
            group="document"
            values={state.filters}
            onChange={(key, value) =>
              store.set({
                filters: { ...state.filters, [key]: value },
                preview: undefined,
              })
            }
          />
          {mode === 'api' && (
            <label>
              <input
                type="checkbox"
                checked={state.confirmed}
                onChange={(e) => store.set({ confirmed: e.target.checked })}
              />
              آزمون فقط سؤال، بدون فیلتر و اطلاعات توصیفی را تأیید می‌کنم.
            </label>
          )}
        </fieldset>
        {state.error && (
          <p role="alert" id="qa-error">
            {state.error}
          </p>
        )}
        {mode === 'api' && <p role="status">{gate.reason}</p>}
        <div className="actions">
          <button
            className="button"
            type="submit"
            disabled={
              !canSwitchMode || (mode === 'api' && (!gate.ready || !state.confirmed))
            }
          >
            {mode === 'demo' ? 'نمایش پاسخ نمونه' : 'آزمون فقط سؤال'}
          </button>
          <button className="button button--quiet" type="button" onClick={preview}>
            پیش‌نمایش پرسش
          </button>
        </div>
      </form>
      {op?.status === 'pending' && <p role="status">در انتظار پاسخ…</p>}
      {op?.diagnostic && <p role="alert">{op.diagnostic.message}</p>}
      {op?.result && (
        <article className="workspace-card">
          <h2>{op.mode === 'demo' ? 'پاسخ نمونه' : 'پاسخ واقعی سرویس'}</h2>
          {op.result.status === 'no_evidence' && <p>شواهد کافی پیدا نشد.</p>}
          <SafeAnswerMarkdown text={op.result.answer} />
          <h3>{op.mode === 'demo' ? 'منابع نمونه' : 'منابع پاسخ'}</h3>
          <ul>
            {op.result.citations.map((c, i) => (
              <li key={`${c.sourceId}-${i}`}>
                {c.title}{' '}
                <bdi>
                  {c.sourceId} · {c.version}
                </bdi>
              </li>
            ))}
          </ul>
        </article>
      )}
      {state.history.length > 1 && (
        <section>
          <h2>پرسش‌های قبلی این نشست</h2>
          <p>
            تاریخچه فقط در حافظه مرورگر است؛ مکالمه چندمرحله‌ای به سرویس ارسال نمی‌شود.
          </p>
          {state.history.slice(0, -1).map((entry, index) => (
            <details key={index}>
              <summary>
                {entry.question} · {entry.mode === 'demo' ? 'نمایشی' : 'API'}
              </summary>
              <SafeAnswerMarkdown text={entry.result.answer} />
            </details>
          ))}
        </section>
      )}
      <TestDetailsPanel
        intended={state.preview}
        transmitted={
          op?.mode === 'api' && state.preview
            ? { question: state.preview.question }
            : undefined
        }
        operation={op}
      />
    </section>
  );
}
