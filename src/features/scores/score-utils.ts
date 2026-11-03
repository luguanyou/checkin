import type { ScoreCategory } from '../../api/scores-types';
export const categories: { key: ScoreCategory; label: string }[] = [
  { key: 'HOMEWORK', label: '作业' }, { key: 'LAB', label: '上机实验表现' },
  { key: 'CLASSROOM', label: '课堂表现' }, { key: 'OTHER', label: '其他' },
];
export const scoreStatus = { READY: '已汇总', RULES_PENDING: '规则待配置', RECORDS_PENDING: '待评完整' };
export function decimal(value: string) { return value.trim() === '' ? null : value.trim(); }
export function displayPoints(value: string | null | undefined) {
  if (value == null) return '—';
  const [whole, fraction = ''] = value.split('.'); const digits = fraction.replace(/0+$/, '');
  return digits ? `${whole}.${digits}` : whole;
}
export function displayScore(value: string | null | undefined) {
  if (value == null) return '—';
  const rounded = roundPoints(value);
  return rounded.includes('.') ? rounded : `${rounded}.0`;
}
export function roundPoints(value: string) {
  if (!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/.test(value)) return value;
  const negative = value.startsWith('-'); const [whole, fraction = ''] = value.replace(/^[+-]/, '').split('.');
  const tenths = BigInt(whole || '0') * 10n + BigInt(fraction[0] || '0') + (Number(fraction[1] ?? '0') >= 5 ? 1n : 0n);
  return `${negative && tenths !== 0n ? '-' : ''}${tenths / 10n}${tenths % 10n ? `.${tenths % 10n}` : ''}`;
}
export function validDecimal(value: string, nonnegative = false) {
  return value.trim() === '' || (/^[+-]?(?:\d+(?:\.\d{0,4})?|\.\d{1,4})$/.test(value.trim()) && Number.isFinite(Number(value)) && (!nonnegative || Number(value) >= 0));
}
