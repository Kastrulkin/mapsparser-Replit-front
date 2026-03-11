import { useEffect, useMemo, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { newAuth } from '@/lib/auth_new';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

type PartnershipLead = {
  id: string;
  name?: string;
  city?: string;
  category?: string;
  source_url?: string;
  status?: string;
  partnership_stage?: string;
  selected_channel?: string;
  updated_at?: string;
};

const STAGE_OPTIONS = [
  { value: 'all', label: 'Все этапы' },
  { value: 'imported', label: 'Импортировано' },
  { value: 'audited', label: 'Аудит готов' },
  { value: 'matched', label: 'Матчинг готов' },
  { value: 'proposal_draft_ready', label: 'Черновик оффера готов' },
];

export const PartnershipSearchPage: React.FC = () => {
  const { currentBusinessId } = useOutletContext<any>();
  const [loading, setLoading] = useState(false);
  const [linksText, setLinksText] = useState('');
  const [stage, setStage] = useState('all');
  const [query, setQuery] = useState('');
  const [items, setItems] = useState<PartnershipLead[]>([]);
  const [selectedLeadId, setSelectedLeadId] = useState<string | null>(null);
  const [auditData, setAuditData] = useState<any>(null);
  const [matchData, setMatchData] = useState<any>(null);
  const [draftText, setDraftText] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectedLead = useMemo(
    () => items.find((item) => item.id === selectedLeadId) || null,
    [items, selectedLeadId]
  );

  const loadLeads = async () => {
    if (!currentBusinessId) return;
    try {
      setLoading(true);
      setError(null);
      const params = new URLSearchParams();
      params.set('business_id', currentBusinessId);
      if (stage !== 'all') params.set('stage', stage);
      if (query.trim()) params.set('q', query.trim());
      const data = await newAuth.makeRequest(`/partnership/leads?${params.toString()}`, { method: 'GET' });
      setItems(Array.isArray(data.items) ? data.items : []);
      if (selectedLeadId && !(data.items || []).some((x: any) => x.id === selectedLeadId)) {
        setSelectedLeadId(null);
      }
    } catch (e: any) {
      setError(e.message || 'Не удалось загрузить список партнёров');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadLeads();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentBusinessId, stage]);

  const handleImportLinks = async () => {
    if (!currentBusinessId) return;
    const links = linksText
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean);
    if (links.length === 0) {
      setError('Добавьте минимум одну ссылку');
      return;
    }
    try {
      setLoading(true);
      setError(null);
      const data = await newAuth.makeRequest('/partnership/leads/import-links', {
        method: 'POST',
        body: JSON.stringify({ business_id: currentBusinessId, links }),
      });
      setMessage(`Импортировано: ${data.imported_count || 0}, пропущено: ${data.skipped_count || 0}`);
      setLinksText('');
      await loadLeads();
    } catch (e: any) {
      setError(e.message || 'Не удалось импортировать ссылки');
    } finally {
      setLoading(false);
    }
  };

  const runAudit = async (leadId: string) => {
    if (!currentBusinessId) return;
    try {
      setLoading(true);
      setError(null);
      setMatchData(null);
      setDraftText('');
      const data = await newAuth.makeRequest(`/partnership/leads/${leadId}/audit`, {
        method: 'POST',
        body: JSON.stringify({ business_id: currentBusinessId }),
      });
      setAuditData(data.snapshot || null);
      setSelectedLeadId(leadId);
      await loadLeads();
    } catch (e: any) {
      setError(e.message || 'Не удалось выполнить аудит');
    } finally {
      setLoading(false);
    }
  };

  const runMatch = async (leadId: string) => {
    if (!currentBusinessId) return;
    try {
      setLoading(true);
      setError(null);
      setDraftText('');
      const data = await newAuth.makeRequest(`/partnership/leads/${leadId}/match`, {
        method: 'POST',
        body: JSON.stringify({ business_id: currentBusinessId }),
      });
      setMatchData(data.result || null);
      setSelectedLeadId(leadId);
      await loadLeads();
    } catch (e: any) {
      setError(e.message || 'Не удалось выполнить матчинг');
    } finally {
      setLoading(false);
    }
  };

  const runDraft = async (leadId: string) => {
    if (!currentBusinessId) return;
    try {
      setLoading(true);
      setError(null);
      const data = await newAuth.makeRequest(`/partnership/leads/${leadId}/draft-offer`, {
        method: 'POST',
        body: JSON.stringify({ business_id: currentBusinessId, channel: 'telegram', tone: 'профессиональный' }),
      });
      setDraftText(data.text || '');
      setSelectedLeadId(leadId);
      await loadLeads();
    } catch (e: any) {
      setError(e.message || 'Не удалось сгенерировать первое письмо');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-foreground">Поиск партнёрств</h1>
        <p className="text-muted-foreground mt-1">
          Добавьте компании по ссылкам, выполните аудит, матчинг услуг и подготовьте первое письмо.
        </p>
      </div>

      {!currentBusinessId ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          Сначала выберите бизнес в переключателе сверху.
        </div>
      ) : (
        <>
          <div className="rounded-xl border bg-white p-4 space-y-3">
            <h2 className="text-lg font-semibold">Импорт компаний по ссылкам</h2>
            <Textarea
              rows={5}
              value={linksText}
              onChange={(e) => setLinksText(e.target.value)}
              placeholder="Вставьте ссылки на Яндекс Карты, по одной на строку"
            />
            <div className="flex gap-2">
              <Button onClick={handleImportLinks} disabled={loading}>
                Добавить в партнёрский список
              </Button>
              <Button variant="outline" onClick={() => void loadLeads()} disabled={loading}>
                Обновить список
              </Button>
            </div>
          </div>

          <div className="rounded-xl border bg-white p-4">
            <div className="flex flex-col md:flex-row gap-3 mb-4">
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Поиск по названию/ссылке"
              />
              <Select value={stage} onValueChange={setStage}>
                <SelectTrigger className="w-full md:w-[240px]">
                  <SelectValue placeholder="Этап" />
                </SelectTrigger>
                <SelectContent>
                  {STAGE_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button variant="outline" onClick={() => void loadLeads()} disabled={loading}>
                Применить
              </Button>
            </div>

            <div className="space-y-3">
              {items.length === 0 ? (
                <p className="text-sm text-muted-foreground">Список пуст.</p>
              ) : (
                items.map((item) => (
                  <div
                    key={item.id}
                    className={`rounded-lg border p-3 ${selectedLeadId === item.id ? 'border-primary' : 'border-gray-200'}`}
                  >
                    <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                      <div>
                        <div className="font-semibold text-foreground">{item.name || 'Без названия'}</div>
                        <div className="text-sm text-muted-foreground">
                          {item.city || '—'} · {item.category || '—'} · этап: {item.partnership_stage || 'imported'}
                        </div>
                        <a
                          href={item.source_url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-sm text-blue-600 underline break-all"
                        >
                          {item.source_url}
                        </a>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Button variant="outline" size="sm" onClick={() => void runAudit(item.id)} disabled={loading}>
                          Аудит
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => void runMatch(item.id)} disabled={loading}>
                          Матчинг
                        </Button>
                        <Button size="sm" onClick={() => void runDraft(item.id)} disabled={loading}>
                          Первое письмо
                        </Button>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="rounded-xl border bg-white p-4 space-y-3">
            <h2 className="text-lg font-semibold">Результат по выбранному лиду</h2>
            <p className="text-sm text-muted-foreground">
              {selectedLead ? `${selectedLead.name || 'Лид'} (${selectedLead.id})` : 'Лид не выбран'}
            </p>

            {auditData && (
              <div className="rounded-lg border border-gray-200 p-3 bg-gray-50">
                <div className="font-medium mb-1">Аудит карточки</div>
                <p className="text-sm text-muted-foreground">
                  Услуг в превью: {(auditData.services_preview || []).length || 0}
                </p>
              </div>
            )}

            {matchData && (
              <div className="rounded-lg border border-gray-200 p-3 bg-gray-50">
                <div className="font-medium mb-1">Матчинг услуг</div>
                <p className="text-sm text-muted-foreground">
                  Match score: {matchData.match_score ?? 0}%
                </p>
                <p className="text-sm text-muted-foreground">
                  Пересечения: {(matchData.overlap || []).slice(0, 8).join(', ') || '—'}
                </p>
              </div>
            )}

            {draftText && (
              <div className="rounded-lg border border-gray-200 p-3 bg-gray-50">
                <div className="font-medium mb-2">Первое письмо</div>
                <Textarea value={draftText} rows={8} readOnly />
              </div>
            )}
          </div>
        </>
      )}

      {message && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm text-emerald-800">
          {message}
        </div>
      )}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
          {error}
        </div>
      )}
    </div>
  );
};

