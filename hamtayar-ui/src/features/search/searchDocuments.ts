import type { PhraseSearchRequest } from './searchRequest';
import type { LocalDocument } from '../../services/documentCatalog';
export type PhraseResult = {
  document: LocalDocument;
  before: string;
  match: string;
  after: string;
};
export function searchDocuments(
  documents: LocalDocument[],
  request: PhraseSearchRequest,
): PhraseResult[] {
  const needle = request.phrase;
  if (!needle) return [];
  const expression = new RegExp(needle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'iu');
  return documents.flatMap((document) => {
    if (
      document.text === undefined ||
      !request.filters.conditions.every(
        (condition) =>
          (condition.key === 'center' ? document.center : document.classification) ===
          condition.value,
      )
    )
      return [];
    const match = expression.exec(document.text);
    if (!match) return [];
    return [
      {
        document,
        before: document.text.slice(Math.max(0, match.index - 65), match.index),
        match: match[0],
        after: document.text.slice(
          match.index + match[0].length,
          match.index + match[0].length + 100,
        ),
      },
    ];
  });
}
