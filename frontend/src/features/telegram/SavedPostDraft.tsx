import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { OperatorPhotoPreview } from '@/components/operator/OperatorPhotoGallery';
import { mobileAuthHeaders, mobileScopeQuery, readMobileJson } from '@/lib/mobileDataClient';
import type { MobileScope } from '@/components/telegram/ScopeProvider.logic';

type SavedDraft = { id:string; business_id:string; text:string; status:string; photos:{asset_id:string;name?:string}[] };
export const SavedPostDraft = ({draftId,scope}:{draftId:string;scope?:MobileScope}) => {
  const [draft,setDraft]=useState<SavedDraft|null>(null);
  const [error,setError]=useState('');
  const [loading,setLoading]=useState(true);
  const [retry,setRetry]=useState(0);
  const [copied,setCopied]=useState(false);
  const [copyError,setCopyError]=useState('');
  useEffect(()=>{
    const controller=new AbortController();
    const timer=window.setTimeout(()=>{setError('Не удалось загрузить черновик. Повторите попытку.');setLoading(false);controller.abort();},20000);
    setDraft(null);setError('');setCopyError('');setCopied(false);setLoading(true);
    fetch(`/api/operator/mobile/content/drafts/${encodeURIComponent(draftId)}?${mobileScopeQuery(scope)}`,{headers:mobileAuthHeaders(),signal:controller.signal})
      .then(readMobileJson<{draft:SavedDraft}>).then(result=>{if(!controller.signal.aborted)setDraft(result.draft);})
      .catch(reason=>{if(!controller.signal.aborted)setError(reason instanceof Error && reason.name!=='AbortError'?reason.message:'Не удалось загрузить черновик. Повторите попытку.');})
      .finally(()=>{window.clearTimeout(timer);if(!controller.signal.aborted)setLoading(false);});
    return()=>{window.clearTimeout(timer);controller.abort();};
  },[draftId,scope?.kind,scope?.id,retry]);
  if(loading&&!error)return <p role="status" className="text-sm text-muted-foreground">Открываю сохранённый черновик…</p>;
  if(error)return <div className="space-y-3"><p role="alert" className="text-sm text-destructive">{error}</p><Button variant="outline" onClick={()=>setRetry(value=>value+1)}>Повторить загрузку</Button></div>;
  if(!draft)return null;
  return <article className="space-y-4 rounded-2xl border border-border bg-card p-4 text-card-foreground">
    <div><h2 className="text-lg font-semibold">Черновик поста</h2><p className="text-sm text-muted-foreground">Сохранённый текст и выбранные фотографии. Публикация — отдельное действие.</p></div>
    <p className="whitespace-pre-wrap break-words text-sm leading-6">{draft.text}</p>
    {draft.photos.length?<div className="grid grid-cols-2 gap-3">{draft.photos.map((photo,index)=><OperatorPhotoPreview key={photo.asset_id} photo={photo} index={index} headers={mobileAuthHeaders}/>)}</div>:<p className="text-sm text-muted-foreground">Фото к этому черновику пока не выбрано.</p>}
    <Button className="w-full" onClick={()=>{void navigator.clipboard.writeText(draft.text).then(()=>setCopied(true)).catch(()=>setCopyError('Не удалось скопировать текст. Выделите его и скопируйте вручную.'));}}>{copied?'Текст скопирован':'Скопировать текст'}</Button>
    {copyError && <p role="alert" className="text-sm text-destructive">{copyError}</p>}
    <p className="text-sm text-muted-foreground">Чтобы выбрать день, вернитесь в чат с LocalOS и напишите: «Добавь этот черновик в план на 30 октября». Перед публикацией нужно отдельное подтверждение.</p>
  </article>;
};
