import type {
  MetadataFieldDefinition,
  MetadataFieldType,
  MetadataOption,
  MetadataValues,
} from '../../types/metadata';

export const METADATA_STORAGE_KEY = 'hamtayar-demo-ui.metadata.v1';

const RESERVED_KEYS = new Set([
  'tenant_id',
  'acl_principals',
  'principals',
  'access_scope',
  'subject_id',
]);

export const DEFAULT_METADATA_FIELDS: MetadataFieldDefinition[] = [
  {
    key: 'department',
    labelFa: 'واحد سازمانی',
    group: 'document',
    type: 'select',
    options: [
      { value: 'engineering', labelFa: 'فنی' },
      { value: 'hr', labelFa: 'منابع انسانی' },
      { value: 'finance', labelFa: 'مالی' },
    ],
    required: false,
    enabled: true,
    visibleInForm: true,
    filterable: true,
  },
  {
    key: 'project',
    labelFa: 'پروژه',
    group: 'document',
    type: 'text',
    required: false,
    enabled: true,
    visibleInForm: true,
    filterable: false,
  },
  {
    key: 'document_type',
    labelFa: 'نوع سند',
    group: 'document',
    type: 'select',
    options: [
      { value: 'guide', labelFa: 'راهنما' },
      { value: 'report', labelFa: 'گزارش' },
      { value: 'policy', labelFa: 'آیین‌نامه' },
    ],
    required: false,
    enabled: true,
    visibleInForm: true,
    filterable: true,
  },
  {
    key: 'tags',
    labelFa: 'برچسب‌ها',
    group: 'document',
    type: 'multi_select',
    options: [
      { value: 'internal', labelFa: 'داخلی' },
      { value: 'customer_facing', labelFa: 'ویژه مشتری' },
      { value: 'research', labelFa: 'پژوهشی' },
    ],
    required: false,
    enabled: true,
    visibleInForm: true,
    filterable: true,
  },
  {
    key: 'display_name',
    labelFa: 'نام نمایشی کاربر',
    group: 'user',
    type: 'text',
    required: false,
    enabled: true,
    visibleInForm: true,
  },
  {
    key: 'expertise',
    labelFa: 'تخصص کاربر',
    group: 'user',
    type: 'text',
    required: false,
    enabled: true,
    visibleInForm: true,
  },
  {
    key: 'answer_language',
    labelFa: 'زبان پاسخ',
    group: 'user',
    type: 'select',
    options: [
      { value: 'fa', labelFa: 'فارسی' },
      { value: 'en', labelFa: 'انگلیسی' },
    ],
    required: false,
    enabled: true,
    visibleInForm: true,
  },
];

export type StorageLike = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

export type MetadataConfigState = {
  definitions: MetadataFieldDefinition[];
  loaded: boolean;
  persistenceAvailable: boolean | null;
  warning?: string;
};

export type MetadataValidationResult =
  | { valid: true; definitions: MetadataFieldDefinition[]; errors: [] }
  | { valid: false; definitions: null; errors: string[] };

export type MetadataValueValidationError = { key: string; message: string };

type MetadataConfigListener = () => void;

function cloneDefinitions(
  definitions: MetadataFieldDefinition[],
): MetadataFieldDefinition[] {
  return definitions.map((field) => ({
    ...field,
    ...(field.options ? { options: field.options.map((option) => ({ ...option })) } : {}),
  })) as MetadataFieldDefinition[];
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isFieldType(value: unknown): value is MetadataFieldType {
  return (
    value === 'text' ||
    value === 'number' ||
    value === 'boolean' ||
    value === 'select' ||
    value === 'multi_select'
  );
}

function parseOptions(
  rawOptions: unknown,
  type: MetadataFieldType,
  index: number,
  errors: string[],
): MetadataOption[] | undefined {
  const isSelection = type === 'select' || type === 'multi_select';
  if (!isSelection) {
    if (
      rawOptions !== undefined &&
      (!Array.isArray(rawOptions) || rawOptions.length > 0)
    ) {
      errors.push(`گزینه برای نوع داده فیلد شماره ${index + 1} مجاز نیست.`);
    }
    return undefined;
  }

  if (!Array.isArray(rawOptions) || rawOptions.length === 0) {
    errors.push(`برای فیلد انتخابی شماره ${index + 1} دست‌کم یک گزینه لازم است.`);
    return [];
  }

  const seen = new Set<string>();
  const options: MetadataOption[] = [];
  for (const [optionIndex, rawOption] of rawOptions.entries()) {
    if (
      !isObject(rawOption) ||
      typeof rawOption.value !== 'string' ||
      !/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(rawOption.value) ||
      typeof rawOption.labelFa !== 'string' ||
      rawOption.labelFa.trim() === ''
    ) {
      errors.push(
        `گزینه شماره ${optionIndex + 1} در فیلد شماره ${index + 1} معتبر نیست.`,
      );
      continue;
    }
    const normalizedValue = rawOption.value.toLowerCase();
    if (seen.has(normalizedValue)) {
      errors.push(`مقدار گزینه‌ها در فیلد شماره ${index + 1} تکراری است.`);
      continue;
    }
    seen.add(normalizedValue);
    options.push({ value: rawOption.value, labelFa: rawOption.labelFa.trim() });
  }
  if (options.length === 0)
    errors.push(`فیلد انتخابی شماره ${index + 1} گزینه معتبر ندارد.`);
  return options;
}

export function validateMetadataDefinitions(input: unknown): MetadataValidationResult {
  if (!Array.isArray(input)) {
    return {
      valid: false,
      definitions: null,
      errors: ['فهرست تعریف‌های فراداده معتبر نیست.'],
    };
  }

  const errors: string[] = [];
  const definitions: MetadataFieldDefinition[] = [];
  const seenKeys = new Set<string>();

  for (const [index, rawField] of input.entries()) {
    if (!isObject(rawField)) {
      errors.push(`تعریف شماره ${index + 1} معتبر نیست.`);
      continue;
    }
    const { key, labelFa, group, type } = rawField;
    if (typeof key !== 'string' || !/^[a-z][a-z0-9_]{0,63}$/.test(key)) {
      errors.push(`کلید تعریف شماره ${index + 1} باید شناسه انگلیسی معتبر باشد.`);
    } else {
      const normalizedKey = key.toLowerCase();
      if (RESERVED_KEYS.has(normalizedKey)) errors.push(`کلید رزروشده مجاز نیست: ${key}`);
      if (seenKeys.has(normalizedKey)) errors.push(`کلید تکراری است: ${key}`);
      seenKeys.add(normalizedKey);
    }
    if (typeof labelFa !== 'string' || labelFa.trim() === '') {
      errors.push(`برچسب فارسی فیلد شماره ${index + 1} الزامی است.`);
    }
    if (group !== 'document' && group !== 'user') {
      errors.push(`گروه فیلد شماره ${index + 1} معتبر نیست.`);
    }
    if (!isFieldType(type)) {
      errors.push(`نوع داده فیلد شماره ${index + 1} معتبر نیست.`);
    }
    if (
      typeof rawField.required !== 'boolean' ||
      typeof rawField.enabled !== 'boolean' ||
      typeof rawField.visibleInForm !== 'boolean'
    ) {
      errors.push(
        `تنظیم‌های فیلد شماره ${index + 1} باید مقدار درست یا نادرست داشته باشند.`,
      );
    }
    if (group === 'document' && typeof rawField.filterable !== 'boolean') {
      errors.push(`وضعیت فیلترپذیری فیلد سند شماره ${index + 1} مشخص نشده است.`);
    }
    if (group === 'user' && Object.hasOwn(rawField, 'filterable')) {
      errors.push(`فیلد کاربر شماره ${index + 1} نمی‌تواند فیلترپذیری سند داشته باشد.`);
    }
    if (!isFieldType(type) || (group !== 'document' && group !== 'user')) continue;

    const options = parseOptions(rawField.options, type, index, errors);
    if (
      typeof key === 'string' &&
      typeof labelFa === 'string' &&
      typeof rawField.required === 'boolean' &&
      typeof rawField.enabled === 'boolean' &&
      typeof rawField.visibleInForm === 'boolean'
    ) {
      const base = {
        key,
        labelFa: labelFa.trim(),
        type,
        ...(options ? { options } : {}),
        required: rawField.required,
        enabled: rawField.enabled,
        visibleInForm: rawField.visibleInForm,
      };
      if (group === 'document' && typeof rawField.filterable === 'boolean') {
        definitions.push({ ...base, group, filterable: rawField.filterable });
      } else if (group === 'user' && !Object.hasOwn(rawField, 'filterable')) {
        definitions.push({ ...base, group });
      }
    }
  }

  return errors.length > 0
    ? { valid: false, definitions: null, errors }
    : { valid: true, definitions, errors: [] };
}

export function isSuppliedValue(value: unknown): boolean {
  if (value === undefined || value === null) return false;
  if (typeof value === 'string') return value.trim().length > 0;
  if (Array.isArray(value)) return value.length > 0;
  return true;
}

export function validateMetadataValues(
  definitions: MetadataFieldDefinition[],
  values: MetadataValues,
  group: 'document' | 'user',
  options: { queryFilters?: boolean } = {},
): { key: string; message: string }[] {
  const errors: { key: string; message: string }[] = [];
  for (const field of definitions) {
    if (
      field.group !== group ||
      !field.enabled ||
      !field.visibleInForm ||
      (options.queryFilters && field.group === 'document' && !field.filterable)
    ) {
      continue;
    }

    const value = values[field.key];
    const supplied = isSuppliedValue(value);
    if (field.required && !options.queryFilters && !supplied) {
      errors.push({ key: field.key, message: `فیلد «${field.labelFa}» الزامی است.` });
      continue;
    }
    if (!supplied) continue;

    let valid = false;
    switch (field.type) {
      case 'text':
        valid = typeof value === 'string';
        break;
      case 'number':
        valid = typeof value === 'number' && Number.isFinite(value);
        break;
      case 'boolean':
        valid = typeof value === 'boolean';
        break;
      case 'select':
        valid =
          typeof value === 'string' &&
          (field.options ?? []).some((option) => option.value === value);
        break;
      case 'multi_select':
        valid =
          Array.isArray(value) &&
          value.every(
            (selected) =>
              typeof selected === 'string' &&
              (field.options ?? []).some((option) => option.value === selected),
          );
        break;
    }
    if (!valid)
      errors.push({
        key: field.key,
        message: `مقدار فیلد «${field.labelFa}» معتبر نیست.`,
      });
  }
  return errors;
}

export function filterActiveMetadataValues(
  definitions: MetadataFieldDefinition[],
  values: MetadataValues,
  group?: 'document' | 'user',
): MetadataValues {
  const activeKeys = new Set(
    definitions
      .filter(
        (field) =>
          field.enabled && field.visibleInForm && (!group || field.group === group),
      )
      .map(({ key }) => key),
  );
  return Object.fromEntries(
    Object.entries(values).filter(
      ([key, value]) => activeKeys.has(key) && isSuppliedValue(value),
    ),
  );
}

export function getDiscardedValueKeys(
  currentDefinitions: MetadataFieldDefinition[],
  nextDefinitions: MetadataFieldDefinition[],
  drafts: MetadataValues,
): string[] {
  const currentByKey = new Map(currentDefinitions.map((field) => [field.key, field]));
  const nextByKey = new Map(nextDefinitions.map((field) => [field.key, field]));
  return Object.keys(drafts).filter((key) => {
    if (!isSuppliedValue(drafts[key])) return false;
    const current = currentByKey.get(key);
    const next = nextByKey.get(key);
    if (!current) return false;
    if (
      !next ||
      !next.enabled ||
      !next.visibleInForm ||
      current.group !== next.group ||
      current.type !== next.type
    ) {
      return true;
    }
    if (next.type === 'select') {
      return !next.options?.some(({ value }) => value === drafts[key]);
    }
    if (next.type === 'multi_select') {
      const draftValue = drafts[key];
      if (!Array.isArray(draftValue)) return true;
      return draftValue.some(
        (selected) => !next.options?.some(({ value }) => value === selected),
      );
    }
    return false;
  });
}

export function createMetadataConfigService(storageProvider: () => StorageLike | null) {
  const listeners = new Set<MetadataConfigListener>();
  const drafts = new Map<
    string,
    { values: MetadataValues; onDiscard?: (keys: string[]) => void }
  >();
  let state: MetadataConfigState = {
    definitions: cloneDefinitions(DEFAULT_METADATA_FIELDS),
    loaded: false,
    persistenceAvailable: null,
  };

  const emit = () => listeners.forEach((listener) => listener());
  const setState = (nextState: MetadataConfigState) => {
    state = nextState;
    emit();
    return state;
  };
  const getStorageOrThrow = (): StorageLike => {
    const storage = storageProvider();
    if (!storage) throw new Error('storage unavailable');
    return storage;
  };
  const collectDrafts = (): MetadataValues => {
    const combined: MetadataValues = {};
    for (const { values } of drafts.values()) {
      for (const [key, value] of Object.entries(values)) {
        if (!Object.hasOwn(combined, key) || isSuppliedValue(value))
          combined[key] = value;
      }
    }
    return combined;
  };

  return {
    getSnapshot: (): MetadataConfigState => state,

    subscribe(listener: MetadataConfigListener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },

    load(): MetadataConfigState {
      try {
        const stored = getStorageOrThrow().getItem(METADATA_STORAGE_KEY);
        if (stored === null) {
          return setState({
            definitions: cloneDefinitions(DEFAULT_METADATA_FIELDS),
            loaded: true,
            persistenceAvailable: true,
          });
        }
        let parsed: unknown;
        try {
          parsed = JSON.parse(stored);
        } catch {
          parsed = null;
        }
        const validation = validateMetadataDefinitions(parsed);
        if (!validation.valid) {
          return setState({
            definitions: cloneDefinitions(DEFAULT_METADATA_FIELDS),
            loaded: true,
            persistenceAvailable: false,
            warning:
              'تعریف‌های ذخیره‌شده معتبر نبودند؛ پیش‌فرض‌ها فقط در حافظه بارگذاری شدند.',
          });
        }
        return setState({
          definitions: validation.definitions,
          loaded: true,
          persistenceAvailable: true,
        });
      } catch {
        return setState({
          definitions: cloneDefinitions(DEFAULT_METADATA_FIELDS),
          loaded: true,
          persistenceAvailable: false,
          warning: 'ذخیره‌سازی مرورگر در دسترس نیست؛ تغییرها موقت و فقط در حافظه هستند.',
        });
      }
    },

    save(input: unknown): MetadataConfigState {
      const validation = validateMetadataDefinitions(input);
      if (!validation.valid) throw new MetadataDefinitionError(validation.errors);
      try {
        getStorageOrThrow().setItem(
          METADATA_STORAGE_KEY,
          JSON.stringify(validation.definitions),
        );
        return setState({
          definitions: validation.definitions,
          loaded: true,
          persistenceAvailable: true,
        });
      } catch {
        return setState({
          definitions: validation.definitions,
          loaded: true,
          persistenceAvailable: false,
          warning: 'تغییرها در حافظه موقت نگه داشته شدند و در مرورگر ذخیره نشدند.',
        });
      }
    },

    restoreDefaults(): MetadataConfigState {
      const definitions = cloneDefinitions(DEFAULT_METADATA_FIELDS);
      try {
        getStorageOrThrow().setItem(METADATA_STORAGE_KEY, JSON.stringify(definitions));
        return setState({ definitions, loaded: true, persistenceAvailable: true });
      } catch {
        return setState({
          definitions,
          loaded: true,
          persistenceAvailable: false,
          warning: 'پیش‌فرض‌ها فقط در حافظه بازگردانده شدند و ذخیره نشدند.',
        });
      }
    },

    getDraftValues: collectDrafts,
    setDraftValues(
      owner: string,
      values: MetadataValues,
      onDiscard?: (keys: string[]) => void,
    ) {
      drafts.set(owner, { values: { ...values }, onDiscard });
    },
    removeDraftValues(owner: string) {
      drafts.delete(owner);
    },
    clearDraftValues() {
      drafts.clear();
    },
    discardDraftValues(keys: string[]) {
      for (const [owner, draft] of [...drafts]) {
        const ownedKeys = keys.filter((key) => Object.hasOwn(draft.values, key));
        if (ownedKeys.length === 0) continue;
        for (const key of ownedKeys) delete draft.values[key];
        draft.onDiscard?.(ownedKeys);
        drafts.set(owner, draft);
      }
    },
    getPotentiallyDiscardedKeys(nextDefinitions: MetadataFieldDefinition[]) {
      return [
        ...new Set(
          [...drafts.values()].flatMap(({ values }) =>
            getDiscardedValueKeys(state.definitions, nextDefinitions, values),
          ),
        ),
      ];
    },
  };
}

export class MetadataDefinitionError extends Error {
  constructor(readonly errors: string[]) {
    super(errors.join(' '));
    this.name = 'MetadataDefinitionError';
  }
}

function browserStorage(): StorageLike | null {
  try {
    return typeof window === 'undefined' ? null : window.localStorage;
  } catch {
    return null;
  }
}

export const metadataConfigService = createMetadataConfigService(browserStorage);
