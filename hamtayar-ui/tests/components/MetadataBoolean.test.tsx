import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it, vi } from 'vitest';
import { MetadataFieldControl } from '../../src/components/metadata/MetadataFieldControl';
afterEach(cleanup);
it('lets the user explicitly select false and reset a boolean filter to unset', async () => {
  const change = vi.fn();
  const user = userEvent.setup();
  render(
    <MetadataFieldControl
      field={{
        key: 'flag',
        labelFa: 'فعال',
        group: 'document',
        type: 'boolean',
        enabled: true,
        visibleInForm: true,
        required: true,
        filterable: true,
      }}
      queryFilter
      value={undefined}
      onChange={change}
    />,
  );
  const select = screen.getByLabelText('فعال');
  expect(select).not.toBeRequired();
  await user.selectOptions(select, 'false');
  expect(change).toHaveBeenLastCalledWith('flag', false);
  await user.selectOptions(select, '');
  expect(change).toHaveBeenLastCalledWith('flag', '');
});
