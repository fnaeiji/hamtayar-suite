import { DEMO_METADATA_FIELDS } from '../../config/demoProfile';
/** Fixed presentation profile; previous browser definitions cannot add hidden fields. */
export function useMetadata() {
  return { definitions: DEMO_METADATA_FIELDS, warning: undefined as string | undefined };
}
