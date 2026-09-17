export const RIDERRA_BUSINESS_ID = 'edbd961a-273f-4f15-836e-33aacc0aa0e3';
export const RIDERRA_SENDER_ACCOUNT_ID = '5e9ce7db-44d1-49dc-9aed-b35ed7174089';
export const RIDERRA_SENDER_IDENTITY = 'riderracs@gmail.com';
export const RIDERRA_AUTHORIZATION_REFERENCE = 'codex:019fd1f3-f2a4-7ea3-8741-0b54ffec3b7e/01a084f0-4624-7650-82d3-8c86c9771af7';
export const RIDERRA_DAILY_LIMIT = 150;

const PRICEBOOK_ID = '17YqqHe0TgDvUgXDNq0FeYe7113R2LTZza4musWLjEUo';
const PRICEBOOK_SHEET = 'Актуальный полный';
const PRICEBOOK_PROVIDER = 'Google Sheets via configured Google Drive connector';
const SUBJECT_TEMPLATE_SUFFIX = 'airport transfers';

const BODY_TEMPLATE = `Hello {company} team,

{opening}

I'm Alex from Riderra. Large transfer brands can add intermediaries without improving the transfer itself.

We keep the chain short, so most of your payment goes to the local operator. We have over 10 years of experience and a 0.24% complaint rate. We've arranged transfers for private aviation pilots, ministers and presidents' families.

Would you be open to trying us for a transfer from {route} for just {price} ({vehicle}, up to {pax} passengers)? You can submit a request at https://riderra.com.

Best regards,
Alex Demyanov
Riderra`;

const BODY_WITHOUT_OPENING_TEMPLATE = `Hello {company} team,

I'm Alex from Riderra. Large transfer brands can add intermediaries without improving the transfer itself.

We keep the chain short, so most of your payment goes to the local operator. We have over 10 years of experience and a 0.24% complaint rate. We've arranged transfers for private aviation pilots, ministers and presidents' families.

Would you be open to trying us for a transfer from {route} for just {price} ({vehicle}, up to {pax} passengers)? You can submit a request at https://riderra.com.

Best regards,
Alex Demyanov
Riderra`;

export type JsonRecord = {
  [key: string]: unknown;
};

export type RiderraRecord = JsonRecord & {
  lead_id: string;
  workstream_id: string;
  contact_point_id: string;
  recipient: string;
  company: string;
  city: string;
  opening: string;
  opening_variant: string;
  content_sha256: string;
  pricebook: JsonRecord;
};

export type RiderraPreview = {
  subject: string;
  body: string;
};

export type RiderraManifest = JsonRecord & {
  business_id: string;
  sender_account_id: string;
  sender_identity: string;
  daily_limit: number;
  records_sha256: string;
  records: JsonRecord[];
};

export const isJsonRecord = (value: unknown): value is JsonRecord => (
  typeof value === 'object' && value !== null && !Array.isArray(value)
);

const requiredString = (record: JsonRecord, key: string, index: number) => {
  const value = record[key];
  if (typeof value !== 'string' || !value.trim()) {
    throw new Error(`Запись ${index + 1}: нет обязательного поля ${key}.`);
  }
  return value.trim();
};

const optionalString = (record: JsonRecord, key: string) => {
  const value = record[key];
  return typeof value === 'string' ? value.trim() : '';
};

const requiredPricebook = (record: JsonRecord, index: number) => {
  if (!isJsonRecord(record.pricebook)) {
    throw new Error(`Запись ${index + 1}: нет проверенной цены.`);
  }
  for (const key of ['route', 'price', 'vehicle']) {
    requiredString(record.pricebook, key, index);
  }
  if (typeof record.pricebook.pax !== 'number' || !Number.isInteger(record.pricebook.pax)) {
    throw new Error(`Запись ${index + 1}: неверно указано число пассажиров.`);
  }
  return record.pricebook;
};

export const parseRiderraRecords = (text: string): RiderraRecord[] => {
  const parsed: unknown = JSON.parse(text);
  const source = isJsonRecord(parsed) ? parsed.records : parsed;
  if (!Array.isArray(source)) {
    throw new Error('Файл группы должен содержать массив records.');
  }
  if (source.length < 1 || source.length > RIDERRA_DAILY_LIMIT) {
    throw new Error(`В группе должно быть от 1 до ${RIDERRA_DAILY_LIMIT} компаний.`);
  }

  return source.map((value, index) => {
    if (!isJsonRecord(value)) {
      throw new Error(`Запись ${index + 1} должна быть JSON-объектом.`);
    }
    const openingVariant = requiredString(value, 'opening_variant', index);
    if (!['verified_opening_v1', 'no_opening_v1'].includes(openingVariant)) {
      throw new Error(`Запись ${index + 1}: недопустимый вариант шаблона.`);
    }
    if (value.audience !== 'transfer_buyer') {
      throw new Error(`Запись ${index + 1}: группа не относится к покупателям трансферов.`);
    }
    const pricebook = requiredPricebook(value, index);
    return {
      ...value,
      lead_id: requiredString(value, 'lead_id', index),
      workstream_id: requiredString(value, 'workstream_id', index),
      contact_point_id: requiredString(value, 'contact_point_id', index),
      recipient: requiredString(value, 'recipient', index).toLowerCase(),
      company: requiredString(value, 'company', index),
      city: requiredString(value, 'city', index),
      opening: optionalString(value, 'opening'),
      opening_variant: openingVariant,
      content_sha256: requiredString(value, 'content_sha256', index),
      pricebook: { ...pricebook },
    };
  });
};

export const validateRiderraSnapshot = (text: string) => {
  const parsed: unknown = JSON.parse(text);
  if (!isJsonRecord(parsed)) {
    throw new Error('Файл snapshot005 должен содержать JSON-объект.');
  }
  if (
    parsed.spreadsheet_id !== PRICEBOOK_ID
    || parsed.sheet !== PRICEBOOK_SHEET
    || parsed.evidence_kind !== 'provider_observed'
    || parsed.provider !== PRICEBOOK_PROVIDER
    || typeof parsed.verified_at !== 'string'
    || !Array.isArray(parsed.ranges)
  ) {
    throw new Error('Это не проверенный snapshot005 из нужного листа тарифов.');
  }
};

export const previewRiderraRecord = (record: RiderraRecord): RiderraPreview => {
  const route = String(record.pricebook.route || '').trim();
  const price = String(record.pricebook.price || '').trim();
  const vehicle = String(record.pricebook.vehicle || '').trim();
  const pax = String(record.pricebook.pax || '').trim();
  const subject = `${record.company} | Riderra | ${record.city} ${SUBJECT_TEMPLATE_SUFFIX}`;
  const template = record.opening_variant === 'verified_opening_v1' ? BODY_TEMPLATE : BODY_WITHOUT_OPENING_TEMPLATE;
  const body = template
    .replace('{company}', record.company)
    .replace('{opening}', record.opening)
    .replace('{route}', route)
    .replace('{price}', price)
    .replace('{vehicle}', vehicle)
    .replace('{pax}', pax);
  return { subject, body };
};

const sameString = (record: JsonRecord, key: string, expected: string) => record[key] === expected;

export const verifyRiderraManifest = (value: unknown, selectedRecords: RiderraRecord[]): RiderraManifest => {
  if (!isJsonRecord(value)) throw new Error('Сервер не вернул проверяемый состав группы.');
  if (
    value.business_id !== RIDERRA_BUSINESS_ID
    || value.sender_account_id !== RIDERRA_SENDER_ACCOUNT_ID
    || value.sender_identity !== RIDERRA_SENDER_IDENTITY
    || value.daily_limit !== RIDERRA_DAILY_LIMIT
    || typeof value.records_sha256 !== 'string'
    || !/^[0-9a-f]{64}$/.test(value.records_sha256)
    || !Array.isArray(value.records)
    || value.records.length !== selectedRecords.length
  ) {
    throw new Error('Серверная группа не совпала с выбранными компаниями.');
  }

  value.records.forEach((serverRecord, index) => {
    if (!isJsonRecord(serverRecord)) throw new Error('Сервер вернул неверную запись группы.');
    const selected = selectedRecords[index];
    const preview = previewRiderraRecord(selected);
    const exact = (
      sameString(serverRecord, 'lead_id', selected.lead_id)
      && sameString(serverRecord, 'workstream_id', selected.workstream_id)
      && sameString(serverRecord, 'contact_point_id', selected.contact_point_id)
      && sameString(serverRecord, 'recipient', selected.recipient)
      && sameString(serverRecord, 'opening_variant', selected.opening_variant)
      && sameString(serverRecord, 'content_sha256', selected.content_sha256)
      && sameString(serverRecord, 'subject', preview.subject)
      && sameString(serverRecord, 'body', preview.body)
    );
    if (!exact) throw new Error(`Серверная запись ${index + 1} изменилась после вашего выбора.`);
  });

  return {
    ...value,
    business_id: RIDERRA_BUSINESS_ID,
    sender_account_id: RIDERRA_SENDER_ACCOUNT_ID,
    sender_identity: RIDERRA_SENDER_IDENTITY,
    daily_limit: RIDERRA_DAILY_LIMIT,
    records_sha256: value.records_sha256,
    records: value.records,
  };
};

export const cloneRiderraRecords = (records: RiderraRecord[]) => records.map((record) => ({
  ...record,
  pricebook: { ...record.pricebook },
}));

export const challengeManifest = (error: unknown) => {
  if (!isJsonRecord(error) || !isJsonRecord(error.details)) return null;
  if (error.details.error !== 'exact_riderra_manifest_approval_required') return null;
  return error.details.manifest;
};

export const activeAuthorizationSummary = (value: unknown) => {
  if (!isJsonRecord(value) || !isJsonRecord(value.authorization)) return { active: false, count: 0 };
  const authorization = value.authorization;
  if (!isJsonRecord(authorization.manifest) || !Array.isArray(authorization.manifest.records)) {
    return { active: false, count: 0 };
  }
  return { active: true, count: authorization.manifest.records.length };
};
