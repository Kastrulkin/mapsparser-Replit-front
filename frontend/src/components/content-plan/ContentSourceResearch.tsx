export type SourceResearch = {
  purpose?: string;
  schema_version: number; title: string; reviewed_at: string; summary: string;
  methodology: string; historical_evidence: string; limitations: string[]; next_steps: string[];
  stale_post_ids: string[];
  findings: { title: string; text: string; source_ids: string[]; post_ids: string[] }[];
  sources: { reference_id: string; name: string; url: string; page_title: string; checked_at: string;
    publication_note: string; quote: string; observation: string; conclusion: string;
    approach_kind?: string; suggested_example?: string; agreement_question?: string;
    post_ids: string[]; application: string; limits: string; retrieval: string }[];
  posts: { post_id: string; title: string; post_created_at: string; post_updated_at: string;
    scheduled_for: string; post_excerpt: string; theme: string; assessment: string; next_step: string }[];
};

export function researchDate(value: string) {
  const date = new Date(value.length === 10 ? `${value}T12:00:00` : value.replace(' ', 'T'));
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString('ru-RU');
}

export function ContentSourceEvidence({ report, referenceId, ru }: { report: SourceResearch; referenceId: string; ru: boolean }) {
  const evidence = report.sources.find(source => source.reference_id === referenceId);
  if (!evidence) return <p className="mt-3 text-sm text-muted-foreground">{ru ? 'Разбор этого источника ещё не добавлен.' : 'No dated research saved for this source.'}</p>;
  const proposal = report.purpose === 'pre_plan_source_research';
  return <div className="space-y-4 text-sm leading-6">
    <div>
      <h5 className="font-semibold">{ru ? 'Как пишет источник' : 'How the source presents it'}</h5>
      <p className="mt-2">{evidence.observation}</p>
      <blockquote className="mt-3 border-l-2 border-primary pl-3"><p>«{evidence.quote}»</p><footer className="mt-1 text-xs text-muted-foreground">{evidence.name} · {ru ? 'цитата со страницы' : 'page quotation'}</footer></blockquote>
    </div>
    <div className="rounded-lg bg-muted/40 p-3">
      <h5 className="font-semibold">{ru ? 'Что предлагаем взять' : 'Approach to consider'}</h5>
      {evidence.approach_kind && <p className="mt-1 text-xs text-muted-foreground">{evidence.approach_kind}</p>}
      <p className="mt-1">{evidence.conclusion}</p>
    </div>
    <div><h5 className="font-semibold">{ru ? 'Как использовать в ваших постах' : 'How to adapt it for your company'}</h5><p className="mt-2">{proposal ? evidence.application : (ru ? 'Обсудите приём с владельцем и подберите собственные фотографии и факты.' : 'Discuss adaptation with the owner, select appropriate material and confirm company facts.')}</p></div>
    {evidence.suggested_example && <div>
      <h5 className="font-semibold">{ru ? 'Пример темы' : 'Illustrative example'}</h5>
      <p className="mt-1 text-xs text-muted-foreground">{ru ? 'Детали уточним у компании.' : 'Our illustrative example, not a finished post or a company fact.'}</p>
      <p className="mt-2 whitespace-pre-wrap rounded-lg border p-3">{evidence.suggested_example}</p>
    </div>}
    {evidence.agreement_question && <p><strong>{ru ? 'Вопрос владельцу: ' : 'Discuss with the owner: '}</strong>{evidence.agreement_question}</p>}
    <details className="border-t pt-2"><summary className="min-h-11 cursor-pointer py-2 font-medium">{ru ? 'Источник и дата проверки' : 'Date, context and limitations'}</summary>
      <p className="text-xs text-muted-foreground">{evidence.page_title} · {ru ? 'Изучено' : 'Reviewed'} {researchDate(evidence.checked_at)}. {evidence.publication_note}</p>
      <p className="mt-2 text-muted-foreground">{evidence.limits}</p><p className="mt-2 text-muted-foreground">{evidence.retrieval}</p>
    </details>
  </div>;
}
