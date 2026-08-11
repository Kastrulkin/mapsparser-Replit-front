import { FormEvent, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { ChevronRight, FileSpreadsheet, MessageCircle, Upload } from 'lucide-react';

type FinanceCrmMobilePanelProps = {
  onOpenFileImport: () => void;
  onRequestCrm: (values: { crmName: string; crmUrl: string; contact: string; comment: string }) => Promise<void>;
  currentRequest?: { crm_name?: string; status?: string } | null;
};

const spring = { type: 'spring', duration: 0.3, bounce: 0 };

const requestStatusLabel = (status?: string) => {
  if (status === 'reviewing') return 'Изучаем подключение';
  if (status === 'planned') return 'Запланировано';
  if (status === 'connected') return 'Подключено';
  if (status === 'declined') return 'Пока не поддерживается';
  if (status === 'closed') return 'Запрос закрыт';
  return 'Запрос получен';
};

const FinanceCrmMobilePanel = ({ onOpenFileImport, onRequestCrm, currentRequest }: FinanceCrmMobilePanelProps) => {
  const [instructionOpen, setInstructionOpen] = useState(false);
  const [requestOpen, setRequestOpen] = useState(false);
  const [crmName, setCrmName] = useState('');
  const [crmUrl, setCrmUrl] = useState('');
  const [contact, setContact] = useState('');
  const [comment, setComment] = useState('');
  const [requestState, setRequestState] = useState<'idle' | 'pending' | 'success' | 'error'>('idle');
  const [requestError, setRequestError] = useState('');
  const submitRequest = async (event: FormEvent) => {
    event.preventDefault();
    if (!crmName.trim() || requestState === 'pending') return;
    setRequestState('pending'); setRequestError('');
    try {
      await onRequestCrm({ crmName: crmName.trim(), crmUrl: crmUrl.trim(), contact: contact.trim(), comment: comment.trim() });
      setRequestState('success');
    } catch (error) {
      setRequestState('error');
      setRequestError(error instanceof Error ? error.message : 'Не удалось отправить запрос. Попробуйте ещё раз.');
    }
  };

  return (
    <section className="overflow-hidden rounded-[24px] bg-white/[0.04] ring-1 ring-inset ring-white/[0.07]">
      <div className="p-4">
        <div className="flex items-start gap-3">
          <span className="grid h-11 w-11 shrink-0 place-items-center rounded-[15px] bg-primary/15 text-primary">
            <FileSpreadsheet className="h-5 w-5" />
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <b className="text-balance text-base">Загрузить данные из CRM</b>
              <span className="rounded-full bg-amber-400/10 px-2 py-1 text-[9px] font-semibold text-amber-200 ring-1 ring-inset ring-amber-300/15">Через файл</span>
            </div>
            <p className="mt-1 text-pretty text-xs leading-5 text-zinc-500">
              Загрузите выгрузку из любой CRM. ЛокалОС распознает структуру и попросит проверить только неоднозначные колонки.
            </p>
          </div>
        </div>

        <button
          type="button"
          aria-expanded={instructionOpen}
          onClick={() => setInstructionOpen((value) => !value)}
          className="mt-4 flex min-h-12 w-full items-center gap-3 rounded-[16px] bg-black/20 px-4 text-left ring-1 ring-inset ring-white/[0.07] active:scale-[0.96]"
        >
          <span className="min-w-0 flex-1">
            <b className="block text-sm">Как выгрузить файл</b>
            <small className="mt-1 block text-pretty text-[10px] leading-4 text-zinc-600">Как выгрузить CSV или Excel из вашей CRM</small>
          </span>
          <ChevronRight className={`h-4 w-4 shrink-0 text-zinc-600 transition-transform ${instructionOpen ? 'rotate-90' : ''}`} />
        </button>

        <AnimatePresence initial={false}>
          {instructionOpen ? (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={spring}
              className="overflow-hidden"
            >
              <ol className="mt-3 space-y-3 rounded-[18px] bg-black/20 p-4 ring-1 ring-inset ring-white/[0.06]">
                {[
                  ['Откройте отчёт', 'Найдите в CRM раздел с продажами, визитами или финансовыми отчётами.'],
                  ['Выберите период', 'Укажите нужные даты и добавьте в отчёт дату, сумму, услугу и сотрудника, если эти поля доступны.'],
                  ['Скачайте файл', 'Выберите CSV или Excel. Не объединяйте ячейки и не удаляйте названия столбцов.'],
                  ['Проверьте распознавание', 'Загрузите файл в ЛокалОС. Если названия колонок незнакомы, сопоставьте их вручную перед сохранением.'],
                ].map(([title, text], index) => (
                  <li key={title} className="flex gap-3">
                    <span className="grid h-7 w-7 shrink-0 place-items-center rounded-[10px] bg-primary/12 text-[11px] font-bold tabular-nums text-primary">{index + 1}</span>
                    <span className="min-w-0 pt-0.5">
                      <b className="block text-xs text-zinc-300">{title}</b>
                      <small className="mt-1 block text-pretty text-[10px] leading-4 text-zinc-600">{text}</small>
                    </span>
                  </li>
                ))}
              </ol>
            </motion.div>
          ) : null}
        </AnimatePresence>

        <button
          type="button"
          onClick={onOpenFileImport}
          className="mt-4 flex min-h-12 w-full items-center justify-center gap-2 rounded-[15px] bg-primary px-4 text-sm font-semibold shadow-[0_10px_28px_rgba(255,92,51,0.18)] active:scale-[0.96]"
        >
          <Upload className="h-4 w-4" />
          Загрузить файл из CRM
        </button>
      </div>

      <div className="border-t border-white/[0.06] p-4">
        <div className="flex items-start gap-3">
          <span className="grid h-11 w-11 shrink-0 place-items-center rounded-[15px] bg-white/[0.05] text-zinc-400">
            <MessageCircle className="h-5 w-5" />
          </span>
          <div className="min-w-0 flex-1">
            <b className="block text-sm">Нужно прямое подключение к CRM?</b>
            <p className="mt-1 text-pretty text-xs leading-5 text-zinc-600">Для загрузки файла подключение не нужно. Оставьте запрос, если хотите автоматическую синхронизацию.</p>
          </div>
        </div>
        {currentRequest && requestState !== 'success' ? <div className="mt-3 rounded-[15px] bg-sky-500/10 p-3 text-xs leading-5 text-sky-100 ring-1 ring-inset ring-sky-400/20"><b>{currentRequest.crm_name}</b> · {requestStatusLabel(currentRequest.status)}</div> : null}
        {requestState === 'success' ? <div role="status" className="mt-3 rounded-[15px] bg-emerald-500/10 p-3 text-xs leading-5 text-emerald-100 ring-1 ring-inset ring-emerald-400/20">Запрос отправлен. Мы учтём CRM и подскажем, когда появится подходящий способ загрузки.</div> : requestOpen ? (
          <form className="mt-3 space-y-2" onSubmit={(event) => void submitRequest(event)}>
            <label className="block text-[10px] font-medium text-zinc-500">Название CRM<input autoFocus value={crmName} onChange={(event) => { setCrmName(event.target.value); setRequestState('idle'); }} placeholder="Например, Bitrix24" className="mt-1 min-h-11 w-full rounded-[13px] bg-black/20 px-3 text-sm text-zinc-100 outline-none ring-1 ring-inset ring-white/[0.08] placeholder:text-zinc-700 focus:ring-primary/50" /></label>
            <label className="block text-[10px] font-medium text-zinc-500">Ссылка на CRM <span className="text-zinc-700">(необязательно)</span><input inputMode="url" value={crmUrl} onChange={(event) => setCrmUrl(event.target.value)} placeholder="https://..." className="mt-1 min-h-11 w-full rounded-[13px] bg-black/20 px-3 text-sm text-zinc-100 outline-none ring-1 ring-inset ring-white/[0.08] placeholder:text-zinc-700 focus:ring-primary/50" /></label>
            <label className="block text-[10px] font-medium text-zinc-500">Как связаться <span className="text-zinc-700">(необязательно)</span><input value={contact} onChange={(event) => setContact(event.target.value)} placeholder="Telegram, email или телефон" className="mt-1 min-h-11 w-full rounded-[13px] bg-black/20 px-3 text-sm text-zinc-100 outline-none ring-1 ring-inset ring-white/[0.08] placeholder:text-zinc-700 focus:ring-primary/50" /></label>
            <label className="block text-[10px] font-medium text-zinc-500">Что хотите загружать? <span className="text-zinc-700">(необязательно)</span><textarea value={comment} onChange={(event) => setComment(event.target.value)} rows={2} placeholder="Например, продажи за месяц" className="mt-1 w-full resize-none rounded-[13px] bg-black/20 px-3 py-2 text-sm text-zinc-100 outline-none ring-1 ring-inset ring-white/[0.08] placeholder:text-zinc-700 focus:ring-primary/50" /></label>
            {requestState === 'error' ? <p role="alert" className="text-xs leading-5 text-rose-200">{requestError}</p> : null}
            <button type="submit" disabled={!crmName.trim() || requestState === 'pending'} className="flex min-h-12 w-full items-center justify-center rounded-[15px] bg-white/[0.08] px-4 text-sm font-semibold text-zinc-100 ring-1 ring-inset ring-white/[0.08] transition-[background-color,transform] active:scale-[0.96] disabled:opacity-45">{requestState === 'pending' ? 'Отправляем запрос…' : 'Отправить запрос'}</button>
          </form>
        ) : <button type="button" onClick={() => setRequestOpen(true)} className="mt-3 min-h-12 w-full rounded-[15px] bg-white/[0.055] px-4 text-sm font-semibold text-zinc-200 ring-1 ring-inset ring-white/[0.08] transition-[background-color,transform] active:scale-[0.96]">Заказать подключение</button>}
      </div>
    </section>
  );
};

export default FinanceCrmMobilePanel;
