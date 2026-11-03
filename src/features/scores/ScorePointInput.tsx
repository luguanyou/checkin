import { useState } from 'react';
import { roundPoints } from './score-utils';

/** Keep an empty editing value separate from the zero shown for pending scores. */
export function ScorePointInput({ value, onChange, label, disabled }: { value: string; onChange(value: string): void; label: string; disabled: boolean }) {
  const [focused, setFocused] = useState(false);
  return <input className="scores-point" type="number" step="1" aria-label={label} disabled={disabled}
    value={value === '' && !focused ? '0' : value} placeholder="0"
    onFocus={(event) => { setFocused(true); if (Number(value) === 0) event.currentTarget.select(); }}
    onChange={(event) => onChange(event.target.value)}
    onBlur={() => { setFocused(false); if (value !== '') onChange(roundPoints(value)); }}
    onKeyDown={(event) => {
      if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') return;
      event.preventDefault();
      const next = Number(value || 0) + (event.key === 'ArrowUp' ? 1 : -1);
      if (Number.isFinite(next)) onChange(roundPoints(String(next)));
    }}
  />;
}
