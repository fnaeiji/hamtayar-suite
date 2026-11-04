import type { ReactNode } from 'react';

export type StatusTone = 'info' | 'success' | 'warning' | 'error';

const cues: Record<StatusTone, string> = {
  info: 'اطلاع',
  success: 'موفق',
  warning: 'توجه',
  error: 'خطا',
};

type StatusMessageProps = {
  tone?: StatusTone;
  title?: string;
  children: ReactNode;
};

export function StatusMessage({ tone = 'info', title, children }: StatusMessageProps) {
  return (
    <div
      className={`status-message status-message--${tone}`}
      role={tone === 'error' ? 'alert' : 'status'}
      aria-live={tone === 'error' ? 'assertive' : 'polite'}
    >
      <span className="status-message__cue" aria-hidden="true">
        {cues[tone]}
      </span>
      <div>
        {title && <strong>{title}</strong>}
        <div>{children}</div>
      </div>
    </div>
  );
}
