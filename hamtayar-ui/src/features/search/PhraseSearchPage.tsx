import { useMode } from '../../app/ModeProvider';
import { CLASSIFICATION_OPTIONS } from '../../config/demoProfile';
import { documentCatalog } from '../../services/documentCatalog';
import { createWorkspaceStore } from '../../services/operations/workspaceStore';
import { buildPhraseSearchRequest, type PhraseSearchRequest } from './searchRequest';
import { searchDocuments, type PhraseResult } from './searchDocuments';
const store = createWorkspaceStore(() => ({
  phrase: '',
  center: '',
  classification: '',
  error: '',
  results: [] as PhraseResult[],
  searched: false,
  preview: false,
}));
export function PhraseSearchPage() {
  const { mode } = useMode();
  const catalog = documentCatalog.use();
  const state = store.use();
  const unsupported = catalog.documents.filter((d) => d.text === undefined);
  let request: PhraseSearchRequest | undefined;
  let validationError = '';
  try {
    request = buildPhraseSearchRequest(
      state.phrase,
      state.center,
      state.classification,
      catalog.centers,
    );
  } catch (error) {
    validationError = (error as Error).message;
  }
  function preview() {
    store.set({ preview: true, error: validationError });
  }
  function search() {
    if (mode === 'api') return;
    if (!request) {
      store.set({ error: validationError });
      return;
    }
    store.set({
      error: '',
      searched: true,
      results: searchDocuments(catalog.documents, request),
    });
  }

  return (
    <section className="page-content">
      <p className="eyebrow">جستجو در متن اسناد</p>
      <h1>جستجو عبارت در اسناد سازمانی</h1>
      <p className="notice">
        جستجوی محلی و مستقیم روی متن TXT و Markdown ثبت‌شده در همین نشست دمو؛ عبارات به
        صورت لفظی و بدون تفاوت حروف بزرگ و کوچک انگلیسی بررسی می‌شوند.
      </p>
      <form
        className="workspace-card search-form"
        onSubmit={(e) => {
          e.preventDefault();
          search();
        }}
      >
        <label htmlFor="phrase">عبارت موردنظر</label>
        <input
          id="phrase"
          value={state.phrase}
          maxLength={512}
          onChange={(e) => store.set({ phrase: e.target.value, searched: false })}
          placeholder="مثلاً: مدیریت دانش"
        />
        <div className="metadata-fields">
          <div className="metadata-field">
            <label htmlFor="search-center">مرکز</label>
            <select
              id="search-center"
              value={state.center}
              onChange={(e) => store.set({ center: e.target.value, searched: false })}
            >
              <option value="">همه مراکز</option>
              {catalog.centers.map((center) => (
                <option key={center}>{center}</option>
              ))}
            </select>
          </div>
          <div className="metadata-field">
            <label htmlFor="search-classification">نوع سند</label>
            <select
              id="search-classification"
              value={state.classification}
              onChange={(e) =>
                store.set({ classification: e.target.value, searched: false })
              }
            >
              <option value="">همه انواع</option>
              {CLASSIFICATION_OPTIONS.map((o) => (
                <option value={o.value} key={o.value}>
                  {o.labelFa}
                </option>
              ))}
            </select>
          </div>
        </div>
        {state.error && <p role="alert">{state.error}</p>}
        {mode === 'api' && (
          <p role="status">
            جستجوی واقعی سرویس اسناد هنوز متصل نیست. برای جستجوی محلی حالت نمایشی را
            انتخاب کنید.
          </p>
        )}
        <div className="actions">
          <button
            className="button button--primary"
            type="submit"
            disabled={mode === 'api'}
          >
            جستجوی عبارت
          </button>
          <button className="button button--quiet" type="button" onClick={preview}>
            پیش‌نمایش درخواست
          </button>
        </div>
      </form>
      {state.preview && request && (
        <section
          className="request-preview workspace-card"
          role="region"
          aria-label="پیش‌نمایش درخواست جستجو"
        >
          <div className="section-heading">
            <h2>پیش‌نمایش درخواست جستجو</h2>
            <button
              type="button"
              className="button button--quiet"
              onClick={() => store.set({ preview: false })}
            >
              بستن پیش‌نمایش
            </button>
          </div>
          <p>
            این JSON الگوی پیشنهادی درخواست و ورودی جستجوی محلی است؛ هنوز endpoint جستجوی
            سرویس متصل نشده و در دمو درخواست شبکه‌ای ارسال نمی‌شود.
          </p>
          <pre dir="ltr">{JSON.stringify(request, null, 2)}</pre>
        </section>
      )}
      {catalog.documents.length === 0 && (
        <div className="empty-state">
          <h2>هنوز سندی برای جستجو ندارید</h2>
          <p>
            ابتدا یک فایل TXT یا Markdown را در بخش پردازش اسناد سازمانی ثبت نمایشی کنید.
          </p>
        </div>
      )}
      {unsupported.length > 0 && (
        <details className="test-details">
          <summary>{unsupported.length} سند در جستجوی محلی پوشش ندارد</summary>
          <ul>
            {unsupported.map((d) => (
              <li key={d.sourceId}>
                <bdi>{d.name}</bdi> — {d.searchNote}
              </li>
            ))}
          </ul>
        </details>
      )}
      {state.searched && (
        <section aria-label="نتایج جستجو" className="search-results">
          <div className="section-heading">
            <h2>نتایج جستجو</h2>
            <span role="status">{state.results.length} سند مطابق</span>
          </div>
          {state.results.length === 0 && (
            <p>عبارت در اسناد قابل جستجو با این فیلترها پیدا نشد.</p>
          )}
          {state.results.map((result) => (
            <article className="workspace-card" key={result.document.sourceId}>
              <h3>
                <bdi>{result.document.name}</bdi>
              </h3>
              <div className="result-tags">
                <span>{result.document.center}</span>
                <span>
                  {
                    CLASSIFICATION_OPTIONS.find(
                      (o) => o.value === result.document.classification,
                    )?.labelFa
                  }
                </span>
              </div>
              <p className="match-snippet">
                …{result.before}
                <mark>{result.match}</mark>
                {result.after}…
              </p>
            </article>
          ))}
        </section>
      )}
    </section>
  );
}
