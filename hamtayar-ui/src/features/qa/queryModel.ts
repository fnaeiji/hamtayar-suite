import type {
  MetadataFieldDefinition,
  MetadataValues,
  MetadataFieldValue,
} from '../../types/metadata';
import {
  filterActiveMetadataValues,
  validateMetadataValues,
} from '../../services/metadata/metadataConfigService';
export type QueryModel = {
  question: string;
  user_metadata: MetadataValues;
  filters: {
    operator: 'and';
    conditions: { key: string; operator: 'eq' | 'any_of'; value: MetadataFieldValue }[];
  };
};
export function buildQuery(
  question: string,
  user: MetadataValues,
  filters: MetadataValues,
  definitions: MetadataFieldDefinition[],
): QueryModel {
  const fields = definitions.filter((f) => f.group === 'document' && f.filterable);
  const errors = [
    ...validateMetadataValues(definitions, user, 'user'),
    ...validateMetadataValues(fields, filters, 'document', { queryFilters: true }),
  ];
  if (errors.length) throw new Error(errors.map((e) => e.message).join(' '));
  const active = filterActiveMetadataValues(fields, filters, 'document');
  return {
    question: question.trim(),
    user_metadata: filterActiveMetadataValues(definitions, user, 'user'),
    filters: {
      operator: 'and',
      conditions: Object.entries(active).map(([key, value]) => ({
        key,
        operator: Array.isArray(value) && value.length > 1 ? 'any_of' : 'eq',
        value: Array.isArray(value) && value.length === 1 ? value[0] : value,
      })),
    },
  };
}
