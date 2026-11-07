import { useState } from 'react';
import type { OperationRecord } from '../../types/operations';
/** Diagnostics are structured client data; never pass raw headers or service error bodies. */
function sanitizeDetails(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sanitizeDetails);
  if (value && typeof value === 'object')
    return Object.fromEntries(
      Object.entries(value)
        .filter(
          ([key]) =>
            !/(token|password|secret|authorization|cookie|stack|traceback|api.?key)/i.test(
              key,
            ),
        )
        .map(([key, item]) => [key, sanitizeDetails(item)]),
    );
  return value;
}
export function TestDetailsPanel({
  intended,
  transmitted,
  operation,
}: {
  intended?: unknown;
  transmitted?: unknown;
  operation?: OperationRecord;
}) {
  const [open, setOpen] = useState(false);
  const details = {
    mode: operation?.mode,
    status: operation?.status,
    intended,
    transmitted: transmitted ?? 'ارسال نشده',
    response: operation?.result,
    diagnostic: operation?.diagnostic,
    elapsedMs: operation ? operation.updatedAt - operation.startedAt : undefined,
  };
  return (
    <details className="test-details" onToggle={(e) => setOpen(e.currentTarget.open)}>
      <summary>جزئیات تست</summary>
      {open && <pre dir="ltr">{JSON.stringify(sanitizeDetails(details), null, 2)}</pre>}
    </details>
  );
}
