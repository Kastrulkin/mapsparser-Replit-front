import assert from 'node:assert/strict';
import {
  buildServicesQualityAudit,
  getKeywordMatches,
  getKeywordScore,
  getMatchedKeywords,
  getServiceQuality,
} from '../src/components/dashboard/cardServicesLogic.ts';

const service = (keywords: string[]) => ({ keywords });

assert.deepEqual(
  getKeywordMatches('Коррекция бровей мужская', service(['брови'])),
  [{ keyword: 'брови', level: 'normalized' }],
);

assert.deepEqual(
  getKeywordMatches('Ваксинг одной зоны', service(['восковая депиляция'])),
  [{ keyword: 'восковая депиляция', level: 'close' }],
);

assert.deepEqual(
  getKeywordMatches('Биозавивка афрокудри на экстра длинные волосы', service(['афро'])),
  [{ keyword: 'афро', level: 'exact' }],
);

assert.deepEqual(
  getKeywordMatches('Ламинирование ресниц', service(['ресницы'])),
  [{ keyword: 'ресницы', level: 'normalized' }],
);

assert.deepEqual(
  getMatchedKeywords('Кофе с собой', service(['восковая депиляция'])),
  [],
);

const permanentScore = getKeywordScore(
  'Пудровое напыление бровей',
  service(['перманентный макияж']),
  'Макияж бровей',
);
assert.equal(permanentScore.found, 1);
assert.equal(permanentScore.closeCount, 1);
assert.deepEqual(permanentScore.weak, ['перманентный макияж']);
assert.deepEqual(permanentScore.added, ['перманентный макияж']);

const nailScore = getKeywordScore(
  'Маникюр с покрытием ногтей',
  service(['ногти', 'покрытие', 'педикюр']),
  'Маникюр',
);
assert.equal(nailScore.found, 2);
assert.deepEqual(nailScore.missing, ['педикюр']);

const botoxScore = getKeywordScore('Ботулинотерапия лица', service(['ботокс']));
assert.equal(botoxScore.closeCount, 1);

const cleaningScore = getKeywordScore('Пилинг и уход за лицом', service(['чистка лица']));
assert.equal(cleaningScore.closeCount, 1);

const laminationScore = getKeywordScore('Долговременная укладка бровей', service(['ламинирование']));
assert.equal(laminationScore.closeCount, 1);

const badQuality = getServiceQuality({
  id: 'svc-1',
  name: 'Ботулинотерапия лица',
  optimized_name: 'Ботулинотерапия лица',
  optimized_description: 'Ботулинотерапия лица: услуга по исходному формату записи.',
  keywords: ['ботокс', 'морщины'],
  fallback_used: true,
  guardrail_reasons: ['added_unconfirmed_medical_claim_name'],
});
assert.equal(badQuality.needsReview, true);
assert.equal(badQuality.issueCodes.includes('missing_keywords'), true);
assert.equal(badQuality.issueCodes.includes('fallback_used'), true);
assert.equal(badQuality.issueCodes.includes('guardrail_reasons'), true);

const qualityAudit = buildServicesQualityAudit([
  {
    id: 'good',
    name: 'Коррекция бровей',
    optimized_name: 'Коррекция бровей мужская',
    optimized_description: 'Коррекция бровей мужская: короткое описание.',
    keywords: ['брови'],
  },
  {
    id: 'bad',
    name: 'Пудровое напыление бровей',
    optimized_name: 'Пудровое напыление бровей',
    optimized_description: 'Пудровое напыление бровей: услуга по исходному формату записи.',
    keywords: ['перманентный макияж', 'ресницы'],
  },
]);
assert.equal(qualityAudit.summary.total, 2);
assert.equal(qualityAudit.summary.good, 1);
assert.equal(qualityAudit.summary.needsReview, 1);
assert.equal(qualityAudit.summary.missingKeywords, 1);
assert.equal(qualityAudit.telegramSummary.includes('Проверено 2 услуг'), true);

console.log('cardServicesLogic keyword matching tests passed');
