export type MetadataFieldType = 'text' | 'number' | 'boolean' | 'select' | 'multi_select';

export type MetadataOption = {
  value: string;
  labelFa: string;
};

type MetadataFieldBase = {
  /** Unique, stable English identifier used in UI models and API mappings. */
  key: string;
  labelFa: string;
  type: MetadataFieldType;
  options?: MetadataOption[];
  required: boolean;
  enabled: boolean;
  visibleInForm: boolean;
};

export type DocumentMetadataField = MetadataFieldBase & {
  group: 'document';
  filterable: boolean;
};

export type UserMetadataField = MetadataFieldBase & {
  group: 'user';
  filterable?: never;
};

export type MetadataFieldDefinition = DocumentMetadataField | UserMetadataField;

export type MetadataFieldValue = string | number | boolean | string[];
export type MetadataValues = Record<string, MetadataFieldValue>;
