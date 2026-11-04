import type { MetadataFieldDefinition } from '../types/metadata';

// Current presentation profile: exactly two document fields and one descriptive user field.
// This UI value is never an authorization grant or an API access scope.
export const DEMO_METADATA_FIELDS: MetadataFieldDefinition[] = [
  {
    key: 'center',
    labelFa: 'مرکز',
    group: 'document',
    type: 'text',
    required: false,
    enabled: true,
    visibleInForm: true,
    filterable: true,
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
    key: 'person_access_level',
    labelFa: 'سطح دسترسی فرد',
    group: 'user',
    type: 'text',
    required: false,
    enabled: true,
    visibleInForm: true,
  },
];
