import { useId } from 'react';
import type {
  MetadataFieldDefinition,
  MetadataFieldValue,
  MetadataValues,
} from '../../types/metadata';
import { MetadataFieldControl } from './MetadataFieldControl';

type MetadataFieldsProps = {
  definitions: MetadataFieldDefinition[];
  values: MetadataValues;
  onChange: (key: string, value: MetadataFieldValue) => void;
  group?: 'document' | 'user';
  queryFilters?: boolean;
};

export function MetadataFields({
  definitions,
  values,
  onChange,
  group,
  queryFilters = false,
}: MetadataFieldsProps) {
  const ownerId = useId();
  const visibleFields = definitions.filter(
    (field) =>
      field.enabled &&
      field.visibleInForm &&
      (!group || field.group === group) &&
      (!queryFilters || (field.group === 'document' && field.filterable)),
  );

  return (
    <div className="metadata-fields">
      {visibleFields.map((field) => (
        <MetadataFieldControl
          field={field}
          idPrefix={`metadata-${ownerId}`}
          key={field.key}
          onChange={onChange}
          queryFilter={queryFilters}
          value={values[field.key]}
        />
      ))}
      {visibleFields.length === 0 && (
        <p className="metadata-fields__empty">فیلدی برای نمایش وجود ندارد.</p>
      )}
    </div>
  );
}
