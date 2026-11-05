import type { MetadataFieldDefinition, MetadataValues } from '../../types/metadata';

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
