import { useEffect, useState } from 'react';
import { BellRing, CheckCircle2, Lightbulb, MessageSquareReply, Plus, RefreshCw, Trash2 } from 'lucide-react';
import { api } from '@/services/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { useLanguage } from '@/i18n/LanguageContext';
import { getDemoWorkspaceCopy } from '@/i18n/demoWorkspaceCopy';

type RadarSource = {
  id: string;
  title: string;
  telegram_chat_id: string;
  telegram_username?: string | null;
  is_active: boolean;
  monitor_config_json?: {
    keywords?: string[];
    [key: string]: unknown;
  } | null;
};

type RadarOpportunity = {
  id: string;
  chat_title: string;
  message_text: string;
  signal_type: string;
  score: number;
  reason?: string | null;
  reply_draft?: string | null;
  status: string;
  message_link?: string | null;
  created_at?: string | null;
};

type Props = {
  businessId?: string | null;
  mode?: 'settings' | 'work';
  sourceSetup?: 'visible' | 'hidden';
};

export const TelegramOpportunityRadar = ({ businessId, mode = 'settings', sourceSetup = 'visible' }: Props) => {
  const { language } = useLanguage();
  const copy = getDemoWorkspaceCopy(language).telegram;
  const [sources, setSources] = useState<RadarSource[]>([]);
  const [opportunities, setOpportunities] = useState<RadarOpportunity[]>([]);
  const [title, setTitle] = useState('');
  const [peer, setPeer] = useState('');
  const [keywords, setKeywords] = useState(copy.keywordsPlaceholder);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savingKeywords, setSavingKeywords] = useState(false);
  const [error, setError] = useState('');
  const [savedMessage, setSavedMessage] = useState('');

  const parseKeywords = (value: string) => value
    .split(/[,;\n]+/)
    .map((item) => item.trim())
    .filter(Boolean);

  const extractSourceKeywords = (items: RadarSource[]) => {
    const seen = new Set<string>();
    const result: string[] = [];
    items.forEach((source) => {
      const sourceKeywords = Array.isArray(source.monitor_config_json?.keywords)
        ? source.monitor_config_json?.keywords || []
        : [];
      sourceKeywords.forEach((item) => {
        const keyword = String(item || '').trim();
        const key = keyword.toLowerCase();
        if (!keyword || seen.has(key)) return;
        seen.add(key);
        result.push(keyword);
      });
    });
    return result;
  };

  const loadRadar = async () => {
    if (!businessId) return;
    setLoading(true);
    setError('');
    try {
      const [sourcesResponse, opportunitiesResponse] = await Promise.all([
        api.get('/telegram-opportunity-radar/sources', { params: { business_id: businessId } }),
        api.get('/telegram-opportunity-radar/opportunities', { params: { business_id: businessId, limit: 20 } }),
      ]);
      const loadedSources = Array.isArray(sourcesResponse.data?.sources) ? sourcesResponse.data.sources : [];
      setSources(loadedSources);
      setOpportunities(Array.isArray(opportunitiesResponse.data?.opportunities) ? opportunitiesResponse.data.opportunities : []);
      const loadedKeywords = extractSourceKeywords(loadedSources);
      if (loadedKeywords.length > 0) {
        setKeywords(loadedKeywords.join(', '));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : copy.loadError);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRadar();
  }, [businessId]);

  useEffect(() => {
    if (sources.length === 0) setKeywords(copy.keywordsPlaceholder);
  }, [copy.keywordsPlaceholder, sources.length]);

  const addSource = async () => {
    if (!businessId || !peer.trim()) return;
    setSaving(true);
    setError('');
    try {
      await api.post('/telegram-opportunity-radar/sources', {
        business_id: businessId,
        source: {
          title: title.trim() || peer.trim(),
          telegram_chat_id: peer.trim(),
          telegram_username: peer.trim().startsWith('@') ? peer.trim().slice(1) : '',
          source_type: 'chat',
          monitor_config: {
            keywords: parseKeywords(keywords),
          },
        },
      });
      setTitle('');
      setPeer('');
      await loadRadar();
    } catch (err) {
      setError(err instanceof Error ? err.message : copy.addError);
    } finally {
      setSaving(false);
    }
  };

  const saveKeywords = async () => {
    if (!businessId) return;
    setSavingKeywords(true);
    setError('');
    setSavedMessage('');
    try {
      const response = await api.patch('/telegram-opportunity-radar/sources/keywords', {
        business_id: businessId,
        keywords: parseKeywords(keywords),
      });
      const nextSources = Array.isArray(response.data?.sources) ? response.data.sources : sources;
      const nextKeywords = Array.isArray(response.data?.keywords) ? response.data.keywords : parseKeywords(keywords);
      setSources(nextSources);
      setKeywords(nextKeywords.join(', '));
      setSavedMessage(`${copy.savedFor} ${response.data?.updated_sources ?? nextSources.length}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : copy.saveError);
    } finally {
      setSavingKeywords(false);
    }
  };

  const updateStatus = async (opportunityId: string, status: string) => {
    if (!businessId) return;
    await api.post(`/telegram-opportunity-radar/opportunities/${opportunityId}/status`, {
      business_id: businessId,
      status,
    });
    setOpportunities((items) => items.map((item) => (item.id === opportunityId ? { ...item, status } : item)));
  };

  const newCount = opportunities.filter((item) => item.status === 'new').length;
  const isWorkMode = mode === 'work';
  const showSourceSetup = sourceSetup === 'visible';
  const keywordList = parseKeywords(keywords);

  return (
    <Card className="overflow-hidden border-slate-200">
      <CardHeader className="space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2 text-xl">
              <BellRing className="h-5 w-5 text-sky-600" />
              {isWorkMode ? copy.workTitle : copy.settingsTitle}
            </CardTitle>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              {isWorkMode
                ? copy.workDescription
                : copy.settingsDescription}
            </p>
          </div>
          <Badge variant={newCount > 0 ? 'default' : 'secondary'}>{newCount} {copy.newItems}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        {!businessId ? (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            {copy.chooseBusiness}
          </div>
        ) : null}

        {showSourceSetup ? (
          <>
            <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto]">
              <div className="space-y-2">
                <Label htmlFor="telegram-radar-peer">{copy.peerLabel}</Label>
                <Input
                  id="telegram-radar-peer"
                  value={peer}
                  onChange={(event) => setPeer(event.target.value)}
                  placeholder={copy.peerPlaceholder}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="telegram-radar-title">{copy.titleLabel}</Label>
                <Input
                  id="telegram-radar-title"
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  placeholder={copy.titlePlaceholder}
                />
              </div>
              <div className="flex items-end">
                <Button type="button" className="gap-2" onClick={addSource} disabled={!businessId || !peer.trim() || saving}>
                  <Plus className="h-4 w-4" />
                  {copy.add}
                </Button>
              </div>
            </div>

          </>
        ) : null}

        <div className="rounded-lg border border-slate-200 bg-slate-50/60 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <Label htmlFor="telegram-radar-keywords">{copy.keywordsLabel}</Label>
              <p className="mt-1 text-xs leading-5 text-slate-500">
                {copy.keywordsDescription}
              </p>
            </div>
            <Badge variant="secondary">{keywordList.length} {copy.words}</Badge>
          </div>
          <Textarea
            id="telegram-radar-keywords"
            value={keywords}
            onChange={(event) => {
              setKeywords(event.target.value);
              setSavedMessage('');
            }}
            className="mt-3 min-h-24 bg-white"
            placeholder={copy.keywordsPlaceholder}
          />
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Button type="button" size="sm" onClick={saveKeywords} disabled={!businessId || savingKeywords}>
              {savingKeywords ? copy.saving : copy.saveWords}
            </Button>
            {savedMessage ? <span className="text-xs font-medium text-emerald-700">{savedMessage}</span> : null}
          </div>
          {keywordList.length > 0 ? (
            <div className="mt-3 flex max-h-28 flex-wrap gap-1.5 overflow-auto">
              {keywordList.map((keyword) => (
                <span key={keyword.toLowerCase()} className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-600">
                  {keyword}
                </span>
              ))}
            </div>
          ) : null}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button type="button" variant="outline" size="sm" className="gap-2" onClick={loadRadar} disabled={loading || !businessId}>
            <RefreshCw className="h-4 w-4" />
            {copy.refresh}
          </Button>
          <span className="text-xs text-slate-500">
            {isWorkMode
              ? copy.workHint
              : copy.settingsHint}
          </span>
        </div>

        {error ? (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>
        ) : null}

        <div className="grid gap-4 lg:grid-cols-[0.8fr_1.2fr]">
          <div className="rounded-lg border border-slate-200">
            <div className="border-b border-slate-100 px-4 py-3 text-sm font-semibold text-slate-900">{copy.sources}</div>
            <div className="divide-y divide-slate-100">
              {sources.length === 0 ? (
                <div className="px-4 py-6 text-sm text-slate-500">{copy.emptySources}</div>
              ) : sources.map((source) => (
                <div key={source.id} className="px-4 py-3">
                  <div className="font-medium text-slate-900">{source.title}</div>
                  <div className="mt-1 text-xs text-slate-500">{source.telegram_username ? `@${source.telegram_username}` : source.telegram_chat_id}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-slate-200">
            <div className="border-b border-slate-100 px-4 py-3 text-sm font-semibold text-slate-900">{copy.workTitle}</div>
            <div className="divide-y divide-slate-100">
              {opportunities.length === 0 ? (
                <div className="px-4 py-6 text-sm text-slate-500">{copy.emptyMessages}</div>
              ) : opportunities.map((item) => (
                <div key={item.id} className="space-y-3 px-4 py-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="font-medium text-slate-900">{item.chat_title}</div>
                    <Badge variant={item.status === 'new' ? 'default' : 'secondary'}>{copy.statuses[item.status] || item.status}</Badge>
                  </div>
                  <div className="text-sm leading-6 text-slate-700">{item.message_text}</div>
                  <div className="text-xs text-slate-500">{item.signal_type} · score {item.score}{item.reason ? ` · ${item.reason}` : ''}</div>
                  {item.reply_draft ? <div className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700">{item.reply_draft}</div> : null}
                  <div className="flex flex-wrap gap-2">
                    <Button type="button" size="sm" variant="outline" className="gap-1" onClick={() => updateStatus(item.id, 'answered')}>
                      <MessageSquareReply className="h-4 w-4" />
                      {copy.answered}
                    </Button>
                    <Button type="button" size="sm" variant="outline" className="gap-1" onClick={() => updateStatus(item.id, 'saved_as_content_idea')}>
                      <Lightbulb className="h-4 w-4" />
                      {copy.idea}
                    </Button>
                    <Button type="button" size="sm" variant="outline" className="gap-1" onClick={() => updateStatus(item.id, 'useful')}>
                      <CheckCircle2 className="h-4 w-4" />
                      {copy.useful}
                    </Button>
                    <Button type="button" size="sm" variant="ghost" className="gap-1 text-slate-500" onClick={() => updateStatus(item.id, 'ignored')}>
                      <Trash2 className="h-4 w-4" />
                      {copy.hide}
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};
