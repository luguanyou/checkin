const MAX_FILE_SIZE = 10 * 1024 * 1024;
const SUPPORTED_EXTENSIONS = ['.csv', '.xls', '.xlsx'];

export function validateRosterFile(file: File) {
  const name = file.name.toLowerCase();
  if (!SUPPORTED_EXTENSIONS.some((extension) => name.endsWith(extension))) {
    return '仅支持 .csv、.xls 或 .xlsx 文件';
  }
  if (file.size > MAX_FILE_SIZE) return '名单文件不能超过 10 MiB';
  return '';
}

export function createRosterTemplate() {
  const content = '\uFEFF学号,姓名,性别,班级,专业\r\n20260001,张敏,女,2026级1班,工业设计\r\n';
  return new Blob([content], { type: 'text/csv;charset=utf-8' });
}

export function previewStatusLabel(status: string) {
  return ({ valid: '有效', error: '错误', duplicate: '重复' } as Record<string, string>)[status] ?? status;
}
