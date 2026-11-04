export type ConnectionStatus = 'connected' | 'unavailable' | 'unknown';

const labels: Record<ConnectionStatus, string> = {
  connected: 'در دسترس',
  unavailable: 'در دسترس نیست',
  unknown: 'بررسی نشده',
};

const cues: Record<ConnectionStatus, string> = {
  connected: '●',
  unavailable: '×',
  unknown: '?',
};

export function ConnectionBadge({
  status,
  service,
}: {
  status: ConnectionStatus;
  service: string;
}) {
  return (
    <span className={`connection-badge connection-badge--${status}`}>
      <span className="connection-badge__cue" aria-hidden="true">
        {cues[status]}
      </span>
      <span>
        {service}: {labels[status]}
      </span>
    </span>
  );
}
