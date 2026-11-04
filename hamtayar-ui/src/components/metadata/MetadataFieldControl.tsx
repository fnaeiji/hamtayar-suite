import type { MetadataFieldDefinition, MetadataFieldValue } from '../../types/metadata';

type MetadataFieldControlProps = {
  field: MetadataFieldDefinition;
  value: MetadataFieldValue | undefined;
  onChange: (key: string, value: MetadataFieldValue) => void;
  queryFilter?: boolean;
  idPrefix?: string;
};

export function MetadataFieldControl({
  field,
  value,
  onChange,
  queryFilter = false,
  idPrefix = 'metadata',
}: MetadataFieldControlProps) {
  const id = `${idPrefix}-${field.key}`;
  const required = queryFilter ? false : field.required;

  if (field.type === 'boolean') {
    return (
      <div className="metadata-field">
        <label htmlFor={id}>
          {field.labelFa}
          {required && <span aria-hidden="true"> *</span>}
        </label>
        <select
          id={id}
          aria-required={required}
          required={required}
          value={typeof value === 'boolean' ? String(value) : ''}
          onChange={(event) =>
            onChange(
              field.key,
              event.target.value === '' ? '' : event.target.value === 'true',
            )
          }
        >
          <option value="">تعیین نشده</option>
          <option value="true">بله</option>
          <option value="false">خیر</option>
        </select>
      </div>
    );
  }

  if (field.type === 'select' || field.type === 'multi_select') {
    const multiple = field.type === 'multi_select';
    const selected = multiple
      ? Array.isArray(value)
        ? value
        : []
      : typeof value === 'string'
        ? value
        : '';
    return (
      <div className="metadata-field">
        <label htmlFor={id}>
          {field.labelFa}
          {required && <span aria-hidden="true"> *</span>}
        </label>
        <select
          aria-required={required}
          id={id}
          multiple={multiple}
          onChange={(event) => {
            if (multiple) {
              onChange(
                field.key,
                Array.from(event.currentTarget.selectedOptions, (option) => option.value),
              );
            } else {
              onChange(field.key, event.target.value);
            }
          }}
          required={required}
          value={selected}
        >
          {!multiple && <option value="">انتخاب کنید</option>}
          {(field.options ?? []).map((option) => (
            <option key={option.value} value={option.value}>
              {option.labelFa}
            </option>
          ))}
        </select>
      </div>
    );
  }

  const number = field.type === 'number';
  const inputValue = typeof value === 'string' || typeof value === 'number' ? value : '';
  return (
    <div className="metadata-field">
      <label htmlFor={id}>
        {field.labelFa}
        {required && <span aria-hidden="true"> *</span>}
      </label>
      <input
        aria-required={required}
        id={id}
        inputMode={number ? 'decimal' : undefined}
        onChange={(event) => {
          const nextValue = event.target.value;
          onChange(field.key, number && nextValue !== '' ? Number(nextValue) : nextValue);
        }}
        required={required}
        type={number ? 'number' : 'text'}
        value={inputValue}
      />
    </div>
  );
}
