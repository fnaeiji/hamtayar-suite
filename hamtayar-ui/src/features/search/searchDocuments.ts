import type { LocalDocument } from '../../services/documentCatalog';
export type PhraseResult = {
  document: LocalDocument;
  before: string;
  match: string;
  after: string;
};
export function searchDocuments(
  documents: LocalDocument[],
  phrase: string,
  center: string,
  classification: string,
): PhraseResult[] {
  const needle = phrase.trim();
  if (!needle) return [];
  const expression = new RegExp(needle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'iu');
  return documents.flatMap((document) => {
    if (
      document.text === undefined ||
      (center && document.center !== center) ||
      (classification && document.classification !== classification)
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
