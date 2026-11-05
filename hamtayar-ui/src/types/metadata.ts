type MetadataOption = { value: string; labelFa: string };
type FieldBase = { labelFa: string; required: boolean };
export type MetadataFieldDefinition =
  | (FieldBase & {
      key: 'center';
      group: 'document';
      type: 'text' | 'select';
      options?: MetadataOption[];
    })
  | (FieldBase & {
      key: 'document_type';
      group: 'document';
      type: 'select';
      options: MetadataOption[];
    })
  | (FieldBase & {
      key: 'person_access_level';
      group: 'user';
      type: 'select';
      options: MetadataOption[];
    });
export type MetadataKey = MetadataFieldDefinition['key'];
export type MetadataValues = Partial<Record<MetadataKey, string>>;
export type DocumentFilters = {
  operator: 'and';
  conditions: { key: 'center' | 'document_type'; operator: 'eq'; value: string }[];
};
