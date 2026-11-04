import { beforeEach, describe, expect, it } from 'vitest';
import {
  createMetadataConfigService,
  DEFAULT_METADATA_FIELDS,
  filterActiveMetadataValues,
  isSuppliedValue,
  validateMetadataDefinitions,
  validateMetadataValues,
  type StorageLike,
} from '../../../src/services/metadata/metadataConfigService';
import type {
  MetadataFieldDefinition,
  MetadataFieldType,
} from '../../../src/types/metadata';

function memoryStorage(
  seed: Record<string, string> = {},
): StorageLike & { data: Record<string, string> } {
  const data = { ...seed };
  return {
    data,
    getItem(key) {
      return data[key] ?? null;
    },
    setItem(key, value) {
      data[key] = value;
    },
    removeItem(key) {
      delete data[key];
    },
  };
}

function documentField(
  overrides: Partial<MetadataFieldDefinition> = {},
): MetadataFieldDefinition {
  return {
    key: 'budget',
    labelFa: 'بودجه',
    group: 'document',
    type: 'number',
    required: true,
    enabled: true,
    visibleInForm: true,
    filterable: true,
    ...overrides,
  } as MetadataFieldDefinition;
}

describe('metadata configuration service', () => {
  beforeEach(() => window.localStorage.clear());

  it('seeds exactly the seven documented defaults with separate Persian labels and English values', () => {
    const keys = DEFAULT_METADATA_FIELDS.map(({ key }) => key);
    expect(keys).toEqual([
      'department',
      'project',
      'document_type',
      'tags',
      'display_name',
      'expertise',
      'answer_language',
    ]);
    expect(new Set(keys).size).toBe(7);
    expect(
      DEFAULT_METADATA_FIELDS.every(({ labelFa }) => labelFa.trim().length > 0),
    ).toBe(true);
    expect(
      DEFAULT_METADATA_FIELDS.find(({ key }) => key === 'department')?.options?.map(
        ({ value }) => value,
      ),
    ).toEqual(['engineering', 'hr', 'finance']);
    expect(
      DEFAULT_METADATA_FIELDS.find(({ key }) => key === 'answer_language')?.options?.map(
        ({ value }) => value,
      ),
    ).toEqual(['fa', 'en']);
  });

  it('rejects duplicate, malformed, and reserved keys without changing valid definitions', () => {
    const duplicate = [documentField(), documentField({ labelFa: 'مبلغ' })];
    const malformed = [documentField({ key: 'Bad Key' })];
    const reserved = [documentField({ key: 'tenant_id' })];
    const invalidType = [documentField({ type: 'date' as MetadataFieldType })];

    expect(validateMetadataDefinitions(duplicate).valid).toBe(false);
    expect(validateMetadataDefinitions(malformed).valid).toBe(false);
    expect(validateMetadataDefinitions(reserved).valid).toBe(false);
    expect(validateMetadataDefinitions(invalidType).valid).toBe(false);
    expect(validateMetadataDefinitions(DEFAULT_METADATA_FIELDS).valid).toBe(true);
  });

  it('validates selection options and rejects duplicates, malformed values, or missing choices', () => {
    const selectField = documentField({
      type: 'select',
      options: [{ value: 'approved', labelFa: 'تأییدشده' }],
    });
    expect(validateMetadataDefinitions([selectField]).valid).toBe(true);
    expect(
      validateMetadataDefinitions([
        {
          ...selectField,
          options: [
            { value: 'same', labelFa: 'گزینه یک' },
            { value: 'same', labelFa: 'گزینه دو' },
          ],
        },
      ]).valid,
    ).toBe(false);
    expect(validateMetadataDefinitions([{ ...selectField, options: [] }]).valid).toBe(
      false,
    );
    expect(
      validateMetadataDefinitions([
        { ...selectField, options: [{ value: 'دو مقدار', labelFa: 'نامعتبر' }] },
      ]).valid,
    ).toBe(false);
  });

  it('treats numeric zero and boolean false as supplied required values', () => {
    expect(isSuppliedValue(0)).toBe(true);
    expect(isSuppliedValue(false)).toBe(true);
    expect(isSuppliedValue('')).toBe(false);
    const fields = [
      documentField(),
      documentField({
        key: 'published',
        labelFa: 'منتشرشده',
        type: 'boolean',
      }),
    ];
    expect(
      validateMetadataValues(fields, { budget: 0, published: false }, 'document'),
    ).toEqual([]);
    expect(
      validateMetadataValues(fields, { budget: '0', published: 'false' }, 'document'),
    ).toHaveLength(2);
    expect(validateMetadataValues(fields, {}, 'document')).toHaveLength(2);
    expect(
      validateMetadataValues(fields, {}, 'document', { queryFilters: true }),
    ).toEqual([]);
  });

  it('excludes values from disabled or hidden fields but preserves zero and false', () => {
    const fields = [
      documentField(),
      documentField({ key: 'hidden', labelFa: 'پنهان', visibleInForm: false }),
      documentField({ key: 'disabled', labelFa: 'غیرفعال', enabled: false }),
      documentField({ key: 'flag', labelFa: 'وضعیت', type: 'boolean' }),
    ];
    expect(
      filterActiveMetadataValues(fields, {
        budget: 0,
        hidden: 'stale',
        disabled: 'stale',
        flag: false,
      }),
    ).toEqual({ budget: 0, flag: false });
  });

  it('persists and reloads only under the namespaced metadata key', () => {
    const storage = memoryStorage({ unrelated: 'preserve' });
    const first = createMetadataConfigService(() => storage);
    first.save([...DEFAULT_METADATA_FIELDS, documentField()]);

    const restarted = createMetadataConfigService(() => storage);
    expect(restarted.load().definitions.map(({ key }) => key)).toContain('budget');
    expect(storage.data.unrelated).toBe('preserve');
    expect(Object.keys(storage.data)).toEqual([
      'unrelated',
      'hamtayar-demo-ui.metadata.v1',
    ]);
  });

  it('restores defaults by changing only the namespaced metadata key', () => {
    const storage = memoryStorage({
      unrelated: 'keep me',
      'hamtayar-demo-ui.metadata.v1': JSON.stringify([documentField()]),
    });
    const service = createMetadataConfigService(() => storage);
    service.restoreDefaults();

    expect(storage.data.unrelated).toBe('keep me');
    expect(JSON.parse(storage.data['hamtayar-demo-ui.metadata.v1'])).toHaveLength(7);
    expect(Object.keys(storage.data)).toHaveLength(2);
  });

  it('falls back to usable in-memory defaults and reports persistence failures', () => {
    const failingStorage: StorageLike = {
      getItem() {
        throw new Error('storage unavailable');
      },
      setItem() {
        throw new Error('storage unavailable');
      },
      removeItem() {
        throw new Error('storage unavailable');
      },
    };
    const service = createMetadataConfigService(() => failingStorage);
    expect(service.load().persistenceAvailable).toBe(false);
    expect(service.getSnapshot().warning).toBeTruthy();

    const updated = service.save([...DEFAULT_METADATA_FIELDS, documentField()]);
    expect(updated.definitions.map(({ key }) => key)).toContain('budget');
    expect(updated.persistenceAvailable).toBe(false);
  });
});
