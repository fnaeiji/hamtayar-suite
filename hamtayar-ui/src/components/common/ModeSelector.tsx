import { useMode } from '../../app/ModeProvider';

export function ModeSelector() {
  const { mode, canSwitchMode, switchMode } = useMode();

  return (
    <label className="mode-selector">
      <span>حالت اجرا</span>
      <select
        aria-label="حالت اجرا"
        disabled={!canSwitchMode}
        onChange={(event) => switchMode(event.target.value as 'demo' | 'api')}
        value={mode}
      >
        <option value="demo">نمایشی</option>
        <option value="api">API</option>
      </select>
      {!canSwitchMode && <span className="mode-selector__hint">تا پایان عملیات قفل است</span>}
    </label>
  );
}
