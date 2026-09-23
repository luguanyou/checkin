import { expect, it } from 'vitest';
import { displayPoints, displayScore, validDecimal } from './score-utils';

it('preserves raw sub-cent points and formats exact large totals without binary floating-point loss', () => {
  expect(displayPoints('0.0001')).toBe('0.0001'); expect(displayPoints('1.2500')).toBe('1.25');
  expect(displayScore('999999999999999999.12')).toBe('999999999999999999.12');
  expect(displayScore('-1.2350')).toBe('-1.24'); expect(displayScore(null)).toBe('—');
  expect(validDecimal('0.00001')).toBe(false); expect(validDecimal('-0.0001')).toBe(true);
});
