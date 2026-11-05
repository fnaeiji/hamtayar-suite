import type {
  DocumentFilters,
  MetadataFieldDefinition,
  MetadataValues,
} from '../../types/metadata';
import {
  buildDocumentFilters,
  filterActiveMetadataValues,
  validateMetadataValues,
} from '../../services/metadata/values';
export type QueryModel = {
  question: string;
  user_metadata: MetadataValues;
  filters: DocumentFilters;
};
export function buildQuery(
  question: string,
  user: MetadataValues,
  filters: MetadataValues,
  definitions: MetadataFieldDefinition[],
): QueryModel {
  const errors = validateMetadataValues(definitions, user, 'user');
  if (errors.length) throw new Error(errors.map((error) => error.message).join(' '));
  return {
    question: question.trim(),
    user_metadata: filterActiveMetadataValues(definitions, user, 'user'),
    filters: buildDocumentFilters(definitions, filters),
  };
}
