import { useId } from 'react';
import type {
  MetadataFieldDefinition,
  MetadataKey,
  MetadataValues,
} from '../../types/metadata';
type Props = {
  definitions: MetadataFieldDefinition[];
  values: MetadataValues;
  group: 'document' | 'user';
  onChange: (key: MetadataKey, value: string) => void;
};
export function MetadataFields({ definitions, values, group, onChange }: Props) {
  const owner = useId();
  return (
    <div className="metadata-fields">
      {definitions
        .filter((field) => field.group === group)
        .map((field) => {
          const id = `metadata-${owner}-${field.key}`;
          return (
            <div className="metadata-field" key={field.key}>
              <label htmlFor={id}>
                {field.labelFa}
                {field.required && <span aria-hidden="true"> *</span>}
              </label>
              {field.type === 'select' ? (
                <select
                  id={id}
                  required={field.required}
                  value={values[field.key] ?? ''}
                  onChange={(e) => onChange(field.key, e.target.value)}
                >
                  <option value="">انتخاب کنید</option>
                  {field.options?.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.labelFa}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  id={id}
                  required={field.required}
                  value={values[field.key] ?? ''}
                  onChange={(e) => onChange(field.key, e.target.value)}
                />
              )}
            </div>
          );
        })}
    </div>
  );
}
