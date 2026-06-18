import { type ChangeEvent, type FormEvent, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { ArrowRight, ExternalLink, FileText, MessageSquare, Paperclip, Send } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { newAuth } from '@/lib/auth_new';

type SalesRoomAttachment = {
  id?: string;
  original_name?: string;
  mime_type?: string;
  size_bytes?: number;
  public_url?: string;
};

type SalesRoomMessage = {
  id?: string;
  author_type?: string;
  author_name?: string;
  author_contact?: string;
  body_text?: string;
  attachments?: SalesRoomAttachment[];
  created_at?: string;
};

type SalesRoomPayload = {
  slug?: string;
  public_url?: string;
  mode?: string;
  data_mode?: string;
  business?: {
    name?: string;
  };
  recipient?: {
    name?: string;
    category?: string;
    city?: string;
    address?: string;
    source_url?: string;
  };
  proposal?: {
    title?: string;
    summary?: string;
    body_text?: string;
    bullets?: string[];
    next_step?: string;
  };
  audit?: {
    available?: boolean;
    public_url?: string | null;
    summary_score?: number | null;
    health_label?: string;
    summary_text?: string;
    findings?: Array<{ title?: string; description?: string } | string>;
    recommended_actions?: Array<{ title?: string; description?: string } | string>;
  };
  match?: {
    available?: boolean;
    match_score?: number | null;
    score_explanation?: string;
    offer_angles?: string[];
    reason_codes?: string[];
  };
  cta?: {
    primary_label?: string;
    secondary_label?: string;
    secondary_url?: string | null;
  };
  localos?: {
    badge?: string;
    description?: string;
  };
  messages?: SalesRoomMessage[];
};

const roomModeLabel = (mode?: string) => {
  if (mode === 'partner_search') return 'Партнёрское предложение';
  if (mode === 'client_search') return 'Предложение по росту';
  return 'Предложение';
};

const formatFileSize = (size?: number) => {
  const normalized = Number(size || 0);
  if (!normalized) return '';
  if (normalized < 1024 * 1024) return `${Math.max(1, Math.round(normalized / 1024))} КБ`;
  return `${(normalized / 1024 / 1024).toFixed(1)} МБ`;
};

const formatDateTime = (value?: string) => {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
};

const roomAuthorNameKey = 'localos_sales_room_author_name';
const roomAuthorContactKey = 'localos_sales_room_author_contact';

export default function PublicSalesRoomPage() {
  const { roomSlug } = useParams<{ roomSlug: string }>();
  const [room, setRoom] = useState<SalesRoomPayload | null>(null);
  const [messages, setMessages] = useState<SalesRoomMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [composerError, setComposerError] = useState<string | null>(null);
  const [authorName, setAuthorName] = useState(() => localStorage.getItem(roomAuthorNameKey) || '');
  const [authorContact, setAuthorContact] = useState(() => localStorage.getItem(roomAuthorContactKey) || '');
  const [messageText, setMessageText] = useState('');
  const [pendingAttachments, setPendingAttachments] = useState<SalesRoomAttachment[]>([]);

  const loadRoom = async () => {
    if (!roomSlug) return;
    try {
      setLoading(true);
      setError(null);
      const response = await newAuth.makeRequest(`/sales-rooms/public/${encodeURIComponent(roomSlug)}`, {
        method: 'GET',
      });
      const nextRoom = response?.room || null;
      setRoom(nextRoom);
      setMessages(Array.isArray(nextRoom?.messages) ? nextRoom.messages : []);
    } catch (loadError) {
      const message = loadError instanceof Error ? loadError.message : 'Не удалось загрузить комнату';
      setError(message);
      setRoom(null);
      setMessages([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadRoom();
  }, [roomSlug]);

  useEffect(() => {
    if (!roomSlug || !room) return;
    void recordEvent('proposal_viewed', { source: 'public_page' });
  }, [roomSlug, room?.slug]);

  const recordEvent = async (eventType: string, metadata?: Record<string, unknown>) => {
    if (!roomSlug) return;
    try {
      await newAuth.makeRequest(`/sales-rooms/public/${encodeURIComponent(roomSlug)}/events`, {
        method: 'POST',
        body: JSON.stringify({ event_type: eventType, metadata: metadata || {} }),
      });
    } catch {
      // Public analytics should never block the recipient.
    }
  };

  const openAudit = () => {
    const url = room?.audit?.public_url || '';
    if (!url) return;
    void recordEvent('audit_open', { target: url });
    window.open(url, '_blank', 'noopener,noreferrer');
  };

  const handleUpload = async (event: ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(event.currentTarget.files || []);
    event.currentTarget.value = '';
    if (!roomSlug || selectedFiles.length === 0) return;
    setComposerError(null);
    setUploading(true);
    try {
      const uploaded: SalesRoomAttachment[] = [];
      for (const file of selectedFiles.slice(0, 5)) {
        const form = new FormData();
        form.append('file', file);
        const response = await fetch(`/api/sales-rooms/public/${encodeURIComponent(roomSlug)}/files`, {
          method: 'POST',
          body: form,
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data?.error || 'Не удалось загрузить файл');
        }
        if (data?.file) uploaded.push(data.file);
      }
      setPendingAttachments((current) => [...current, ...uploaded].slice(0, 5));
    } catch (uploadError) {
      const message = uploadError instanceof Error ? uploadError.message : 'Не удалось загрузить файл';
      setComposerError(message);
    } finally {
      setUploading(false);
    }
  };

  const sendMessage = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!roomSlug || sending) return;
    const cleanName = authorName.trim();
    const cleanContact = authorContact.trim();
    const cleanMessage = messageText.trim();
    if (!cleanName) {
      setComposerError('Укажите имя, чтобы было понятно, кто пишет.');
      return;
    }
    if (!cleanContact) {
      setComposerError('Оставьте контакт для ответа.');
      return;
    }
    if (!cleanMessage && pendingAttachments.length === 0) {
      setComposerError('Напишите сообщение или приложите файл.');
      return;
    }
    setSending(true);
    setComposerError(null);
    try {
      localStorage.setItem(roomAuthorNameKey, cleanName);
      localStorage.setItem(roomAuthorContactKey, cleanContact);
      const response = await newAuth.makeRequest(`/sales-rooms/public/${encodeURIComponent(roomSlug)}/messages`, {
        method: 'POST',
        body: JSON.stringify({
          author_name: cleanName,
          author_contact: cleanContact,
          body_text: cleanMessage,
          attachments: pendingAttachments,
        }),
      });
      if (response?.message) {
        setMessages((current) => [...current, response.message]);
      } else {
        await loadRoom();
      }
      setMessageText('');
      setPendingAttachments([]);
    } catch (sendError) {
      const message = sendError instanceof Error ? sendError.message : 'Не удалось отправить сообщение';
      setComposerError(message);
    } finally {
      setSending(false);
    }
  };

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
        <div className="rounded-xl border border-slate-200 bg-white px-5 py-4 text-sm text-slate-500 shadow-sm">
          Загружаем предложение...
        </div>
      </main>
    );
  }

  if (error || !room) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
        <div className="max-w-md rounded-2xl border border-slate-200 bg-white p-6 text-center shadow-sm">
          <div className="text-lg font-semibold text-slate-950">Комната не найдена</div>
          <p className="mt-2 text-sm leading-6 text-slate-500">{error || 'Ссылка устарела или была удалена.'}</p>
        </div>
      </main>
    );
  }

  const recipientName = room.recipient?.name || 'получатель';
  const businessName = room.business?.name || 'Компания';
  const hasAudit = Boolean(room.audit?.available && room.audit?.public_url);
  const proposalText =
    room.proposal?.body_text?.trim() ||
    room.proposal?.next_step?.trim() ||
    `Предлагаем обсудить формат сотрудничества между ${businessName} и ${recipientName} и согласовать следующий шаг.`;

  return (
    <main className="min-h-screen bg-[#f5f7fb] text-slate-950">
      <section className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6 lg:px-8 lg:py-10">
        <header className="flex flex-col gap-3 border-b border-slate-200 pb-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2 text-sm font-semibold text-slate-600">
              <span>{businessName}</span>
              <ArrowRight className="h-4 w-4 text-slate-400" />
              <span className="text-slate-950">{recipientName}</span>
            </div>
            <div className="mt-1 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">{roomModeLabel(room.mode)}</div>
          </div>
          <div className="w-fit rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-500 shadow-sm">
            Подготовлено в LocalOS
          </div>
        </header>

        <section className="mt-8 rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm sm:p-7 lg:p-8">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <div className="text-xs font-bold uppercase tracking-[0.2em] text-orange-500">Предложение</div>
              <h1 className="mt-3 text-2xl font-black leading-tight tracking-tight text-slate-950 sm:text-3xl">
                {room.proposal?.title || 'Предложение'}
              </h1>
            </div>
            {hasAudit ? (
              <Button variant="outline" className="shrink-0 gap-2" onClick={openAudit}>
                Открыть аудит
                <ExternalLink className="h-4 w-4" />
              </Button>
            ) : null}
          </div>

          <div className="mt-7 rounded-2xl border border-slate-100 bg-slate-50 px-4 py-5 sm:px-6 sm:py-6">
            <div className="whitespace-pre-wrap text-base leading-8 text-slate-800">{proposalText}</div>
          </div>
        </section>

        <form onSubmit={sendMessage} className="mt-6 rounded-[24px] border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
          <div className="flex items-center gap-2 text-sm font-bold text-slate-950">
            <MessageSquare className="h-4 w-4 text-orange-500" />
            Обсудить следующий шаг
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <Input
              value={authorName}
              onChange={(event) => setAuthorName(event.currentTarget.value)}
              placeholder="Ваше имя"
              autoComplete="name"
            />
            <Input
              value={authorContact}
              onChange={(event) => setAuthorContact(event.currentTarget.value)}
              placeholder="Email, телефон или Telegram"
              autoComplete="email"
            />
          </div>
          <Textarea
            value={messageText}
            onChange={(event) => setMessageText(event.currentTarget.value)}
            placeholder="Напишите, что уточнить, изменить или обсудить..."
            className="mt-3 min-h-28 resize-none"
          />

          {pendingAttachments.length > 0 ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {pendingAttachments.map((attachment) => (
                <button
                  key={attachment.id}
                  type="button"
                  onClick={() => setPendingAttachments((current) => current.filter((item) => item.id !== attachment.id))}
                  className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-medium text-slate-600"
                >
                  <FileText className="h-3.5 w-3.5" />
                  {attachment.original_name}
                </button>
              ))}
            </div>
          ) : null}

          {composerError ? <div className="mt-3 text-sm font-medium text-red-600">{composerError}</div> : null}

          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <label className="inline-flex cursor-pointer items-center gap-2 text-sm font-semibold text-slate-600 hover:text-slate-950">
              <Paperclip className="h-4 w-4" />
              {uploading ? 'Загружаем файл...' : 'Приложить файл'}
              <input
                type="file"
                className="hidden"
                multiple
                accept=".pdf,.doc,.docx,.xls,.xlsx,.csv,.txt,.png,.jpg,.jpeg,.webp"
                onChange={handleUpload}
                disabled={uploading || sending}
              />
            </label>
            <Button type="submit" className="gap-2 bg-slate-950 text-white hover:bg-slate-800" disabled={sending || uploading}>
              {sending ? 'Отправляем...' : 'Отправить'}
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </form>

        <section className="mt-6 rounded-[24px] border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-sm font-bold text-slate-950">История обсуждения</div>
              <p className="mt-1 text-sm text-slate-500">Сообщения и файлы по этому предложению.</p>
            </div>
            <div className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-500">{messages.length}</div>
          </div>

          {messages.length > 0 ? (
            <div className="mt-5 space-y-3">
              {messages.map((message) => (
                <article key={message.id} className="rounded-2xl border border-slate-100 bg-slate-50 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="font-semibold text-slate-950">{message.author_name || 'Гость'}</div>
                    <div className="text-xs font-medium text-slate-400">{formatDateTime(message.created_at)}</div>
                  </div>
                  {message.body_text ? <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-700">{message.body_text}</p> : null}
                  {Array.isArray(message.attachments) && message.attachments.length > 0 ? (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {message.attachments.map((attachment) => (
                        <a
                          key={attachment.id}
                          href={attachment.public_url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 hover:border-orange-200 hover:text-orange-600"
                        >
                          <FileText className="h-3.5 w-3.5" />
                          {attachment.original_name}
                          {formatFileSize(attachment.size_bytes) ? <span className="text-slate-400">{formatFileSize(attachment.size_bytes)}</span> : null}
                        </a>
                      ))}
                    </div>
                  ) : null}
                </article>
              ))}
            </div>
          ) : (
            <div className="mt-5 rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
              Пока нет сообщений. Начните обсуждение с вопроса, файла или правки к предложению.
            </div>
          )}
        </section>

        <footer className="px-2 py-8 text-sm leading-6 text-slate-500">
          Цифровая комната LocalOS. Подготовьте предложение и обсудите в одном месте.
        </footer>
      </section>
    </main>
  );
}
