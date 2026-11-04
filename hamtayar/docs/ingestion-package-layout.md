# ساختار پیشنهادی بسته‌ی ingestion

این ساختار منطق اجرای سند را زیر یک بسته جمع می‌کند. قراردادها در `packages/contracts` و adapterهای زیرساختی (ذخیره‌سازی، Qdrant و مجوزدهی) در بسته‌های مالک خود باقی می‌مانند؛ سرویس‌های ingestion آن‌ها را از طریق تزریق وابستگی دریافت می‌کنند. LangGraph فقط state، node و اتصال‌ها را نگه می‌دارد.

## درخت پوشه‌ها

```text
packages/
  contracts/                         # DTOهای مشترک موجود؛ مرجع واحد قراردادها
    common.py                         # SourceVersion, ContentRef
    document.py                       # DocumentInput, ParsedDocument, DocumentBlock
    chunks.py                         # ChunkingRequest, Chunk, ChunkingResult
    indexing.py                       # EmbeddingRecord, IndexingResult, Publication*
    document_ingestion.py             # ArtifactOutcome و DocumentWorkflowPorts (انتقال از apps)
    artifacts.py                      # ArtifactRepository protocol
  ingestion/
    config.py                         # re-export/load تنظیمات معتبر config/knowledge.toml
    workflow.py                       # DocumentIngestionService؛ facade هفت مرحله
    authorization.py                  # قرارداد/سرویس مجوز ingestion (بدون اعتماد به ورودی کاربر)
    artifacts.py                      # قرارداد سطح ingestion روی ArtifactRepository
    parsers/
      base.py                          # DocumentParser protocol و تشخیص نوع
      dispatch.py                      # انتخاب parser با filename/content_type
      txt/parser.py                    # مقصد پیشنهادی برای packages/ingestion/txt/parser.py
      markdown/parser.py               # مقصد پیشنهادی برای packages/ingestion/markdown/parser.py
    loading/service.py                 # اعتبارسنجی منبع، مجوز، stage raw پایدار
    normalization/service.py           # ترکیب cleaner + normalizer موجود
    chunking/service.py                # ParsedDocument -> ChunkingResult
    embedding/service.py               # ChunkingResult -> list[EmbeddingRecord]
    indexing/service.py                # نوشتن و read-back نسل ایندکس
    publication/service.py             # فعال‌سازی اتمیک نسل
  storage/artifacts/repository.py      # پیاده‌سازی durable/local از قرارداد artifacts
  knowledge/configuration.py           # فعلاً مالک واقعی تنظیمات و اعتبارسنجی TOML
  knowledge/tokenizer.py               # tokenizer دقیق BGE موجود؛ بدون بارگذاری وزن مدل
  documents/                           # cleaner/normalizer فعلی تا زمان انتقال
  storage/                              # پیاده‌سازی فعلی Qdrant و storage
apps/document_ingestion/workflows/document_ingestion/
  state.py
  graph.py
  nodes/{load_document,parse,normalize,chunk,embed,index,activate}.py
```

در working tree فعلی parserهای TXT و Markdown از قبل به `packages/ingestion/{txt,markdown}` منتقل شده‌اند؛ در درخت نهایی بهتر است این دو زیر `packages/ingestion/parsers/` گروه‌بندی شوند و importهای مصرف‌کننده در همان تغییر اصلاح شوند. Cleaner و normalizer هنوز در `packages/documents` هستند. سرویس‌های جدید `packages/ingestion` می‌توانند فعلاً آن‌ها را پشت API خود wrap کنند؛ حذف فیزیکی `packages/documents` بعد از مهاجرت و اصلاح importها انجام شود. همین‌طور `packages/knowledge` اکنون مالک config و tokenizer است و `packages/storage` مالک Qdrant می‌ماند. قراردادهای Graph را دوباره در `apps/` تعریف نکنید.

## اتصال Graph به سرویس

هر node فقط port متناظر را فراخوانی می‌کند. امضاها از `DocumentWorkflowPorts` در `packages/contracts/document_ingestion.py` می‌آیند:

```python
class DocumentWorkflowPorts(Protocol):
    async def load_document(self, *, document: DocumentInput, access: AccessMetadata) -> ArtifactOutcome: ...
    async def parse(self, *, source: SourceVersion, loaded: ContentRef, filename: str, content_type: str) -> ArtifactOutcome: ...
    async def normalize(self, *, source: SourceVersion, parsed: ContentRef, profile: str) -> ArtifactOutcome: ...
    async def chunk(self, *, source: SourceVersion, normalized: ContentRef, access: AccessMetadata, profile: str) -> ChunkArtifactOutcome: ...
    async def embed(self, *, source: SourceVersion, chunks: ContentRef) -> ArtifactOutcome: ...
    async def index(self, *, source: SourceVersion, chunks: ContentRef, embeddings: ContentRef, access: AccessMetadata) -> IndexingResult: ...
    async def activate(self, *, request: PublicationRequest, access: AccessMetadata) -> PublicationResult: ...
```

در `apps/bootstrap.py` نمونه‌ی facade را با dependencyهای concrete می‌سازید و از طریق config/dependency به graph می‌دهید. هر node خروجی را در state قرار می‌دهد؛ هیچ فایل، `ParsedDocument`، chunk یا vector را به state/checkpoint اضافه نمی‌کند.

## سرویس‌ها و ورودی/خروجی هر مرحله

| مرحله | سرویس پیشنهادی | کار تابع | قرارداد داده |
|---|---|---|---|
| load | `LoadingService.load_document` | اعتبارسنجی ورودی و مجوز، کپی stream به artifact پایدار | `DocumentInput`, `AccessMetadata` -> `ArtifactOutcome` |
| parse | `ParserDispatchService.parse` | انتخاب parser براساس پسوند/MIME، خواندن raw در context، ذخیره ParsedDocument | `ContentRef` -> `ArtifactOutcome` |
| normalize | `NormalizationService.normalize` | اعمال cleaning و normalization به blockها با حفظ location و protected spans | parsed ref -> normalized ref |
| chunk | `ChunkingService.chunk` | ساخت `ChunkingRequest` با `prepare_chunking_request`، شمارش با tokenizer کانفیگ، تولید Chunkها | normalized ref -> `ChunkArtifactOutcome` |
| embed | `EmbeddingService.embed` | بارگذاری مدل BGE در adapter، تولید یک vector dense برای هر chunk، ذخیره batch | chunks ref -> embedding ref |
| index | `IndexingService.index` | تطبیق chunk/vector بر اساس chunk_id، نوشتن idempotent و read-back | `IndexingResult(validated=True)` |
| activate | `PublicationService.activate` | اعتبارسنجی generation و ثبت اتمیک active generation | `PublicationResult(published=True)` |

`load/parse/normalize/chunk/embed` باید خطای قابل‌انتظار را به `ErrorDetail` برگردانند؛ خطاهای غیرمنتظره و retryable را با همان vocabulary مشترک به runtime بسپارند. `index` تنها پس از read-back می‌تواند `validated=True` بدهد و `activate` فقط پس از commit پایدار `published=True` برگرداند.

## Chunking و Embedding

کانفیگ موجود `config/knowledge.toml` در حال حاضر محل واحد تنظیمات است: مدل `BAAI/bge-m3`، ابعاد ۱۰۲۴، normalization، سقف ۵۱۲ token، profile و سیاست oversized را تعریف کرده. آن را به فایل دوم منتقل نکنید. Loader فعلی `packages.knowledge.configuration.load_knowledge_configuration` را در Composition Root یک بار اجرا کنید و همان `KnowledgeConfiguration` را به tokenizer، chunker و embedder تزریق کنید.

Tokenizer فعلی فقط tokenizer را lazy-load می‌کند؛ این به معنی پیاده‌سازی embedding نیست. adapter embedding باید جدا باشد و تنظیمات زیر را از `configuration.embedding` بخواند: `model_id`, `model_revision`, `dimensions`, `normalize_embeddings`. پیاده‌سازی را پشت یک protocol کوچک نگه دارید تا انتخاب runtime مدل (برای مثال Sentence Transformers/FlagEmbedding) از node و contract جدا بماند. تضمین کنید مدل BGE-M3 در حالت dense خروجی ۱۰۲۴ بعدی بدهد و ترتیب vectorها با `chunk_id` حفظ شود. ابعاد و شناسه مدل را از ثابت‌های پخش‌شده در کد نخوانید.

chunker از `prepare_chunking_request` و `ChunkingRequest` استفاده کند. برای هر item، تعداد tokenها را با همان tokenizer و همان `include_special_tokens` بشمارد. `structure_aware_v1` فعلی `overlap_tokens=0` و `oversized_content_policy="error"` الزام می‌کند؛ بنابراین تا زمانی که الگوریتم split ساختاری و سیاست citation برای block بزرگ تعریف نشده، از بریدن خام متن و تولید citation نادرست خودداری کنید و block بزرگ را با `VALIDATION_ERROR` گزارش دهید. Chunkهای خروجی باید `Chunk`های قرارداد موجود باشند و `chunk_id` قطعی از source/version/block/ordinal ساخته شود تا retry idempotent باشد.

## شکل پیشنهادی adapterهای Domain

هر سرویس constructor injection داشته باشد؛ نمونه‌ی امضای سطح سرویس:

```python
class ChunkingService:
    def __init__(self, *, repository: ArtifactRepository, configuration: KnowledgeConfiguration, tokenizer: TokenCounter): ...
    async def chunk(self, *, source: SourceVersion, normalized: ContentRef, access: AccessMetadata, profile: str) -> ChunkArtifactOutcome: ...

class EmbeddingService:
    def __init__(self, *, repository: ArtifactRepository, configuration: KnowledgeConfiguration, model: EmbeddingModel): ...
    async def embed(self, *, source: SourceVersion, chunks: ContentRef) -> ArtifactOutcome: ...
```

`ArtifactRepository` از `packages/contracts/artifacts.py` می‌آید و عملیات `get_parsed/put_parsed/get_chunks/put_chunks/get_embeddings/put_embeddings` را انجام می‌دهد. خود سرویس‌ها storage SDK یا مسیر فایل را نمی‌شناسند. نسخه‌ی Local repository فقط برای توسعه/تست است؛ runtime چندنمونه‌ای به backend اشتراکی نیاز دارد.

## ترتیب پیاده‌سازی

۱. انتقال `ArtifactOutcome`, `ChunkArtifactOutcome`, `DocumentWorkflowPorts` به contracts و اصلاح import nodeها. ۲. قرارداد و backend artifact پایدار. ۳. parser dispatcher با reuse parserهای موجود. ۴. loader و authorization معتبر. ۵. normalize و chunk با config واحد. ۶. embedding adapter BGE و اعتبارسنجی dimension. ۷. index/read-back و publication idempotent. ۸. facade و اتصال در bootstrap. تا مرحله‌ی ۲ تمام نشده graph واقعی را با checkpoint پایدار اجرا نکنید؛ `ContentRef`های موقت بعد از restart قابل بازیابی نیستند.
