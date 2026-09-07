import { describe, expect, it } from 'vitest';
import { createRosterTemplate, validateRosterFile } from './import-utils';

describe('roster import utilities', () => {
  it('accepts supported files within 10 MiB', () => {
    expect(validateRosterFile(new File(['x'], '名单.CSV'))).toBe('');
    expect(validateRosterFile(new File(['x'], '名单.xlsx'))).toBe('');
  });

  it('rejects unsupported or oversized files', () => {
    expect(validateRosterFile(new File(['x'], '名单.txt'))).toBe('仅支持 .csv、.xls 或 .xlsx 文件');
    const file = new File(['x'], '名单.csv');
    Object.defineProperty(file, 'size', { value: 10 * 1024 * 1024 + 1 });
    expect(validateRosterFile(file)).toBe('名单文件不能超过 10 MiB');
  });

  it('creates a UTF-8 BOM CSV template', async () => {
    const blob = createRosterTemplate();
    const bytes = new Uint8Array(await blob.arrayBuffer());
    expect([...bytes.slice(0, 3)]).toEqual([0xef, 0xbb, 0xbf]);
    expect(await blob.text()).toContain('学号,姓名,性别,班级,专业');
  });
});
