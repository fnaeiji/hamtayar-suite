import { useEffect, useState, useSyncExternalStore, type FormEvent } from 'react';
import { MetadataFields } from '../../components/metadata/MetadataFields';
import { LoadingState } from '../../components/common/LoadingState';
import { StatusMessage } from '../../components/common/StatusMessage';
import {
  DEFAULT_METADATA_FIELDS,
  MetadataDefinitionError,
  metadataConfigService,
} from '../../services/metadata/metadataConfigService';
import type {
  MetadataFieldDefinition,
  MetadataFieldType,
  MetadataFieldValue,
  MetadataValues,
} from '../../types/metadata';

type EditorDraft = {
  key: string;
  labelFa: string;
  group: 'document' | 'user';
  type: MetadataFieldType;
  optionsText: string;
  required: boolean;
  enabled: boolean;
  visibleInForm: boolean;
  filterable: boolean;
};

const emptyDraft: EditorDraft = {
  key: '',
  labelFa: '',
  group: 'document',
  type: 'text',
  optionsText: '',
  required: false,
  enabled: true,
  visibleInForm: true,
  filterable: false,
};

function toDraft(field?: MetadataFieldDefinition): EditorDraft {
  if (!field) return { ...emptyDraft };
  return {
    key: field.key,
    labelFa: field.labelFa,
    group: field.group,
    type: field.type,
    optionsText: (field.options ?? [])
      .map(({ value, labelFa }) => `${value}=${labelFa}`)
      .join('\n'),
    required: field.required,
    enabled: field.enabled,
    visibleInForm: field.visibleInForm,
    filterable: field.group === 'document' && field.filterable,
  };
}

function parseOptions(text: string) {
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const separator = line.indexOf('=');
      if (separator < 0) return { value: line, labelFa: '' };
      return {
        value: line.slice(0, separator).trim(),
        labelFa: line.slice(separator + 1).trim(),
      };
    });
}

function toDefinition(draft: EditorDraft): MetadataFieldDefinition {
  const common = {
    key: draft.key.trim(),
    labelFa: draft.labelFa.trim(),
    type: draft.type,
    required: draft.required,
    enabled: draft.enabled,
    visibleInForm: draft.visibleInForm,
    ...(['select', 'multi_select'].includes(draft.type)
      ? { options: parseOptions(draft.optionsText) }
      : {}),
  };
  return draft.group === 'document'
    ? { ...common, group: 'document', filterable: draft.filterable }
    : { ...common, group: 'user' };
}

function needsConfirmation(keys: string[]): boolean {
  if (keys.length === 0) return true;
  return window.confirm(
    'این تغییر مقدارهای واردشده را حذف یا نامعتبر می‌کند. ادامه می‌دهید؟',
  );
}

export function MetadataSettingsPage() {
  const state = useSyncExternalStore(
    metadataConfigService.subscribe,
    metadataConfigService.getSnapshot,
    metadataConfigService.getSnapshot,
  );
  const [draft, setDraft] = useState<EditorDraft>({ ...emptyDraft });
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [error, setError] = useState('');
  const [previewValues, setPreviewValues] = useState<MetadataValues>({});
  const [filterPreviewValues, setFilterPreviewValues] = useState<MetadataValues>({});

  useEffect(() => {
    metadataConfigService.load();
  }, []);

  if (!state.loaded) return <LoadingState label="در حال بارگذاری تنظیمات فراداده…" />;

  function openNewField() {
    setDraft({ ...emptyDraft });
    setEditingKey(null);
    setError('');
    setEditorOpen(true);
  }

  function openEditField(field: MetadataFieldDefinition) {
    setDraft(toDraft(field));
    setEditingKey(field.key);
    setError('');
    setEditorOpen(true);
  }

  function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    const definition = toDefinition(draft);
    const nextDefinitions = editingKey
      ? state.definitions.map((field) => (field.key === editingKey ? definition : field))
      : [...state.definitions, definition];
    const affected = metadataConfigService.getPotentiallyDiscardedKeys(nextDefinitions);
    if (!needsConfirmation(affected)) return;

    try {
      metadataConfigService.save(nextDefinitions);
      if (affected.length > 0) {
        metadataConfigService.discardDraftValues(affected);
        setPreviewValues((current) => {
          const next = { ...current };
          for (const key of affected) delete next[key];
          return next;
        });
        setFilterPreviewValues((current) => {
          const next = { ...current };
          for (const key of affected) delete next[key];
          return next;
        });
      }
      setEditorOpen(false);
      setEditingKey(null);
    } catch (saveError) {
      setError(
        saveError instanceof MetadataDefinitionError
          ? saveError.errors.join(' ')
          : 'تعریف فیلد ذخیره نشد. ورودی‌ها را بررسی کنید.',
      );
    }
  }

  function handleDelete(field: MetadataFieldDefinition) {
    const nextDefinitions = state.definitions.filter((item) => item.key !== field.key);
    const affected = metadataConfigService.getPotentiallyDiscardedKeys(nextDefinitions);
    if (!needsConfirmation(affected)) return;
    metadataConfigService.save(nextDefinitions);
    metadataConfigService.discardDraftValues(affected);
    setPreviewValues((current) => {
      const next = { ...current };
      for (const key of affected) delete next[key];
      return next;
    });
    setFilterPreviewValues((current) => {
      const next = { ...current };
      for (const key of affected) delete next[key];
      return next;
    });
  }

  function handleRestoreDefaults() {
    const affected = metadataConfigService.getPotentiallyDiscardedKeys(DEFAULT_METADATA_FIELDS);
    if (!needsConfirmation(affected)) return;
    metadataConfigService.restoreDefaults();
    metadataConfigService.discardDraftValues(affected);
    setPreviewValues((current) => {
      const next = { ...current };
      for (const key of affected) delete next[key];
      return next;
    });
    setFilterPreviewValues((current) => {
      const next = { ...current };
      for (const key of affected) delete next[key];
      return next;
    });
    setEditorOpen(false);
    setEditingKey(null);
  }

  function updatePreview(key: string, value: MetadataFieldValue) {
    setPreviewValues((current) => ({ ...current, [key]: value }));
  }

  return (
    <section className="page-content metadata-settings" aria-labelledby="metadata-title">
      <p className="eyebrow">تنظیمات محلی</p>
      <h1 id="metadata-title">تنظیم فراداده</h1>
      <p className="page-intro">
        تعریف فیلدها فقط در همین مرورگر ذخیره می‌شود و به سرویس یا کاربر دیگری منتقل نمی‌شود.
      </p>
      {state.warning && <StatusMessage tone="warning">{state.warning}</StatusMessage>}
      {error && <StatusMessage tone="error">{error}</StatusMessage>}

      <div className="metadata-toolbar">
        <button className="button button--primary" onClick={openNewField} type="button">
          افزودن فیلد
        </button>
        <button className="button button--quiet" onClick={handleRestoreDefaults} type="button">
          بازگردانی پیش‌فرض‌ها
        </button>
      </div>

      {editorOpen && (
        <form className="metadata-editor" onSubmit={handleSave}>
          <h2>{editingKey ? 'ویرایش فیلد' : 'افزودن فیلد جدید'}</h2>
          <div className="metadata-editor__grid">
            <label>
              کلید انگلیسی
              <input
                autoComplete="off"
                disabled={editingKey !== null}
                onChange={(event) => setDraft({ ...draft, key: event.target.value })}
                required
                value={draft.key}
              />
            </label>
            <label>
              برچسب فارسی
              <input
                onChange={(event) => setDraft({ ...draft, labelFa: event.target.value })}
                required
                value={draft.labelFa}
              />
            </label>
            <label>
              گروه
              <select
                onChange={(event) =>
                  setDraft({ ...draft, group: event.target.value as EditorDraft['group'] })
                }
                value={draft.group}
              >
                <option value="document">سند</option>
                <option value="user">کاربر</option>
              </select>
            </label>
            <label>
              نوع داده
              <select
                onChange={(event) =>
                  setDraft({ ...draft, type: event.target.value as MetadataFieldType })
                }
                value={draft.type}
              >
                <option value="text">متن</option>
                <option value="number">عدد</option>
                <option value="boolean">درست/نادرست</option>
                <option value="select">انتخاب تکی</option>
                <option value="multi_select">انتخاب چندگانه</option>
              </select>
            </label>
            {['select', 'multi_select'].includes(draft.type) && (
              <label className="metadata-editor__options">
                گزینه‌ها (هر خط: مقدار=برچسب فارسی)
                <textarea
                  onChange={(event) => setDraft({ ...draft, optionsText: event.target.value })}
                  rows={4}
                  value={draft.optionsText}
                />
              </label>
            )}
          </div>
          <div className="metadata-editor__flags">
            <label>
              <input
                checked={draft.required}
                onChange={(event) => setDraft({ ...draft, required: event.target.checked })}
                type="checkbox"
              />
              الزامی
            </label>
            <label>
              <input
                checked={draft.enabled}
                onChange={(event) => setDraft({ ...draft, enabled: event.target.checked })}
                type="checkbox"
              />
              فعال
            </label>
            <label>
              <input
                checked={draft.visibleInForm}
                onChange={(event) =>
                  setDraft({ ...draft, visibleInForm: event.target.checked })
                }
                type="checkbox"
              />
              نمایش در فرم
            </label>
            {draft.group === 'document' && (
              <label>
                <input
                  checked={draft.filterable}
                  onChange={(event) =>
                    setDraft({ ...draft, filterable: event.target.checked })
                  }
                  type="checkbox"
                />
                قابل استفاده در فیلتر پرسش‌وپاسخ
              </label>
            )}
          </div>
          <div className="metadata-editor__actions">
            <button className="button button--primary" type="submit">
              ذخیره فیلد
            </button>
            <button
              className="button button--quiet"
              onClick={() => {
                setEditorOpen(false);
                setEditingKey(null);
                setError('');
              }}
              type="button"
            >
              انصراف
            </button>
          </div>
        </form>
      )}

      <section aria-labelledby="definitions-title" className="metadata-definition-section">
        <h2 id="definitions-title">تعریف‌های موجود</h2>
        <div className="metadata-definition-list">
          {state.definitions.map((field) => (
            <article className="metadata-definition" key={field.key}>
              <div>
                <h3>{field.labelFa}</h3>
                <p>
                  <code dir="ltr">{field.key}</code> · {field.group === 'document' ? 'سند' : 'کاربر'} ·{' '}
                  {field.type}
                </p>
              </div>
              <div className="metadata-definition__actions">
                <button
                  aria-label={`ویرایش ${field.labelFa}`}
                  className="button button--quiet"
                  onClick={() => openEditField(field)}
                  type="button"
                >
                  ویرایش
                </button>
                <button
                  aria-label={`حذف ${field.labelFa}`}
                  className="button button--quiet"
                  onClick={() => handleDelete(field)}
                  type="button"
                >
                  حذف
                </button>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section aria-labelledby="preview-title" className="metadata-preview">
        <h2 id="preview-title">پیش‌نمایش فیلدهای سند</h2>
        <MetadataFields
          definitions={state.definitions}
          group="document"
          onChange={updatePreview}
          values={previewValues}
        />
      </section>

      <section aria-labelledby="filter-preview-title" className="metadata-preview">
        <h2 id="filter-preview-title">پیش‌نمایش فیلترهای پرسش‌وپاسخ</h2>
        <MetadataFields
          definitions={state.definitions}
          onChange={(key, value) =>
            setFilterPreviewValues((current) => ({ ...current, [key]: value }))
          }
          queryFilters
          values={filterPreviewValues}
        />
      </section>
    </section>
  );
}
