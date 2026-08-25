import { useCallback, useEffect, useState } from 'react';
import { CheckCircle2, EyeOff, Lightbulb, Loader2, MessageCircleQuestion, RefreshCw, Save, Settings2 } from 'lucide-react';

import { TelegramResearchSetup } from '@/components/TelegramResearchSetup';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { newAuth } from '@/lib/auth_new';
import { useLanguage } from '@/i18n/LanguageContext';
import { fillContentTemplate, getContentWorkspaceControlsCopy, getContentWorkspaceCopy } from '@/i18n/contentWorkspaceCopy';

type AudienceInsight = {
  id: string;
  concept_type?: string;
  label?: string;
  display_label?: string;
  industry?: string;
  sources_count?: number;
  messages_count?: number;
  relevance_score?: number;
  engagement_score?: number;
  priority_score?: number;
  last_seen_at?: string;
  has_private_sources?: boolean;
  decision?: string;
  content_angle?: string;
};

export const AudienceInsights = ({ businessId }: { businessId: string }) => {
  const { language } = useLanguage();
  const copy = getContentWorkspaceCopy(language);
  const controls = getContentWorkspaceControlsCopy(language);
  const [items, setItems] = useState<AudienceInsight[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [sourcesOpen, setSourcesOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const response = await newAuth.makeRequest(`/business/${encodeURIComponent(businessId)}/audience-insights`);
      setItems(Array.isArray(response.items) ? response.items : []);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : copy.loadError);
    } finally {
      setLoading(false);
    }
  }, [businessId, copy.loadError]);

  useEffect(() => {
    void load();
  }, [load]);

  const decide = async (item: AudienceInsight, decision: 'use_in_plan' | 'save_as_rule' | 'ignored') => {
    setSavingId(item.id);
    setError('');
    setMessage('');
    try {
      await newAuth.makeRequest(`/business/${encodeURIComponent(businessId)}/audience-insights/${encodeURIComponent(item.id)}/decision`, {
        method: 'POST',
        body: JSON.stringify({ decision }),
      });
      const decisionMessage = decision === 'use_in_plan'
        ? copy.decisionPlan
        : decision === 'save_as_rule'
          ? copy.decisionRule
          : copy.decisionIgnored;
      setMessage(decisionMessage);
      await load();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : copy.saveError);
    } finally {
      setSavingId('');
    }
  };

  return (
    <section className="space-y-5" aria-labelledby="audience-insights-title">
      <Sheet open={sourcesOpen} onOpenChange={setSourcesOpen}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-2xl">
          <SheetHeader>
            <SheetTitle>{controls.sourcesTitle}</SheetTitle>
            <SheetDescription>
              {controls.sourcesDescription}
            </SheetDescription>
          </SheetHeader>
          <div className="mt-6">
            <TelegramResearchSetup businessId={businessId} mode="sources" />
          </div>
        </SheetContent>
      </Sheet>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">{copy.marketKnowledge}</div>
          <h2 id="audience-insights-title" className="mt-1 text-2xl font-semibold text-slate-950">{copy.audienceTitle}</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">{copy.audienceDescription}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button type="button" onClick={() => setSourcesOpen(true)} className="min-h-10 bg-slate-950 text-white hover:bg-slate-800">
            <Settings2 className="mr-2 h-4 w-4" /> {controls.configureSources}
          </Button>
          <Button type="button" variant="outline" onClick={() => void load()} disabled={loading} className="min-h-10">
            <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} /> {copy.refresh}
          </Button>
        </div>
      </div>

      {error ? <div className="rounded-2xl bg-rose-50 px-4 py-3 text-sm text-rose-800 ring-1 ring-rose-100">{error}</div> : null}
      {message ? <div className="rounded-2xl bg-emerald-50 px-4 py-3 text-sm text-emerald-800 ring-1 ring-emerald-100">{message}</div> : null}

      {loading && items.length === 0 ? (
        <div className="flex min-h-56 items-center justify-center gap-2 rounded-3xl bg-white text-sm text-slate-500 ring-1 ring-slate-200"><Loader2 className="h-4 w-4 animate-spin" /> {copy.loading}</div>
      ) : items.length === 0 ? (
        <div className="rounded-3xl bg-white px-6 py-12 text-center ring-1 ring-slate-200">
          <MessageCircleQuestion className="mx-auto h-8 w-8 text-slate-400" />
          <p className="mt-3 font-semibold text-slate-900">{copy.emptyTitle}</p>
          <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-slate-600">{copy.emptyDescription}</p>
          <Button type="button" onClick={() => setSourcesOpen(true)} className="mt-5 min-h-10 bg-slate-950 text-white hover:bg-slate-800">{controls.addSource}</Button>
        </div>
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          {items.map((item) => (
            <article key={item.id} className="flex min-h-60 flex-col rounded-3xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
              <div className="flex items-start justify-between gap-3">
                <span className="rounded-full bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-700 ring-1 ring-sky-100">{copy.insightTypes[item.concept_type || ''] || copy.audienceTopic}</span>
                <span className="text-sm font-semibold tabular-nums text-slate-500">{copy.importance} {Math.round(item.priority_score || 0)}%</span>
              </div>
              <h3 className="mt-4 text-lg font-semibold leading-7 text-slate-950">{item.display_label || item.label}</h3>
              <p className="mt-2 text-sm leading-6 text-slate-600">{fillContentTemplate(copy.repeated, { messages: item.messages_count || 0, sources: item.sources_count || 0 })}</p>
              <div className="mt-4 border-t border-slate-100 pt-4">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">{language === 'ru' ? 'Что добавить в план' : copy.audienceTopic}</p>
                <p className="mt-2 text-sm leading-6 text-slate-700">{item.content_angle || item.label}</p>
              </div>
              <div className="mt-auto flex flex-wrap gap-2 pt-5">
                <Button type="button" onClick={() => void decide(item, 'use_in_plan')} disabled={savingId === item.id || item.decision === 'use_in_plan'} className="min-h-10 bg-slate-950 text-white hover:bg-slate-800">
                  <Lightbulb className="mr-2 h-4 w-4" /> {item.decision === 'use_in_plan' ? copy.addedToPlan : copy.useInPlan}
                </Button>
                <Button type="button" variant="outline" onClick={() => void decide(item, 'save_as_rule')} disabled={savingId === item.id} className="min-h-10">
                  <Save className="mr-2 h-4 w-4" /> {copy.saveRule}
                </Button>
                <Button type="button" variant="ghost" onClick={() => void decide(item, 'ignored')} disabled={savingId === item.id} className="min-h-10 text-slate-500">
                  {item.decision === 'ignored' ? <CheckCircle2 className="mr-2 h-4 w-4" /> : <EyeOff className="mr-2 h-4 w-4" />} {copy.unsuitable}
                </Button>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
};
