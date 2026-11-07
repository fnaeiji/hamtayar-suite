import type {
  DocumentFilters,
  MetadataFieldDefinition,
  MetadataValues,
} from '../../types/metadata';
export function validateMetadataValues(
  definitions: MetadataFieldDefinition[],
  values: MetadataValues,
  group: 'document' | 'user',
  options: { requireFields?: boolean } = {},
): { key: string; message: string }[] {
  return definitions
    .filter((field) => field.group === group)
    .flatMap((field) => {
      const value = values[field.key];
      if (value === undefined || value === '')
        return field.required && options.requireFields !== false
          ? [{ key: field.key, message: `فیلد «${field.labelFa}» الزامی است.` }]
          : [];
      if (
        typeof value !== 'string' ||
        !value.trim() ||
        (field.type === 'select' &&
          !field.options?.some((option) => option.value === value.trim()))
      )
        return [{ key: field.key, message: `مقدار فیلد «${field.labelFa}» معتبر نیست.` }];
      return [];
    });
}
export function filterActiveMetadataValues(
  definitions: MetadataFieldDefinition[],
  values: MetadataValues,
  group: 'document' | 'user',
): MetadataValues {
  return Object.fromEntries(
    definitions
      .filter((field) => field.group === group)
      .flatMap(({ key }) => {
        const value = values[key];
        return typeof value === 'string' && value.trim() ? [[key, value.trim()]] : [];
      }),
  );
}
export function buildDocumentFilters(
  definitions: MetadataFieldDefinition[],
  values: MetadataValues,
): DocumentFilters {
  const errors = validateMetadataValues(definitions, values, 'document', {
    requireFields: false,
  });
  if (errors.length) throw new Error(errors.map((error) => error.message).join(' '));
  return {
    operator: 'and',
    conditions: definitions
      .filter((field) => field.group === 'document')
      .flatMap(({ key }) => {
        const value = values[key]?.trim();
        return value ? [{ key, operator: 'eq' as const, value }] : [];
      }),
  };
}
