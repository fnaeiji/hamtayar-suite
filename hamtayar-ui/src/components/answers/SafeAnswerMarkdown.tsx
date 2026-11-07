import ReactMarkdown from 'react-markdown';
export function SafeAnswerMarkdown({ text }: { text: string }) {
  return (
    <div className="answer-markdown">
      <ReactMarkdown skipHtml>{text}</ReactMarkdown>
    </div>
  );
}
