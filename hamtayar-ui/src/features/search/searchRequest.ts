import { questionMetadataDefinitions } from '../../config/demoProfile';
import { buildDocumentFilters } from '../../services/metadata/values';
import type { DocumentFilters } from '../../types/metadata';
export type PhraseSearchRequest = {
  phrase: string;
  match: { mode: 'literal'; case_sensitive: false };
  filters: DocumentFilters;
};
export function buildPhraseSearchRequest(
  phrase: string,
  center: string,
  classification: string,
  centers: string[],
): PhraseSearchRequest {
  phrase = phrase.trim();
  if (!phrase) throw new Error('عبارت موردنظر را وارد کنید.');
  if (phrase.length > 512) throw new Error('عبارت جستجو باید حداکثر ۵۱۲ نویسه باشد.');
  return {
    phrase,
    match: { mode: 'literal', case_sensitive: false },
    filters: buildDocumentFilters(questionMetadataDefinitions(centers), {
      center,
      document_type: classification,
    }),
  };
}
