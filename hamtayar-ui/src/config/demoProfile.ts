import type { MetadataFieldDefinition } from '../types/metadata';

// Current presentation profile: exactly two document fields and one descriptive user field.
// This UI value is never an authorization grant or an API access scope.
export const CLASSIFICATION_OPTIONS = [
  { value: 'normal', labelFa: 'عادی' },
  { value: 'confidential', labelFa: 'محرمانه' },
  { value: 'highly_confidential', labelFa: 'خیلی محرمانه' },
];

export const DEMO_METADATA_FIELDS: MetadataFieldDefinition[] = [
  {
    key: 'center',
    labelFa: 'مرکز',
    group: 'document',
    type: 'text',
    required: true,
  },
  {
    key: 'document_type',
    labelFa: 'نوع سند',
    group: 'document',
    type: 'select',
    options: CLASSIFICATION_OPTIONS,
    required: true,
  },
  {
    key: 'person_access_level',
    labelFa: 'سطح دسترسی',
    group: 'user',
    type: 'select',
    options: CLASSIFICATION_OPTIONS,
    required: false,
  },
];

export function questionMetadataDefinitions(
  centers: string[],
): MetadataFieldDefinition[] {
  return DEMO_METADATA_FIELDS.map((field) =>
    field.key === 'center'
      ? {
          ...field,
          type: 'select' as const,
          required: false,
          options: centers.map((center) => ({ value: center, labelFa: center })),
        }
      : { ...field, required: false },
  );
}
