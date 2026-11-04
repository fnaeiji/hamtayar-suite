import { render, screen, cleanup } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { ModeProvider } from '../../../src/app/ModeProvider';
import { QAPage } from '../../../src/features/qa/QAPage';
import { DEMO_METADATA_FIELDS } from '../../../src/config/demoProfile';
import { buildQuery } from '../../../src/features/qa/queryModel';
afterEach(cleanup);
it('shows only center, document type and a descriptive person access level', () => {
  render(
    <ModeProvider>
      <QAPage />
    </ModeProvider>,
  );
  expect(screen.getByLabelText('مرکز')).toBeVisible();
  expect(screen.getByLabelText('نوع سند')).toBeVisible();
  expect(screen.getByLabelText('سطح دسترسی فرد')).toBeVisible();
  expect(screen.queryByLabelText('واحد سازمانی')).not.toBeInTheDocument();
  expect(screen.queryByLabelText('تخصص کاربر')).not.toBeInTheDocument();
  const q = buildQuery(
    'سؤال',
    { person_access_level: 'کارشناس', access_scope: 'admin' },
    {
      center: 'مرکز الف',
      document_type: 'report',
      project: 'stale',
      department: 'engineering',
    },
    DEMO_METADATA_FIELDS,
  );
  expect(q.filters.conditions.map((c) => c.key)).toEqual(['center', 'document_type']);
  expect(q.user_metadata).toEqual({ person_access_level: 'کارشناس' });
});
