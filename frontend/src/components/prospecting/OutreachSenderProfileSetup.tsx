import { useCallback, useEffect, useState } from 'react';
import { CheckCircle2, RefreshCw, UserRound } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { newAuth } from '@/lib/auth_new';

type ProfileFact = string | {
  fact?: string;
  text?: string;
  result?: string;
  title?: string;
  status?: string;
};

type SenderProfile = {
  id?: string;
  display_name?: string;
  role_title?: string;
  company_name?: string;
  competence_story?: string;
  proof_points_json?: ProfileFact[];
  verified_cases_json?: ProfileFact[];
  allowed_offers_json?: ProfileFact[];
  forbidden_claims_json?: ProfileFact[];
  voice_examples_json?: ProfileFact[];
  outreach_context_json?: {
    product_outcome?: string;
    services?: string[];
    audience?: string;
    segments?: string[];
    geography?: string;
    recipient_roles?: string[];
    desired_partner_types?: string[];
    disqualifiers?: string[];
    allowed_ctas?: string[];
  };
  confirmed_at?: string | null;
};

type ProfileCompleteness = {
  ready?: boolean;
  completed_count?: number;
  required_count?: number;
  missing_items?: Array<{
    code?: string;
    label?: string;
  }>;
};

type FormState = {
  displayName: string;
  roleTitle: string;
  companyName: string;
  competenceStory: string;
  proofPoints: string;
  verifiedCases: string;
  allowedOffers: string;
  forbiddenClaims: string;
  voiceExamples: string;
  productOutcome: string;
  services: string;
  audience: string;
  segments: string;
  geography: string;
  recipientRoles: string;
  desiredPartnerTypes: string;
  disqualifiers: string;
  allowedCtas: string;
};

const emptyForm: FormState = {
  displayName: '',
  roleTitle: '',
  companyName: '',
  competenceStory: '',
  proofPoints: '',
  verifiedCases: '',
  allowedOffers: '',
  forbiddenClaims: '',
  voiceExamples: '',
  productOutcome: '',
  services: '',
  audience: '',
  segments: '',
  geography: '',
  recipientRoles: '',
  desiredPartnerTypes: '',
  disqualifiers: '',
  allowedCtas: '',
};

const factsToText = (items?: ProfileFact[]) => (items || [])
  .map((item) => typeof item === 'string'
    ? item
    : String(item.fact || item.text || item.result || item.title || ''))
  .filter(Boolean)
  .join('\n');

const lines = (value: string) => value.split('\n').map((item) => item.trim()).filter(Boolean);

export function OutreachSenderProfileSetup({
  businessId,
  defaultCompanyName = '',
  onChanged,
}: {
  businessId?: string | null;
  defaultCompanyName?: string;
  onChanged?: () => void;
}) {
  const [form, setForm] = useState<FormState>({ ...emptyForm, companyName: defaultCompanyName });
  const [confirmed, setConfirmed] = useState(false);
  const [completeness, setCompleteness] = useState<ProfileCompleteness | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    if (!businessId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError('');
    try {
      const payload = await newAuth.makeRequest(`/partnership/sender-profile?business_id=${encodeURIComponent(businessId)}`);
      const profile: SenderProfile | null = payload?.profile || null;
      const profileCompleteness: ProfileCompleteness | null = payload?.profile_completeness || null;
      const suggestedServices = Array.isArray(payload?.suggested_context?.services)
        ? payload.suggested_context.services.map((item: unknown) => String(item || '').trim()).filter(Boolean)
        : [];
      setCompleteness(profileCompleteness);
      if (profile) {
        const context = profile.outreach_context_json || {};
        setForm({
          displayName: String(profile.display_name || ''),
          roleTitle: String(profile.role_title || ''),
          companyName: String(profile.company_name || defaultCompanyName),
          competenceStory: String(profile.competence_story || ''),
          proofPoints: factsToText(profile.proof_points_json),
          verifiedCases: factsToText(profile.verified_cases_json),
          allowedOffers: factsToText(profile.allowed_offers_json),
          forbiddenClaims: factsToText(profile.forbidden_claims_json),
          voiceExamples: factsToText(profile.voice_examples_json),
          productOutcome: String(context.product_outcome || ''),
          services: (context.services?.length ? context.services : suggestedServices).join('\n'),
          audience: String(context.audience || ''),
          segments: (context.segments || []).join('\n'),
          geography: String(context.geography || ''),
          recipientRoles: (context.recipient_roles || []).join('\n'),
          desiredPartnerTypes: (context.desired_partner_types || []).join('\n'),
          disqualifiers: (context.disqualifiers || []).join('\n'),
          allowedCtas: (context.allowed_ctas || []).join('\n'),
        });
        setConfirmed(Boolean(profile.confirmed_at));
      } else {
        setForm({
          ...emptyForm,
          companyName: defaultCompanyName,
          services: suggestedServices.join('\n'),
        });
        setConfirmed(false);
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось загрузить профиль');
    } finally {
      setLoading(false);
    }
  }, [businessId, defaultCompanyName]);

  useEffect(() => {
    void load();
  }, [load]);

  const update = (key: keyof FormState, value: string) => {
    setForm((current) => ({ ...current, [key]: value }));
    setConfirmed(false);
    setNotice('');
  };

  const save = async () => {
    if (!businessId) return;
    setSaving(true);
    setError('');
    setNotice('');
    try {
      const payload = await newAuth.makeRequest('/partnership/sender-profile', {
        method: 'POST',
        body: JSON.stringify({
          business_id: businessId,
          display_name: form.displayName.trim(),
          role_title: form.roleTitle.trim(),
          company_name: form.companyName.trim(),
          competence_story: form.competenceStory.trim(),
          competence_story_status: confirmed ? 'approved' : 'missing',
          proof_points: lines(form.proofPoints).map((fact) => ({ fact, status: confirmed ? 'approved' : 'missing' })),
          verified_cases: lines(form.verifiedCases).map((fact) => ({ fact, status: confirmed ? 'approved' : 'missing' })),
          allowed_offers: lines(form.allowedOffers),
          forbidden_claims: lines(form.forbiddenClaims),
          voice_examples: lines(form.voiceExamples),
          outreach_context: {
            product_outcome: form.productOutcome.trim(),
            services: lines(form.services),
            audience: form.audience.trim(),
            segments: lines(form.segments),
            geography: form.geography.trim(),
            recipient_roles: lines(form.recipientRoles),
            desired_partner_types: lines(form.desiredPartnerTypes),
            disqualifiers: lines(form.disqualifiers),
            allowed_ctas: lines(form.allowedCtas),
          },
          confirmed,
        }),
      });
      const savedCompleteness: ProfileCompleteness | null = payload?.profile_completeness || null;
      const profileConfirmed = Boolean(payload?.profile?.confirmed_at);
      const missingLabels = (savedCompleteness?.missing_items || [])
        .map((item) => String(item.label || '').trim())
        .filter(Boolean);
      setCompleteness(savedCompleteness);
      setNotice(profileConfirmed
        ? 'Профиль подтверждён. LocalOS может использовать эти факты в founder-led сообщениях.'
        : confirmed
          ? `Профиль сохранён, но пока не подтверждён. Осталось: ${missingLabels.join('; ') || 'заполнить обязательные факты'}.`
          : 'Профиль сохранён как черновик. Подтвердите его, когда все факты будут точными.');
      onChanged?.();
      await load();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Не удалось сохранить профиль');
    } finally {
      setSaving(false);
    }
  };

  if (!businessId) return null;

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-3">
        <UserRound className="mt-0.5 h-5 w-5 text-slate-700" />
        <div>
          <div className="font-semibold text-slate-950">Почему вы можете быть полезны</div>
          <p className="mt-1 text-pretty text-sm leading-6 text-slate-600">Только подтверждённые факты попадут в сообщения. Гипотезы не станут обещаниями.</p>
        </div>
      </div>

      {loading ? <div className="flex min-h-11 items-center gap-2 text-sm text-slate-500"><RefreshCw className="h-4 w-4 animate-spin" /> Загружаем профиль…</div> : (
        <>
          <div className={`rounded-xl px-4 py-3 ${completeness?.ready ? 'bg-emerald-50 text-emerald-950 ring-1 ring-emerald-200' : 'bg-amber-50 text-amber-950 ring-1 ring-amber-200'}`}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="font-semibold">
                {completeness?.ready ? 'Фактов достаточно' : 'Что нужно заполнить'}
              </div>
              <div className="text-sm tabular-nums">
                {Number(completeness?.completed_count || 0)} из {Number(completeness?.required_count || 9)} готово
              </div>
            </div>
            {completeness?.ready ? (
              <p className="mt-1 text-pretty text-sm leading-6">Проверьте поля ниже и подтвердите точность фактов.</p>
            ) : (
              <ul className="mt-2 space-y-1 text-sm leading-5">
                {(completeness?.missing_items || []).map((item) => (
                  <li key={String(item.code || item.label)} className="flex gap-2">
                    <span aria-hidden="true">•</span>
                    <span>{item.label}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <Input value={form.displayName} onChange={(event) => update('displayName', event.target.value)} placeholder="Имя отправителя" className="min-h-11 bg-white" />
            <Input value={form.roleTitle} onChange={(event) => update('roleTitle', event.target.value)} placeholder="Роль, например: основатель" className="min-h-11 bg-white" />
          </div>
          <Input value={form.companyName} onChange={(event) => update('companyName', event.target.value)} placeholder="Бизнес" className="min-h-11 bg-white" />
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <div className="font-semibold text-slate-950">Кому и с чем вы хотите писать</div>
            <p className="mt-1 text-sm leading-6 text-slate-600">Эти настройки используются для поиска, квалификации и выбора релевантного следующего шага.</p>
            <div className="mt-3 space-y-3">
              <Textarea value={form.productOutcome} onChange={(event) => update('productOutcome', event.target.value)} placeholder="Какой результат получает клиент или партнёр" className="min-h-20 bg-white" />
              <Textarea value={form.services} onChange={(event) => update('services', event.target.value)} placeholder="Ваши услуги — по одной на строку" className="min-h-20 bg-white" />
              <Textarea value={form.audience} onChange={(event) => update('audience', event.target.value)} placeholder="Кому полезны ваши услуги: аудитория и её контекст" className="min-h-20 bg-white" />
              <div className="grid gap-3 sm:grid-cols-2">
                <Textarea value={form.segments} onChange={(event) => update('segments', event.target.value)} placeholder="Целевые сегменты — по одному на строку" className="min-h-20 bg-white" />
                <Textarea value={form.desiredPartnerTypes} onChange={(event) => update('desiredPartnerTypes', event.target.value)} placeholder="Желаемые типы партнёров — по одному на строку" className="min-h-20 bg-white" />
                <Textarea value={form.recipientRoles} onChange={(event) => update('recipientRoles', event.target.value)} placeholder="Роли получателей — по одной на строку" className="min-h-20 bg-white" />
                <Textarea value={form.allowedCtas} onChange={(event) => update('allowedCtas', event.target.value)} placeholder="Допустимые следующие шаги — по одному на строку" className="min-h-20 bg-white" />
              </div>
              <Input value={form.geography} onChange={(event) => update('geography', event.target.value)} placeholder="География поиска и работы" className="min-h-11 bg-white" />
              <Textarea value={form.disqualifiers} onChange={(event) => update('disqualifiers', event.target.value)} placeholder="Кого исключать из поиска — по одному условию на строку" className="min-h-20 bg-white" />
            </div>
          </div>
          <Textarea value={form.competenceStory} onChange={(event) => update('competenceStory', event.target.value)} placeholder="Какой опыт делает вас релевантными для этого типа партнёров" className="min-h-24 bg-white" />
          <Textarea value={form.proofPoints} onChange={(event) => update('proofPoints', event.target.value)} placeholder="Подтверждённые факты и результаты — по одному на строку" className="min-h-24 bg-white" />
          <Textarea value={form.verifiedCases} onChange={(event) => update('verifiedCases', event.target.value)} placeholder="Проверенные кейсы — по одному на строку" className="min-h-24 bg-white" />
          <Textarea value={form.allowedOffers} onChange={(event) => update('allowedOffers', event.target.value)} placeholder="Что можно предлагать — по одному варианту на строку" className="min-h-20 bg-white" />
          <details className="border-t border-slate-200 pt-2">
            <summary className="min-h-10 cursor-pointer text-sm font-semibold text-slate-700">Голос и запрещённые утверждения</summary>
            <div className="space-y-3 pt-3">
              <Textarea value={form.voiceExamples} onChange={(event) => update('voiceExamples', event.target.value)} placeholder="Примеры ваших живых сообщений" className="min-h-20 bg-white" />
              <Textarea value={form.forbiddenClaims} onChange={(event) => update('forbiddenClaims', event.target.value)} placeholder="Что нельзя утверждать" className="min-h-20 bg-white" />
            </div>
          </details>
          <div className="flex items-start justify-between gap-4 rounded-xl border border-slate-200 bg-white p-4">
            <div>
              <div className="text-sm font-semibold text-slate-950">Подтверждаю факты</div>
              <p className="mt-1 text-xs leading-5 text-slate-600">Включайте только если опыт, кейсы и предложения точны. Если чего-то не хватает, LocalOS сохранит черновик и покажет конкретный список.</p>
            </div>
            <Switch checked={confirmed} onCheckedChange={setConfirmed} aria-label="Подтвердить факты профиля" />
          </div>
          <Button onClick={() => void save()} disabled={saving || !form.displayName.trim() || !form.roleTitle.trim() || !form.companyName.trim()} className="min-h-11 w-full">
            {saving ? <RefreshCw className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
            {confirmed ? 'Сохранить и подтвердить' : 'Сохранить черновик'}
          </Button>
        </>
      )}

      {notice ? <div role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">{notice}</div> : null}
      {error ? <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-950">{error}</div> : null}
    </div>
  );
}
