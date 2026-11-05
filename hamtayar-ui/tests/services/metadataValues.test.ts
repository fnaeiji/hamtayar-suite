import { expect, it } from 'vitest';
import { DEMO_METADATA_FIELDS } from '../../src/config/demoProfile';
import {
  filterActiveMetadataValues,
  validateMetadataValues,
} from '../../src/services/metadata/values';
it('requires current document fields, rejects invalid classifications and omits obsolete keys', () => {
  expect(validateMetadataValues(DEMO_METADATA_FIELDS, {}, 'document')).toHaveLength(2);
  expect(
    validateMetadataValues(
      DEMO_METADATA_FIELDS,
      { center: 'الف', document_type: 'confidential' },
      'document',
    ),
  ).toHaveLength(0);
  expect(
    validateMetadataValues(
      DEMO_METADATA_FIELDS,
      { center: 'الف', document_type: 'guide' },
      'document',
    ),
  ).toHaveLength(1);
  expect(
    filterActiveMetadataValues(
      DEMO_METADATA_FIELDS,
      { center: 'الف', document_type: 'normal', department: 'stale' },
      'document',
    ),
  ).toEqual({ center: 'الف', document_type: 'normal' });
  expect(
    validateMetadataValues(DEMO_METADATA_FIELDS, {}, 'document', {
      requireFields: false,
    }),
  ).toHaveLength(0);
});
