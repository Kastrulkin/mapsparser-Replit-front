export type TableInput = {
  columns: string[];
  rows: Array<Record<string, string>>;
};

export type TableParseResult = {
  table: TableInput | null;
  error: string;
};

type TableLocale = 'ru' | 'en';

const tableCopy = (locale: TableLocale) => locale === 'ru' ? {
  unclosedQuote: 'Закройте кавычку в таблице.', emptyHeader: 'В первой строке укажите непустые названия столбцов.', headerLength: (limit: number) => `Название столбца должно быть не длиннее ${limit} символов.`, columnLimit: (limit: number) => `Можно проверить до ${limit} столбцов.`, uniqueHeaders: 'Названия столбцов должны быть уникальны.', rowLimit: (limit: number) => `Можно проверить до ${limit} строк за один запуск.`, extraCells: 'В одной из строк больше ячеек, чем в заголовке.', cellLength: (limit: number) => `Каждая ячейка должна быть не длиннее ${limit} символов.`, controlCharacter: 'Таблица содержит недопустимый служебный символ.', tooLarge: 'Таблица слишком большая для безопасного запуска. Уменьшите её до 20 KB.', checkHeaders: 'Проверьте названия столбцов.', rowNumber: 'Номер строки данных (без заголовка)', reason: 'Причина', code: 'Код', columns: 'Столбцы', required: (columns: string) => `Не заполнены: ${columns || 'обязательные поля'}`, duplicate: 'Дубликат строки', rowNotObject: 'Строка не распознана как запись таблицы', invalid: 'Строка не прошла проверку',
} : {
  unclosedQuote: 'Close the quote in the table.', emptyHeader: 'Enter non-empty column names in the first row.', headerLength: (limit: number) => `A column name must be ${limit} characters or fewer.`, columnLimit: (limit: number) => `You can check up to ${limit} columns.`, uniqueHeaders: 'Column names must be unique.', rowLimit: (limit: number) => `You can check up to ${limit} rows in one run.`, extraCells: 'One of the rows has more cells than the header.', cellLength: (limit: number) => `Each cell must be ${limit} characters or fewer.`, controlCharacter: 'The table contains an unsupported control character.', tooLarge: 'The table is too large for a safe run. Reduce it to 20 KB.', checkHeaders: 'Check the column names.', rowNumber: 'Data row number (excluding header)', reason: 'Reason', code: 'Code', columns: 'Columns', required: (columns: string) => `Missing: ${columns || 'required fields'}`, duplicate: 'Duplicate row', rowNotObject: 'The row was not recognized as a table record', invalid: 'The row did not pass validation',
};

const MAX_ROWS = 200;
const MAX_COLUMNS = 20;
const MAX_CELL_LENGTH = 1000;
const MAX_ENCODED_BYTES = 20 * 1024;
const MAX_HEADER_LENGTH = 80;
const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value);

const readDelimitedRows = (value: string, delimiter: string, locale: TableLocale) => {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = '';
  let quoted = false;
  for (let index = 0; index < value.length; index += 1) {
    const char = value[index] || '';
    const next = value[index + 1] || '';
    if (char === '"' && quoted && next === '"') {
      cell += '"';
      index += 1;
    } else if (char === '"') {
      quoted = !quoted;
    } else if (char === delimiter && !quoted) {
      row.push(cell);
      cell = '';
    } else if ((char === '\n' || char === '\r') && !quoted) {
      if (char === '\r' && next === '\n') index += 1;
      row.push(cell);
      rows.push(row);
      row = [];
      cell = '';
    } else {
      cell += char;
    }
  }
  if (quoted) return { rows: [], error: tableCopy(locale).unclosedQuote };
  if (cell || row.length) {
    row.push(cell);
    rows.push(row);
  }
  return { rows, error: '' };
};

const delimiterFor = (value: string) => {
  const header = value.split(/\r?\n/, 1)[0] || '';
  if (header.includes('\t')) return '\t';
  if (header.split(';').length > header.split(',').length) return ';';
  return ',';
};

export const parsePastedTable = (value: string, locale: TableLocale = 'ru'): TableParseResult => {
  const copy = tableCopy(locale);
  if (!value.trim()) return { table: null, error: '' };
  const parsed = readDelimitedRows(value.replace(/^\uFEFF/, ''), delimiterFor(value), locale);
  if (parsed.error) return { table: null, error: parsed.error };
  const sourceColumns = parsed.rows[0] || [];
  const columns = sourceColumns.map((column) => column.trim());
  if (!columns.length || columns.some((column) => !column)) return { table: null, error: copy.emptyHeader };
  if (columns.some((column) => column.length > MAX_HEADER_LENGTH)) return { table: null, error: copy.headerLength(MAX_HEADER_LENGTH) };
  if (columns.length > MAX_COLUMNS) return { table: null, error: copy.columnLimit(MAX_COLUMNS) };
  if (new Set(columns).size !== columns.length) return { table: null, error: copy.uniqueHeaders };
  const rawRows = parsed.rows.slice(1);
  if (rawRows.length > MAX_ROWS) return { table: null, error: copy.rowLimit(MAX_ROWS) };
  const rows: Array<Record<string, string>> = [];
  for (const rawRow of rawRows) {
    if (rawRow.length > columns.length) return { table: null, error: copy.extraCells };
    const row: Record<string, string> = {};
    columns.forEach((column, index) => {
      const cell = rawRow[index] || '';
      row[column] = cell;
    });
    if (Object.values(row).some((cell) => cell.length > MAX_CELL_LENGTH)) return { table: null, error: copy.cellLength(MAX_CELL_LENGTH) };
    if (Object.values(row).some((cell) => cell.includes('\u001f'))) return { table: null, error: copy.controlCharacter };
    rows.push(row);
  }
  const table = { columns, rows };
  if (new TextEncoder().encode(JSON.stringify({ rows })).length > MAX_ENCODED_BYTES) return { table: null, error: copy.tooLarge };
  return { table, error: '' };
};

export const mapTableColumns = (table: TableInput, mapping: Record<string, string>): TableInput => {
  const columns = table.columns.map((column) => (mapping[column] || column).trim());
  return {
    columns,
    rows: table.rows.map((row) => Object.fromEntries(table.columns.map((column, index) => [columns[index] || column, row[column] || '']))),
  };
};

export const tableInputPayload = (table: TableInput) => ({ rows: table.rows });

export const tableInputError = (table: TableInput, locale: TableLocale = 'ru'): string => {
  const copy = tableCopy(locale);
  if (table.columns.some((column) => !column || column.length > MAX_HEADER_LENGTH) || new Set(table.columns).size !== table.columns.length) return copy.checkHeaders;
  if (new TextEncoder().encode(JSON.stringify(tableInputPayload(table))).length > MAX_ENCODED_BYTES) return copy.tooLarge;
  return '';
};

const escapeCsvCell = (value: string) => {
  const safe = /^[=+\-@]/.test(value) ? `'${value}` : value;
  return `"${safe.replaceAll('"', '""')}"`;
};

export const tableTextFromRows = (columns: string[], rows: unknown): string => {
  const sourceRows = Array.isArray(rows) ? rows : [];
  const lines = [columns.map(escapeCsvCell).join(',')];
  sourceRows.forEach((row) => {
    const values = isRecord(row) ? row : {};
    lines.push(columns.map((column) => typeof values[column] === 'string' ? values[column] : '').map(escapeCsvCell).join(','));
  });
  return lines.join('\n');
};

export const reportCsv = (value: Record<string, unknown>, locale: TableLocale = 'ru'): string => {
  const copy = tableCopy(locale);
  const errors = Array.isArray(value.errors) ? value.errors : [];
  const lines = [[copy.rowNumber, copy.reason, copy.code, copy.columns].map(escapeCsvCell).join(',')];
  errors.forEach((error) => {
    const item = isRecord(error) ? error : {};
    const columns = Array.isArray(item.columns) ? item.columns.filter((column) => typeof column === 'string').join(', ') : '';
    const code = String(item.code || 'unknown');
    const reason = code === 'required' ? copy.required(columns) : code === 'duplicate' ? copy.duplicate : code === 'row_not_object' ? copy.rowNotObject : copy.invalid;
    lines.push([String(item.row || ''), reason, code, columns].map(escapeCsvCell).join(','));
  });
  return lines.join('\n');
};
