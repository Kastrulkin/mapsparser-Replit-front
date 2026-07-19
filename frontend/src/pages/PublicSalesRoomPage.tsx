import { type ChangeEvent, type FormEvent, useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { ArrowRight, Check, ExternalLink, FileText, MessageSquare, Paperclip, Pencil, Send, X } from 'lucide-react';
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

type SalesRoomProposalSuggestion = {
  id?: string;
  version_id?: string;
  suggestion_type?: 'replace' | 'comment' | string;
  selection_text?: string;
  selection_start?: number | null;
  selection_end?: number | null;
  replacement_text?: string;
  comment_text?: string;
  author_name?: string;
  author_contact?: string;
  status?: string;
  resolved_by_name?: string;
  resolved_by_contact?: string;
  resolved_at?: string;
  created_at?: string;
  updated_at?: string;
};

type SalesRoomProposalReview = {
  latest_version?: {
    id?: string;
    version_no?: number;
    body_text?: string;
    created_by_name?: string;
    created_at?: string;
  } | null;
  suggestions?: SalesRoomProposalSuggestion[];
};

type SalesRoomPayload = {
  slug?: string;
  public_url?: string;
  mode?: string;
  data_mode?: string;
  business?: {
    name?: string;
  };
  manager?: {
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
  welcome?: {
    body_text?: string;
  };
  permissions?: {
    can_edit_welcome?: boolean;
  };
  participant?: {
    id?: string;
    email?: string;
    name?: string;
    company?: string;
    verified?: boolean;
    verified_at?: string;
  };
  audit_offer?: SalesRoomAuditOffer | null;
  messages?: SalesRoomMessage[];
  proposal_review?: SalesRoomProposalReview;
};

type SalesRoomAuditOffer = {
  id?: string;
  status?: string;
  platform?: string;
  company_name?: string;
  company_address?: string;
  offer_title?: string;
  offer_text?: string;
  button_text?: string;
  prepared_audit_slug?: string | null;
  requires_registration?: boolean;
  requires_verification?: boolean;
  requested_at?: string;
  processing_started_at?: string;
  ready_at?: string;
  opened_at?: string;
  audit_url?: string | null;
  processing_delay_seconds?: number;
};

const roomModeLabel = (mode?: string) => {
  if (mode === 'partner_search') return 'Предложение партнёрства';
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
const roomAuthorCompanyKey = 'localos_sales_room_author_company';
const roomParticipantTokenKey = (slug?: string) => `localos_sales_room_participant_token_${slug || 'unknown'}`;
const roomAuditOfferDismissedKey = (slug?: string) => `localos_sales_room_audit_offer_dismissed_${slug || 'unknown'}`;
const fileUploadsVisible = true;
const defaultWelcomeText =
  'Рад знакомству. Я подготовил эту цифровую комнату, чтобы было проще обсуждать детали, подключать коллег и видеть всё в одном месте.\n\n' +
  'Ниже - актуальный документ. Можно оставить комментарий и предложить правку.\n\n' +
  'Если будут вопросы, напишите — всё сохраним в одном диалоге.';

const textOffsetInElement = (root: HTMLElement, targetNode: Node, targetOffset: number) => {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let offset = 0;
  let node = walker.nextNode();
  while (node) {
    const nodeText = node.textContent || '';
    if (node === targetNode) {
      return offset + targetOffset;
    }
    offset += nodeText.length;
    node = walker.nextNode();
  }
  return null;
};

const getSuggestionRange = (bodyText: string, suggestion: SalesRoomProposalSuggestion) => {
  if (suggestion.suggestion_type !== 'replace' || suggestion.status !== 'pending') return null;
  const selectionText = (suggestion.selection_text || '').trim();
  const replacementText = (suggestion.replacement_text || '').trim();
  if (!selectionText || !replacementText || !suggestion.id) return null;

  const start = typeof suggestion.selection_start === 'number' ? suggestion.selection_start : -1;
  const end = typeof suggestion.selection_end === 'number' ? suggestion.selection_end : -1;
  if (start >= 0 && end > start && bodyText.slice(start, end) === selectionText) {
    return { start, end, suggestion };
  }

  const fallbackStart = bodyText.indexOf(selectionText);
  if (fallbackStart >= 0) {
    return { start: fallbackStart, end: fallbackStart + selectionText.length, suggestion };
  }
  return null;
};

export default function PublicSalesRoomPage() {
  const { roomSlug } = useParams<{ roomSlug: string }>();
  const proposalRef = useRef<HTMLDivElement | null>(null);
  const [room, setRoom] = useState<SalesRoomPayload | null>(null);
  const [messages, setMessages] = useState<SalesRoomMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [composerError, setComposerError] = useState<string | null>(null);
  const [authorName, setAuthorName] = useState(() => localStorage.getItem(roomAuthorNameKey) || '');
  const [authorCompany, setAuthorCompany] = useState(() => localStorage.getItem(roomAuthorCompanyKey) || '');
  const [messageText, setMessageText] = useState('');
  const [pendingAttachments, setPendingAttachments] = useState<SalesRoomAttachment[]>([]);
  const [selectedText, setSelectedText] = useState('');
  const [selectedStart, setSelectedStart] = useState<number | null>(null);
  const [selectedEnd, setSelectedEnd] = useState<number | null>(null);
  const [reviewMode, setReviewMode] = useState<'replace' | 'comment'>('replace');
  const [replacementText, setReplacementText] = useState('');
  const [commentText, setCommentText] = useState('');
  const [reviewError, setReviewError] = useState<string | null>(null);
  const [submittingSuggestion, setSubmittingSuggestion] = useState(false);
  const [resolvingSuggestionId, setResolvingSuggestionId] = useState<string | null>(null);
  const [editingWelcome, setEditingWelcome] = useState(false);
  const [welcomeDraft, setWelcomeDraft] = useState('');
  const [savingWelcome, setSavingWelcome] = useState(false);
  const [welcomeError, setWelcomeError] = useState<string | null>(null);
  const [participantToken, setParticipantToken] = useState(() => localStorage.getItem(roomParticipantTokenKey(roomSlug)) || '');
  const [participantEmail, setParticipantEmail] = useState('');
  const [participantBusy, setParticipantBusy] = useState(false);
  const [participantMessage, setParticipantMessage] = useState<string | null>(null);
  const [participantError, setParticipantError] = useState<string | null>(null);
  const [participantConsent, setParticipantConsent] = useState(false);
  const [auditOfferBusy, setAuditOfferBusy] = useState(false);
  const [auditOfferError, setAuditOfferError] = useState<string | null>(null);
  const [auditOfferDismissed, setAuditOfferDismissed] = useState(() => localStorage.getItem(roomAuditOfferDismissedKey(roomSlug)) === '1');

  const updateAuthorName = (value: string) => {
    setAuthorName(value);
    localStorage.setItem(roomAuthorNameKey, value);
  };

  const updateAuthorCompany = (value: string) => {
    setAuthorCompany(value);
    localStorage.setItem(roomAuthorCompanyKey, value);
  };

  const loadRoom = async () => {
    if (!roomSlug) return;
    try {
      setLoading(true);
      setError(null);
      const headers: Record<string, string> = {};
      if (participantToken) {
        headers['X-Sales-Room-Participant-Token'] = participantToken;
      }
      const selectedBusinessId = localStorage.getItem('selectedBusinessId') || '';
      if (selectedBusinessId) {
        headers['X-LocalOS-Current-Business-Id'] = selectedBusinessId;
      }
      const response = await newAuth.makeRequest(`/sales-rooms/public/${encodeURIComponent(roomSlug)}`, {
        method: 'GET',
        headers,
      });
      const nextRoom = response?.room || null;
      setRoom(nextRoom);
      setMessages(Array.isArray(nextRoom?.messages) ? nextRoom.messages : []);
      setWelcomeDraft(String(nextRoom?.welcome?.body_text || defaultWelcomeText));
      if (nextRoom?.participant?.email) {
        setParticipantEmail(String(nextRoom.participant.email || ''));
      }
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
  }, [roomSlug, participantToken]);

  useEffect(() => {
    setParticipantToken(localStorage.getItem(roomParticipantTokenKey(roomSlug)) || '');
    setAuditOfferDismissed(localStorage.getItem(roomAuditOfferDismissedKey(roomSlug)) === '1');
  }, [roomSlug]);

  useEffect(() => {
    if (!roomSlug) return;
    const params = new URLSearchParams(window.location.search);
    const verifyToken = params.get('verify_token') || '';
    const urlParticipantToken = params.get('participant_token') || '';
    if (!verifyToken) return;
    void verifyParticipantFromUrl(verifyToken, urlParticipantToken);
  }, [roomSlug]);

  useEffect(() => {
    if (!roomSlug || !participantToken || room?.audit_offer?.status !== 'processing') return;
    const timer = window.setInterval(() => {
      void refreshAuditOfferStatus();
    }, 5000);
    return () => window.clearInterval(timer);
  }, [roomSlug, participantToken, room?.audit_offer?.status]);

  const participantHeaders = () => {
    const headers: Record<string, string> = {};
    if (participantToken) {
      headers['X-Sales-Room-Participant-Token'] = participantToken;
    }
    return headers;
  };

  const verifyParticipantFromUrl = async (verificationToken: string, tokenFromUrl: string) => {
    if (!roomSlug || !verificationToken) return;
    setParticipantBusy(true);
    setParticipantError(null);
    try {
      const response = await newAuth.makeRequest(`/sales-rooms/public/${encodeURIComponent(roomSlug)}/participants/verify`, {
        method: 'POST',
        body: JSON.stringify({
          verification_token: verificationToken,
          participant_token: tokenFromUrl || participantToken,
        }),
      });
      const nextToken = String(response?.participant_token || tokenFromUrl || participantToken || '');
      if (nextToken) {
        localStorage.setItem(roomParticipantTokenKey(roomSlug), nextToken);
        setParticipantToken(nextToken);
      }
      setParticipantMessage('Email подтверждён.');
      const cleanUrl = `${window.location.pathname}${window.location.hash || ''}`;
      window.history.replaceState({}, '', cleanUrl);
      await loadRoom();
    } catch (verifyError) {
      const message = verifyError instanceof Error ? verifyError.message : 'Не удалось подтвердить email';
      setParticipantError(message);
    } finally {
      setParticipantBusy(false);
    }
  };

  const registerParticipant = async () => {
    if (!roomSlug || participantBusy) return;
    const cleanEmail = participantEmail.trim();
    if (!cleanEmail) {
      setParticipantError('Укажите email.');
      return;
    }
    if (!participantConsent) {
      setParticipantError('Нужно согласие на обработку персональных данных.');
      return;
    }
    setParticipantBusy(true);
    setParticipantError(null);
    setParticipantMessage(null);
    try {
      const response = await newAuth.makeRequest(`/sales-rooms/public/${encodeURIComponent(roomSlug)}/participants`, {
        method: 'POST',
        body: JSON.stringify({
          email: cleanEmail,
          name: authorName.trim(),
          company: authorCompany.trim(),
          personal_data_consent: participantConsent,
          consent_version: 'localos-personal-data-v1-2026-05-11',
        }),
      });
      const nextToken = String(response?.participant_token || '');
      if (nextToken) {
        localStorage.setItem(roomParticipantTokenKey(roomSlug), nextToken);
        setParticipantToken(nextToken);
      }
      setParticipantMessage(response?.verification_required ? 'Отправили письмо для подтверждения email.' : 'Email уже подтверждён.');
      await loadRoom();
    } catch (registerError) {
      const message = registerError instanceof Error ? registerError.message : 'Не удалось отправить письмо подтверждения';
      setParticipantError(message);
    } finally {
      setParticipantBusy(false);
    }
  };

  const setAuditOffer = (auditOffer: SalesRoomAuditOffer | null) => {
    setRoom((current) => {
      if (!current) return current;
      return {
        ...current,
        audit_offer: auditOffer,
      };
    });
  };

  const requestAuditOffer = async () => {
    if (!roomSlug || auditOfferBusy) return;
    setAuditOfferBusy(true);
    setAuditOfferError(null);
    try {
      const response = await newAuth.makeRequest(`/sales-rooms/public/${encodeURIComponent(roomSlug)}/audit-offer/request`, {
        method: 'POST',
        headers: participantHeaders(),
      });
      setAuditOffer(response?.audit_offer || null);
      setAuditOfferDismissed(false);
      localStorage.removeItem(roomAuditOfferDismissedKey(roomSlug));
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : 'Не удалось запросить аудит';
      setAuditOfferError(message);
    } finally {
      setAuditOfferBusy(false);
    }
  };

  const refreshAuditOfferStatus = async () => {
    if (!roomSlug || !participantToken) return;
    try {
      const response = await newAuth.makeRequest(`/sales-rooms/public/${encodeURIComponent(roomSlug)}/audit-offer/status`, {
        method: 'GET',
        headers: participantHeaders(),
      });
      setAuditOffer(response?.audit_offer || null);
    } catch {
      // Status polling should stay quiet for the recipient.
    }
  };

  const dismissAuditOffer = () => {
    setAuditOfferDismissed(true);
    if (roomSlug) {
      localStorage.setItem(roomAuditOfferDismissedKey(roomSlug), '1');
    }
    void recordEvent('audit_offer_dismissed', { source: 'public_page' });
  };

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

  const openAuditOffer = async () => {
    const url = room?.audit_offer?.audit_url || '';
    if (!url || !roomSlug) return;
    try {
      await newAuth.makeRequest(`/sales-rooms/public/${encodeURIComponent(roomSlug)}/audit-offer/opened`, {
        method: 'POST',
        headers: participantHeaders(),
      });
    } catch {
      // Opening the ready audit should not be blocked by analytics.
    }
    window.open(url, '_blank', 'noopener,noreferrer');
    await refreshAuditOfferStatus();
  };

  const saveWelcome = async () => {
    if (!roomSlug || savingWelcome) return;
    const cleanText = welcomeDraft.trim();
    if (!cleanText) {
      setWelcomeError('Напишите приветствие.');
      return;
    }
    setSavingWelcome(true);
    setWelcomeError(null);
    try {
      const response = await newAuth.makeRequest(`/sales-rooms/public/${encodeURIComponent(roomSlug)}/welcome`, {
        method: 'PATCH',
        body: JSON.stringify({ body_text: cleanText }),
      });
      const nextWelcome = response?.welcome || { body_text: cleanText };
      setRoom((current) => {
        if (!current) return current;
        return {
          ...current,
          welcome: {
            ...(current.welcome || {}),
            body_text: String(nextWelcome.body_text || cleanText),
          },
        };
      });
      setWelcomeDraft(String(nextWelcome.body_text || cleanText));
      setEditingWelcome(false);
    } catch (saveError) {
      const message = saveError instanceof Error ? saveError.message : 'Не удалось сохранить приветствие';
      setWelcomeError(message);
    } finally {
      setSavingWelcome(false);
    }
  };

  const captureProposalSelection = () => {
    const root = proposalRef.current;
    const selection = window.getSelection();
    if (!root || !selection || selection.rangeCount === 0) return;
    const range = selection.getRangeAt(0);
    if (range.collapsed || !root.contains(range.commonAncestorContainer)) return;
    const text = selection.toString().trim();
    if (!text) return;
    const start = textOffsetInElement(root, range.startContainer, range.startOffset);
    const end = textOffsetInElement(root, range.endContainer, range.endOffset);
    setSelectedText(text);
    setSelectedStart(start);
    setSelectedEnd(end);
    setReplacementText(text);
    setReviewError(null);
  };

  const clearProposalSelection = () => {
    setSelectedText('');
    setSelectedStart(null);
    setSelectedEnd(null);
    setReplacementText('');
    setCommentText('');
    setReviewError(null);
    window.getSelection()?.removeAllRanges();
  };

  const submitProposalSuggestion = async () => {
    if (!roomSlug || submittingSuggestion) return;
    const cleanName = authorName.trim();
    const cleanCompany = authorCompany.trim();
    const cleanSelection = selectedText.trim();
    const cleanReplacement = replacementText.trim();
    const cleanComment = commentText.trim();
    if (!cleanName || !cleanCompany) {
      setReviewError('Укажите имя и компанию под приветствием, чтобы было понятно, кто предложил правку.');
      return;
    }
    if (!cleanSelection) {
      setReviewError('Сначала выделите фрагмент предложения.');
      return;
    }
    if (reviewMode === 'replace' && !cleanReplacement) {
      setReviewError('Напишите вариант замены.');
      return;
    }
    if (reviewMode === 'comment' && !cleanComment) {
      setReviewError('Напишите комментарий.');
      return;
    }
    setSubmittingSuggestion(true);
    setReviewError(null);
    try {
      localStorage.setItem(roomAuthorNameKey, cleanName);
      localStorage.setItem(roomAuthorCompanyKey, cleanCompany);
      await newAuth.makeRequest(`/sales-rooms/public/${encodeURIComponent(roomSlug)}/proposal/suggestions`, {
        method: 'POST',
        body: JSON.stringify({
          author_name: cleanName,
          author_contact: cleanCompany,
          suggestion_type: reviewMode,
          selection_text: cleanSelection,
          selection_start: selectedStart,
          selection_end: selectedEnd,
          replacement_text: reviewMode === 'replace' ? cleanReplacement : '',
          comment_text: reviewMode === 'comment' ? cleanComment : '',
        }),
      });
      clearProposalSelection();
      await loadRoom();
    } catch (suggestionError) {
      const message = suggestionError instanceof Error ? suggestionError.message : 'Не удалось сохранить правку';
      setReviewError(message);
    } finally {
      setSubmittingSuggestion(false);
    }
  };

  const resolveProposalSuggestion = async (suggestion: SalesRoomProposalSuggestion, action: 'accept' | 'reject') => {
    if (!roomSlug || !suggestion.id || resolvingSuggestionId) return;
    const cleanName = authorName.trim();
    const cleanCompany = authorCompany.trim();
    if (!cleanName || !cleanCompany) {
      setReviewError('Укажите имя и компанию под приветствием, чтобы принять или отклонить правку.');
      return;
    }
    setResolvingSuggestionId(suggestion.id);
    setReviewError(null);
    try {
      await newAuth.makeRequest(`/sales-rooms/public/${encodeURIComponent(roomSlug)}/proposal/suggestions/${encodeURIComponent(suggestion.id)}/resolve`, {
        method: 'POST',
        body: JSON.stringify({
          action,
          author_name: cleanName,
          author_contact: cleanCompany,
        }),
      });
      await loadRoom();
    } catch (resolveError) {
      const message = resolveError instanceof Error ? resolveError.message : 'Не удалось обновить правку';
      setReviewError(message);
    } finally {
      setResolvingSuggestionId(null);
    }
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
    const cleanCompany = authorCompany.trim();
    const cleanMessage = messageText.trim();
    if (!cleanName) {
      setComposerError('Укажите имя, чтобы было понятно, кто пишет.');
      return;
    }
    if (!cleanCompany) {
      setComposerError('Укажите компанию.');
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
      localStorage.setItem(roomAuthorCompanyKey, cleanCompany);
      const response = await newAuth.makeRequest(`/sales-rooms/public/${encodeURIComponent(roomSlug)}/messages`, {
        method: 'POST',
        body: JSON.stringify({
          author_name: cleanName,
          author_contact: cleanCompany,
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
  const managerName = room.manager?.name?.trim() || 'Александр Демьянов';
  const managerInitial = managerName.trim().charAt(0).toUpperCase();
  const welcomeText = String(room.welcome?.body_text || defaultWelcomeText);
  const canEditWelcome = Boolean(room.permissions?.can_edit_welcome);
  const auditOffer = room.audit_offer || null;
  const participantVerified = Boolean(room.participant?.verified);
  const hasAudit = Boolean(!auditOffer && room.audit?.available && room.audit?.public_url);
  const auditOfferReady = Boolean(auditOffer?.audit_url && (auditOffer.status === 'ready' || auditOffer.status === 'opened'));
  const auditOfferProcessing = auditOffer?.status === 'processing' || auditOffer?.status === 'requested';
  const auditOfferInitial = Boolean(auditOffer && !auditOfferDismissed && !auditOfferProcessing && !auditOfferReady);
  const auditOfferRegisterUrl = auditOffer?.prepared_audit_slug
    ? `/login?tab=register&source=sales_room&audit_slug=${encodeURIComponent(auditOffer.prepared_audit_slug)}&business_name=${encodeURIComponent(
        auditOffer.company_name || recipientName,
      )}&business_address=${encodeURIComponent(auditOffer.company_address || room.recipient?.address || '')}&business_city=${encodeURIComponent(room.recipient?.city || '')}`
    : '';
  const proposalText =
    room.proposal?.body_text?.trim() ||
    room.proposal?.next_step?.trim() ||
    `Предлагаем обсудить формат сотрудничества между ${businessName} и ${recipientName} и согласовать следующий шаг.`;
  const suggestions = Array.isArray(room.proposal_review?.suggestions) ? room.proposal_review.suggestions : [];
  const pendingSuggestions = suggestions.filter((suggestion) => suggestion.status === 'pending');
  const resolvedSuggestions = suggestions.filter((suggestion) => suggestion.status !== 'pending').slice(0, 6);
  const latestVersionNo = room.proposal_review?.latest_version?.version_no || 1;
  const inlineReplacementRanges = pendingSuggestions
    .map((suggestion) => getSuggestionRange(proposalText, suggestion))
    .filter((range): range is { start: number; end: number; suggestion: SalesRoomProposalSuggestion } => Boolean(range))
    .sort((left, right) => left.start - right.start)
    .filter((range, index, ranges) => index === 0 || range.start >= ranges[index - 1].end);

  const renderProposalWithInlineSuggestions = () => {
    if (inlineReplacementRanges.length === 0) return proposalText;
    const fragments: Array<string | JSX.Element> = [];
    let cursor = 0;
    inlineReplacementRanges.forEach((range) => {
      if (range.start > cursor) {
        fragments.push(proposalText.slice(cursor, range.start));
      }
      const originalText = proposalText.slice(range.start, range.end);
      fragments.push(
        <span key={range.suggestion.id} className="mx-0.5 inline-flex max-w-full flex-col align-baseline">
          <span className="rounded-lg border border-orange-200 bg-orange-50 px-2 py-1 text-sm font-semibold leading-6 text-orange-700">
            {range.suggestion.replacement_text}
          </span>
          <span className="mt-0.5 text-slate-400 line-through decoration-orange-500 decoration-2">{originalText}</span>
          <span className="mt-1 inline-flex flex-wrap gap-1">
            <button
              type="button"
              className="rounded-full bg-orange-500 px-2 py-0.5 text-xs font-semibold leading-5 text-white hover:bg-orange-600 disabled:opacity-60"
              onClick={() => void resolveProposalSuggestion(range.suggestion, 'accept')}
              disabled={resolvingSuggestionId === range.suggestion.id}
            >
              Принять
            </button>
            <button
              type="button"
              className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-xs font-semibold leading-5 text-slate-600 hover:border-slate-300 hover:text-slate-900 disabled:opacity-60"
              onClick={() => void resolveProposalSuggestion(range.suggestion, 'reject')}
              disabled={resolvingSuggestionId === range.suggestion.id}
            >
              Отклонить
            </button>
          </span>
        </span>,
      );
      cursor = range.end;
    });
    if (cursor < proposalText.length) {
      fragments.push(proposalText.slice(cursor));
    }
    return fragments;
  };

  return (
    <main className="min-h-screen bg-[#f5f7fb] text-slate-950">
      <section className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6 lg:px-8 lg:py-10">
        <header className="border-b border-slate-200 pb-5">
          <div>
            <div className="flex flex-wrap items-center gap-2 text-sm font-semibold text-slate-600">
              <span>{businessName}</span>
              <ArrowRight className="h-4 w-4 text-slate-400" />
              <span className="text-slate-950">{recipientName}</span>
            </div>
            <div className="mt-1 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">{roomModeLabel(room.mode)}</div>
          </div>
        </header>

        <section className="mt-8 overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-sm">
          <div className="grid lg:grid-cols-[280px_1fr]">
            <aside className="flex flex-col items-center justify-center border-b border-slate-100 bg-slate-50/60 px-6 py-8 text-center lg:border-b-0 lg:border-r">
              <div className="flex h-24 w-24 items-center justify-center rounded-full bg-slate-900 text-4xl font-semibold text-white">
                {managerInitial}
              </div>
              <div className="mt-5 text-xl font-black tracking-tight text-slate-950">{managerName}</div>
            </aside>
            <div className="px-5 py-7 sm:px-8 lg:px-10">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="text-2xl font-black tracking-tight text-slate-950">Здравствуйте.</div>
                {canEditWelcome ? (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="gap-2"
                    onClick={() => {
                      setWelcomeDraft(welcomeText);
                      setWelcomeError(null);
                      setEditingWelcome((current) => !current);
                    }}
                  >
                    <Pencil className="h-4 w-4" />
                    {editingWelcome ? 'Закрыть' : 'Править'}
                  </Button>
                ) : null}
              </div>
              {editingWelcome && canEditWelcome ? (
                <div className="mt-5 max-w-2xl">
                  <Textarea
                    value={welcomeDraft}
                    onChange={(event) => setWelcomeDraft(event.currentTarget.value)}
                    className="min-h-44 resize-y bg-white text-base leading-7"
                    maxLength={1200}
                  />
                  {welcomeError ? <div className="mt-3 text-sm font-medium text-red-600">{welcomeError}</div> : null}
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button type="button" size="sm" onClick={saveWelcome} disabled={savingWelcome}>
                      {savingWelcome ? 'Сохраняем...' : 'Сохранить'}
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        setWelcomeDraft(welcomeText);
                        setWelcomeError(null);
                        setEditingWelcome(false);
                      }}
                    >
                      Отмена
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="mt-5 max-w-2xl space-y-4 text-base leading-8 text-slate-700">
                  {welcomeText.split(/\n{2,}/).map((paragraph, index) => (
                    <p key={`${index}-${paragraph.slice(0, 12)}`}>{paragraph}</p>
                  ))}
                </div>
              )}
              <div className="mt-6 max-w-2xl rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="text-sm font-bold text-slate-950">Представьтесь для правок и сообщений</div>
                <p className="mt-1 text-sm leading-6 text-slate-500">
                  Имя и компания будут видны рядом с вашими комментариями, правками и файлами.
                </p>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <Input
                    value={authorName}
                    onChange={(event) => updateAuthorName(event.currentTarget.value)}
                    placeholder="Ваше имя"
                    autoComplete="name"
                  />
                  <Input
                    value={authorCompany}
                    onChange={(event) => updateAuthorCompany(event.currentTarget.value)}
                    placeholder="Компания"
                    autoComplete="organization"
                  />
                </div>
              </div>
              <div className="mt-4 max-w-2xl rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <div className="text-sm font-bold text-slate-950">Добавьте email для уведомлений</div>
                    <p className="mt-1 text-sm leading-6 text-slate-500">
                      Чтобы получать уведомления о новых комментариях и доступных действиях в комнате, добавьте адрес почты.
                    </p>
                  </div>
                  {participantVerified ? (
                    <span className="inline-flex rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">Подтверждён</span>
                  ) : null}
                </div>
                {!participantVerified ? (
                  <div className="mt-3 space-y-3">
                    <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
                      <Input
                        value={participantEmail}
                        onChange={(event) => setParticipantEmail(event.currentTarget.value)}
                        placeholder="email@company.ru"
                        autoComplete="email"
                        type="email"
                      />
                      <Button type="button" onClick={registerParticipant} disabled={participantBusy || !participantConsent}>
                        {participantBusy ? 'Отправляем...' : 'Подтвердить email'}
                      </Button>
                    </div>
                    <label className="flex items-start gap-2 text-xs leading-5 text-slate-600">
                      <input
                        type="checkbox"
                        className="mt-1 h-4 w-4 rounded border-slate-300"
                        checked={participantConsent}
                        onChange={(event) => setParticipantConsent(event.currentTarget.checked)}
                      />
                      <span>
                        Я согласен на обработку персональных данных и принимаю{' '}
                        <a href="/privacy" target="_blank" rel="noreferrer" className="font-semibold text-slate-900 underline underline-offset-2">
                          политику обработки персональных данных
                        </a>
                        .
                      </span>
                    </label>
                  </div>
                ) : (
                  <div className="mt-3 text-sm font-medium text-slate-700">{room.participant?.email}</div>
                )}
                {participantMessage ? <div className="mt-3 text-sm font-medium text-emerald-700">{participantMessage}</div> : null}
                {participantError ? <div className="mt-3 text-sm font-medium text-red-600">{participantError}</div> : null}
              </div>
            </div>
          </div>
        </section>

        <section className="mt-8 rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm sm:p-7 lg:p-8">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <div className="text-xs font-bold uppercase tracking-[0.2em] text-orange-500">Предложение</div>
            </div>
            {hasAudit ? (
              <Button variant="outline" className="shrink-0 gap-2" onClick={openAudit}>
                Открыть аудит
                <ExternalLink className="h-4 w-4" />
              </Button>
            ) : null}
          </div>

          {auditOfferInitial ? (
            <div className="mt-6 rounded-2xl border border-orange-100 bg-orange-50/70 p-5">
              <div className="text-xs font-bold uppercase tracking-[0.18em] text-orange-500">LocalOS</div>
              <h2 className="mt-2 text-xl font-black tracking-tight text-slate-950">
                {auditOffer?.offer_title || 'Проверьте, как ваша компания выглядит на Яндекс Картах'}
              </h2>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-700">
                {auditOffer?.offer_text || 'LocalOS может создать короткий аудит вашей карточки: фото, отзывы, описание, услуги и видимость рядом с конкурентами.'}
              </p>
              {auditOfferError ? <div className="mt-3 text-sm font-semibold text-red-600">{auditOfferError}</div> : null}
              <div className="mt-4 flex flex-wrap gap-2">
                <Button type="button" className="bg-slate-950 text-white hover:bg-slate-800" onClick={requestAuditOffer} disabled={auditOfferBusy || !participantVerified}>
                  {auditOfferBusy ? 'Запускаем...' : auditOffer?.button_text || 'Создать аудит карточки'}
                </Button>
                {auditOfferRegisterUrl ? (
                  <Button type="button" variant="outline" onClick={() => window.open(auditOfferRegisterUrl, '_self')}>
                    Зарегистрироваться и забрать аудит
                  </Button>
                ) : null}
                <Button type="button" variant="ghost" onClick={dismissAuditOffer}>
                  Не сейчас
                </Button>
              </div>
              {!participantVerified ? (
                <div className="mt-3 text-sm text-slate-500">Подтвердите email выше, чтобы запросить аудит.</div>
              ) : null}
            </div>
          ) : null}

          {auditOfferProcessing ? (
            <div className="mt-6 rounded-2xl border border-slate-200 bg-slate-50 p-5">
              <div className="text-xl font-black tracking-tight text-slate-950">Аудит создаётся</div>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-700">
                Мы проверяем карточку компании, отзывы, фото, услуги и видимость на картах. Когда аудит будет готов, отправим ссылку на вашу почту.
              </p>
              <div className="mt-3 text-sm font-semibold text-slate-500">Обычно занимает 2–3 минуты.</div>
              {auditOfferError ? <div className="mt-3 text-sm font-semibold text-red-600">{auditOfferError}</div> : null}
            </div>
          ) : null}

          {auditOfferReady ? (
            <div className="mt-6 rounded-2xl border border-emerald-100 bg-emerald-50 p-5">
              <div className="text-xl font-black tracking-tight text-slate-950">Аудит готов. Мы отправили ссылку на вашу почту.</div>
              <Button type="button" className="mt-4 gap-2 bg-slate-950 text-white hover:bg-slate-800" onClick={openAuditOffer}>
                Открыть аудит
                <ExternalLink className="h-4 w-4" />
              </Button>
            </div>
          ) : null}

          <div className="mt-7 rounded-2xl border border-slate-100 bg-slate-50 px-4 py-5 sm:px-6 sm:py-6">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-3">
              <div className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">Версия {latestVersionNo}</div>
              <div className="text-xs text-slate-500">Выделите текст, чтобы предложить правку или оставить комментарий.</div>
            </div>
            <div
              ref={proposalRef}
              onMouseUp={captureProposalSelection}
              onKeyUp={captureProposalSelection}
              className="whitespace-pre-wrap text-base leading-8 text-slate-800 selection:bg-orange-100"
            >
              {renderProposalWithInlineSuggestions()}
            </div>
          </div>

          {selectedText ? (
            <div className="mt-4 rounded-2xl border border-orange-100 bg-orange-50/60 p-4">
              <div className="text-xs font-bold uppercase tracking-[0.16em] text-orange-500">Выбранный фрагмент</div>
              <div className="mt-2 rounded-xl bg-white px-3 py-2 text-sm leading-6 text-slate-700">{selectedText}</div>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button type="button" size="sm" variant={reviewMode === 'replace' ? 'default' : 'outline'} onClick={() => setReviewMode('replace')}>
                  Предложить правку
                </Button>
                <Button type="button" size="sm" variant={reviewMode === 'comment' ? 'default' : 'outline'} onClick={() => setReviewMode('comment')}>
                  Комментарий
                </Button>
              </div>
              {reviewMode === 'replace' ? (
                <Textarea
                  value={replacementText}
                  onChange={(event) => setReplacementText(event.currentTarget.value)}
                  className="mt-3 min-h-24 bg-white"
                  placeholder="Напишите новый вариант этого фрагмента"
                />
              ) : (
                <Textarea
                  value={commentText}
                  onChange={(event) => setCommentText(event.currentTarget.value)}
                  className="mt-3 min-h-24 bg-white"
                  placeholder="Напишите комментарий к выбранному фрагменту"
                />
              )}
              {reviewError ? <div className="mt-3 text-sm font-medium text-red-600">{reviewError}</div> : null}
              <div className="mt-3 flex flex-wrap gap-2">
                <Button type="button" size="sm" onClick={submitProposalSuggestion} disabled={submittingSuggestion}>
                  {submittingSuggestion ? 'Сохраняем...' : 'Сохранить'}
                </Button>
                <Button type="button" size="sm" variant="ghost" onClick={clearProposalSelection}>
                  Отмена
                </Button>
              </div>
            </div>
          ) : reviewError ? (
            <div className="mt-4 rounded-2xl border border-red-100 bg-red-50 px-4 py-3 text-sm font-medium text-red-600">{reviewError}</div>
          ) : null}

          {suggestions.length > 0 ? (
            <div className="mt-6 grid gap-4 lg:grid-cols-2">
              <div className="rounded-2xl border border-slate-100 bg-white p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="text-sm font-bold text-slate-950">Ожидают решения</div>
                  <div className="rounded-full bg-orange-50 px-2.5 py-1 text-xs font-semibold text-orange-600">{pendingSuggestions.length}</div>
                </div>
                <div className="mt-4 space-y-3">
                  {pendingSuggestions.length > 0 ? (
                    pendingSuggestions.map((suggestion) => (
                      <article key={suggestion.id} className="rounded-xl border border-slate-100 bg-slate-50 p-3">
                        <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
                          {suggestion.suggestion_type === 'comment' ? 'Комментарий' : 'Правка'} от {suggestion.author_name || 'Гость'}
                          {suggestion.author_contact ? ` · ${suggestion.author_contact}` : ''}
                        </div>
                        <div className="mt-2 rounded-lg bg-white px-3 py-2 text-sm leading-6 text-slate-500 line-through decoration-orange-500 decoration-2">
                          {suggestion.selection_text}
                        </div>
                        {suggestion.suggestion_type === 'replace' ? (
                          <div className="mt-2 rounded-lg border border-orange-100 bg-orange-50 px-3 py-2 text-sm font-semibold leading-6 text-orange-700">
                            {suggestion.replacement_text}
                          </div>
                        ) : (
                          <div className="mt-2 text-sm leading-6 text-slate-700">{suggestion.comment_text}</div>
                        )}
                        <div className="mt-3 flex flex-wrap gap-2">
                          <Button
                            type="button"
                            size="sm"
                            className="gap-1"
                            onClick={() => void resolveProposalSuggestion(suggestion, 'accept')}
                            disabled={resolvingSuggestionId === suggestion.id}
                          >
                            <Check className="h-3.5 w-3.5" />
                            Принять
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            className="gap-1"
                            onClick={() => void resolveProposalSuggestion(suggestion, 'reject')}
                            disabled={resolvingSuggestionId === suggestion.id}
                          >
                            <X className="h-3.5 w-3.5" />
                            Отклонить
                          </Button>
                        </div>
                      </article>
                    ))
                  ) : (
                    <div className="rounded-xl border border-dashed border-slate-200 px-3 py-6 text-center text-sm text-slate-500">
                      Нет правок на согласовании.
                    </div>
                  )}
                </div>
              </div>
              <div className="rounded-2xl border border-slate-100 bg-white p-4">
                <div className="text-sm font-bold text-slate-950">История правок</div>
                <div className="mt-4 space-y-3">
                  {resolvedSuggestions.length > 0 ? (
                    resolvedSuggestions.map((suggestion) => (
                      <article key={suggestion.id} className="rounded-xl bg-slate-50 px-3 py-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-400">
                            {suggestion.status === 'accepted' ? 'Принято' : 'Отклонено'}
                          </div>
                          <div className="text-xs text-slate-400">{formatDateTime(suggestion.resolved_at || suggestion.updated_at)}</div>
                        </div>
                        <div className="mt-2 text-sm leading-6 text-slate-600">{suggestion.selection_text}</div>
                      </article>
                    ))
                  ) : (
                    <div className="rounded-xl border border-dashed border-slate-200 px-3 py-6 text-center text-sm text-slate-500">
                      История появится после принятия или отклонения правок.
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : null}
        </section>

        <form onSubmit={sendMessage} className="mt-6 rounded-[24px] border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
          <div className="flex items-center gap-2 text-sm font-bold text-slate-950">
            <MessageSquare className="h-4 w-4 text-orange-500" />
            Обсудить следующий шаг
          </div>
          <Textarea
            value={messageText}
            onChange={(event) => setMessageText(event.currentTarget.value)}
            placeholder="Напишите, что уточнить, изменить или обсудить..."
            className="mt-4 min-h-28 resize-none"
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
            {fileUploadsVisible ? (
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
            ) : (
              <span />
            )}
            <Button type="submit" className="gap-2 bg-slate-950 text-white hover:bg-slate-800" disabled={sending || (fileUploadsVisible && uploading)}>
              {sending ? 'Отправляем...' : 'Отправить'}
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </form>

        <section className="mt-6 rounded-[24px] border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-sm font-bold text-slate-950">История обсуждения</div>
              <p className="mt-1 text-sm text-slate-500">Сообщения по этому предложению.</p>
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
                  {message.author_contact ? <div className="mt-1 text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">{message.author_contact}</div> : null}
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
              Пока нет сообщений. Начните обсуждение с вопроса или правки к предложению.
            </div>
          )}
        </section>

        <footer className="px-2 py-8 text-sm leading-6 text-slate-500">
          Цифровая комната. Подготовьте предложение и обсудите в одном месте.
        </footer>
      </section>
      <a
        href="https://localos.pro/"
        className="fixed bottom-4 right-4 z-30 rounded-full border border-slate-200 bg-white/90 px-3 py-1.5 text-xs font-medium text-slate-500 shadow-sm backdrop-blur transition hover:border-orange-200 hover:text-orange-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-400 focus-visible:ring-offset-2 sm:bottom-6 sm:right-6"
      >
        Подготовлено в LocalOS
      </a>
    </main>
  );
}
