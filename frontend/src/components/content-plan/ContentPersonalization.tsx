import { useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { ContentReferences } from './ContentReferences';
import { contentRequest, ContentAccessError } from './contentRequest';

type Profile = {
  version: number; summary?: string;
  preferences?: { business_description?: string; audience_description?: string; tone_instruction?: string; editorial_notes?: Array<{ id: string; kind: string; text: string }> };
  examples?: Array<{ id: string; text: string }>;
};
const steps = ['О бизнесе', 'О клиентах', 'Как писать'];

/** One content setup for web, Telegram and MAX. Facts and examples retain their existing storage. */
export function ContentPersonalization({ businessId, open, onOpenChange, headers, onOpenKnowledge }: {
  businessId: string; open: boolean; onOpenChange: (open: boolean) => void;
  headers?: () => HeadersInit; onOpenKnowledge?: () => void;
}) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [business, setBusiness] = useState('');
  const [audience, setAudience] = useState('');
  const [tone, setTone] = useState('');
  const [story, setStory] = useState('');
  const [example, setExample] = useState('');
  const [step, setStep] = useState(0);
  const [references, setReferences] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState('');
  const generation = useRef(0);
  const endpoint = '/content-voice?business_id=' + encodeURIComponent(businessId);
  useEffect(() => {
    const version = ++generation.current;
    setProfile(null); setBusiness(''); setAudience(''); setTone(''); setStory(''); setExample('');
    setError(''); setSaved(''); setStep(0); setReferences(false); setBusy(false);
    if (!open || !businessId) return;
    setBusy(true);
    void contentRequest<{ profile: Profile }>(endpoint, undefined, headers).then(({ profile: loaded }) => {
      if (generation.current !== version) return;
      setProfile(loaded); setBusiness(loaded.preferences?.business_description || '');
      setAudience(loaded.preferences?.audience_description || ''); setTone(loaded.preferences?.tone_instruction || loaded.summary || '');
    }).catch(reason => { if (generation.current === version) setError(reason instanceof Error ? reason.message : 'Не удалось загрузить настройки.'); })
      .finally(() => { if (generation.current === version) setBusy(false); });
    return () => { generation.current += 1; };
  }, [businessId, open, endpoint, headers]);

  const save = async () => {
    if (!profile || busy) return;
    const version = generation.current;
    setBusy(true); setError(''); setSaved('');
    try {
      const result = await contentRequest<{ profile: Profile }>('/content-voice', {
        method: 'PATCH', body: JSON.stringify({ business_id: businessId, expected_version: profile.version,
          summary: tone, preferences: { business_description: business.trim(), audience_description: audience.trim() },
          ...(story.trim() ? { founder_story: story.trim() } : {}), confirm: true }),
      }, headers);
      if (generation.current !== version) return;
      setProfile(result.profile); setStory('');
      setSaved('Сохранено для будущих текстов. Готовые посты не изменены.');
    } catch (reason) {
      if (generation.current === version) {
        setError(reason instanceof Error ? reason.message : 'Не удалось сохранить.');
        if (reason instanceof ContentAccessError) { setProfile(null); setBusiness(''); setAudience(''); setStory(''); setTone(''); setExample(''); }
      }
    } finally { if (generation.current === version) setBusy(false); }
  };
  const changeExample = async (id?: string) => {
    const version = generation.current;
    setBusy(true); setError('');
    try {
      await contentRequest(id ? '/content-voice/examples/' + encodeURIComponent(id) : '/content-voice/examples', {
        method: id ? 'DELETE' : 'POST', ...(!id ? { body: JSON.stringify({ business_id: businessId, text: example, origin: 'manual', quality_status: 'reference' }) } : {}),
      }, headers);
      const result = await contentRequest<{ profile: Profile }>(endpoint, undefined, headers);
      if (generation.current === version) { setProfile(result.profile); setExample(''); }
    } catch (reason) { if (generation.current === version) setError(reason instanceof Error ? reason.message : 'Не удалось сохранить пример.'); }
    finally { if (generation.current === version) setBusy(false); }
  };
  const knowledge = () => {
    onOpenChange(false);
    if (onOpenKnowledge) onOpenKnowledge();
    else window.location.assign('/dashboard/profile?section=knowledge&business_id=' + encodeURIComponent(businessId));
  };
  return <>
    <Dialog open={open && !references} onOpenChange={value => { if (!busy) onOpenChange(value); }}>
      <DialogContent className={`flex max-h-[90dvh] flex-col overflow-hidden text-foreground sm:max-w-xl ${headers ? 'dark' : ''}`}>
        <DialogHeader><DialogTitle>Настроить контент</DialogTitle><DialogDescription>Три коротких шага, чтобы тексты были похожи на вас и понятны вашим клиентам.</DialogDescription></DialogHeader>
        <Button id="content-references-button" variant="outline" disabled={busy} onClick={() => setReferences(true)}>Ориентиры для постов</Button>
        <Button variant="ghost" className="h-auto min-h-11 whitespace-normal" disabled={busy} onClick={knowledge}>Общие сведения и документы о бизнесе</Button>
        <nav aria-label="Шаги настройки контента" className="grid grid-cols-3 gap-2">{steps.map((label, index) => <Button key={label} className="h-auto min-h-11 min-w-0 whitespace-normal px-2 text-xs" variant={step === index ? 'default' : 'outline'} aria-current={step === index ? 'step' : undefined} disabled={busy} onClick={() => setStep(index)}>{label}</Button>)}</nav>
        {busy && !profile && <p role="status">Загружаем настройки…</p>}
        {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
        {saved && <p role="status" className="text-sm">{saved}</p>}
        {profile && <div className="min-h-0 flex-1 space-y-4 overflow-y-auto">
          {step === 0 && <>
            <label className="block space-y-2"><span>Что важно знать о бизнесе</span><Textarea disabled={busy} value={business} maxLength={6000} onChange={event => setBusiness(event.target.value)} placeholder="Чем занимаетесь, чем отличаетесь и что нельзя искажать в текстах" /></label>
            <label className="block space-y-2"><span>История основателя</span><Textarea disabled={busy} value={story} maxLength={6000} onChange={event => setStory(event.target.value)} placeholder="Добавьте реальный эпизод: почему открыли компанию, во что верите, что делаете лично" /></label>
            <p className="text-sm text-muted-foreground">История сохраняется как ваши сведения для контента. Примеры чужих компаний добавляйте в ориентиры.</p>
            {(profile.preferences?.editorial_notes || []).filter(note => note.kind === 'founder_story' || note.kind === 'company_fact').map(note => <p key={note.id} className="whitespace-pre-wrap border-l-2 pl-3 text-sm">{note.text}</p>)}
          </>}
          {step === 1 && <label className="block space-y-2"><span>Кто ваши клиенты</span><Textarea disabled={busy} value={audience} maxLength={6000} onChange={event => setAudience(event.target.value)} placeholder="Их ситуации, вопросы и причины выбрать вас" /></label>}
          {step === 2 && <>
            <label className="block space-y-2"><span>Как должны звучать тексты</span><Textarea disabled={busy} value={tone} maxLength={600} onChange={event => setTone(event.target.value)} placeholder="Например: конкретно, тепло, без рекламных вопросов" /></label>
            <details><summary className="min-h-11 cursor-pointer py-2">Примеры понравившихся постов · {profile.examples?.length || 0}</summary>
              <label className="block space-y-2"><span>Полный текст примера</span><Textarea disabled={busy} value={example} maxLength={12000} onChange={event => setExample(event.target.value)} /></label>
              <Button variant="outline" disabled={busy || example.trim().length < 20} onClick={() => void changeExample()}>Добавить пример</Button>
              {profile.examples?.map(item => <div key={item.id} className="border-b py-3"><p className="whitespace-pre-wrap text-sm">{item.text}</p><Button variant="ghost" disabled={busy} onClick={() => void changeExample(item.id)}>Удалить пример</Button></div>)}
            </details>
          </>}
        </div>}
        <DialogFooter className="shrink-0 border-t pt-3">
          {step > 0 ? <Button variant="outline" disabled={busy} onClick={() => setStep(step - 1)}>Назад</Button> : <Button variant="outline" disabled={busy} onClick={() => onOpenChange(false)}>Закрыть</Button>}
          {step < 2 ? <Button disabled={busy} onClick={() => setStep(step + 1)}>Дальше</Button> : <Button disabled={busy || !profile} onClick={() => void save()}>{busy ? 'Сохраняем…' : 'Сохранить'}</Button>}
        </DialogFooter>
      </DialogContent>
    </Dialog>
    <ContentReferences businessId={businessId} open={open && references} onOpenChange={setReferences} headers={headers} />
  </>;
}
