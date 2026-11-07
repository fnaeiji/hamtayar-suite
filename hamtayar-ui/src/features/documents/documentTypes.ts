import type { MetadataValues } from '../../types/metadata';
export type DocumentDraft = {
  id: string;
  file: File;
  version: string;
  processingProfile: string;
  customMetadata: MetadataValues;
};
export type DocumentResult = {
  provenance: 'fixture' | 'service';
  label: string;
  status: 'completed';
  message: string;
  chunksIndexed?: number | null;
  sourceId?: string;
  version?: string;
  requestId?: string;
};
