import React, { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';
import { Input } from './ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { useLanguage } from '@/i18n/LanguageContext';
import {
  MessageSquare,
  Sparkles,
  Copy,
  Edit3,
  Send,
  Save,
  X,
  ChevronLeft,
  ChevronRight,
  Trash2,
  Plus,
  Globe,
  Settings2,
  Calendar,
  User,
  Star,
  Quote
} from 'lucide-react';
import { DESIGN_TOKENS, cn } from '@/lib/design-tokens';

type Tone = 'friendly' | 'professional' | 'premium' | 'youth' | 'business';

// Tones will be translated inside component using t()

interface ExternalReview {
  id: string;
  source: string;
  rating: number | null;
  author_name: string;
  text: string;
  response_text: string | null;
  published_at: string | null;
  has_response: boolean;
}

export default function ReviewReplyAssistant({ businessName }: { businessName?: string }) {
  const { currentBusinessId } = useOutletContext<any>();
  const { language: interfaceLanguage, t } = useLanguage();
  const [tone, setTone] = useState<Tone>('professional');
  const [review, setReview] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reply, setReply] = useState('');
  const [editableReply, setEditableReply] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [exampleInput, setExampleInput] = useState('');
  const [examples, setExamples] = useState<{ id: string, text: string }[]>([]);
  const [language, setLanguage] = useState<string>(interfaceLanguage);
  const [externalReviews, setExternalReviews] = useState<ExternalReview[]>([]);
  const [loadingReviews, setLoadingReviews] = useState(false);
  const [generatingForReviewId, setGeneratingForReviewId] = useState<string | null>(null);
  const [generatedReplies, setGeneratedReplies] = useState<Record<string, string>>({});
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  const LANGUAGE_OPTIONS = [
    { value: 'ru', label: 'Русский' },
    { value: 'en', label: 'English' },
    { value: 'es', label: 'Español' },
    { value: 'de', label: 'Deutsch' },
    { value: 'fr', label: 'Français' },
    { value: 'it', label: 'Italiano' },
    { value: 'pt', label: 'Português' },
    { value: 'zh', label: '中文' },
  ];

  const loadExamples = async () => {
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${window.location.origin}/api/review-examples`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await res.json();
      if (data.success) setExamples((data.examples || []).map((e: any) => ({ id: e.id, text: e.text })));
    } catch { }
  };

  const loadExternalReviews = async () => {
    // Сбрасываем страницу при загрузке новых отзывов
    setCurrentPage(1);
    if (!currentBusinessId) return;
    setLoadingReviews(true);
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${window.location.origin}/api/business/${currentBusinessId}/external/reviews`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await res.json();
      if (data.success) {
        setExternalReviews(data.reviews || []);
      }
    } catch (e: any) {
      console.error('Ошибка загрузки отзывов:', e);
    } finally {
      setLoadingReviews(false);
    }
  };

  useEffect(() => {
    loadExamples();
    loadExternalReviews();
  }, [currentBusinessId]);

  const addExample = async () => {
    const text = exampleInput.trim();
    if (!text) return;
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${window.location.origin}/api/review-examples`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ text })
      });
      const data = await res.json();
      if (data.success) { setExampleInput(''); await loadExamples(); }
      else setError(data.error || t.dashboard.card.reviewReply.errorAddExample);
    } catch (e: any) { setError(e.message || t.dashboard.card.reviewReply.errorAddExample); }
  };

  const deleteExample = async (id: string) => {
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${window.location.origin}/api/review-examples/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await res.json();
      if (data.success) await loadExamples(); else setError(data.error || t.dashboard.card.reviewReply.errorDeleteExample);
    } catch (e: any) { setError(e.message || t.dashboard.card.reviewReply.errorDeleteExample); }
  };

  const handleGenerate = async (reviewText?: string, reviewId?: string) => {
    const textToGenerate = reviewText || review;
    if (!textToGenerate.trim()) return;

    if (reviewId) {
      setGeneratingForReviewId(reviewId);
    } else {
      setLoading(true);
    }
    setError(null);

    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${window.location.origin}/api/reviews/reply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({
          review: textToGenerate,
          tone,
          business_name: businessName || '',
          language,
          examples: examples.map(e => e.text) // Передаём примеры для генерации
        })
      });
      const data = await res.json();

      if (!res.ok || data.error) {
        setError(data.error || t.dashboard.card.reviewReply.errorGenerate);
      } else {
        // Проверяем разные форматы ответа
        let generatedReply = '';
        if (data.result?.reply) {
          generatedReply = data.result.reply;
        } else if (data.reply) {
          generatedReply = data.reply;
        } else if (typeof data.result === 'string') {
          generatedReply = data.result;
        } else if (data.result && typeof data.result === 'object' && 'text' in data.result) {
          generatedReply = data.result.text;
        }

        if (reviewId) {
          // Сохраняем ответ для конкретного отзыва
          setGeneratedReplies(prev => ({ ...prev, [reviewId]: generatedReply }));
        } else {
          // Для ручного ввода
          setReply(generatedReply);
          setEditableReply(generatedReply);
          setIsEditing(false);
        }
      }
    } catch (e: any) {
      setError(e.message || t.dashboard.card.reviewReply.errorGenerate);
    } finally {
      if (reviewId) {
        setGeneratingForReviewId(null);
      } else {
        setLoading(false);
      }
    }
  };

  const handleEditReply = () => {
    setIsEditing(true);
    setEditableReply(reply);
  };

  const handleSaveReply = async () => {
    if (!editableReply.trim()) {
      setError(t.dashboard.card.reviewReply.errorEmptyReply);
      return;
    }

    setSaving(true);
    setError(null);

    try {
      const token = localStorage.getItem('auth_token');
      const replyId = `reply_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

      const res = await fetch(`${window.location.origin}/api/review-replies/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({
          replyId,
          replyText: editableReply.trim()
        })
      });

      const data = await res.json();
      if (data.success) {
        setReply(editableReply);
        setIsEditing(false);
        setError(null);
      } else {
        setError(data.error || t.dashboard.card.reviewReply.errorSave);
      }
    } catch (e: any) {
      setError(e.message || t.dashboard.card.reviewReply.errorSave);
    } finally {
      setSaving(false);
    }
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
    setEditableReply(reply);
  };


  // Get tone labels from translations
  const tones: { key: Tone; label: string }[] = [
    { key: 'friendly', label: t.dashboard.card.reviewReply.tones.friendly },
    { key: 'professional', label: t.dashboard.card.reviewReply.tones.professional },
    { key: 'premium', label: t.dashboard.card.reviewReply.tones.premium },
    { key: 'youth', label: t.dashboard.card.reviewReply.tones.youth },
    { key: 'business', label: t.dashboard.card.reviewReply.tones.business },
  ];

  return (
    <div className="space-y-8">
      {/* Header Section */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h3 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <MessageSquare className="w-6 h-6 text-primary" />
            {t.dashboard.card.reviewReply.title}
          </h3>
          <p className="text-gray-600 mt-1">{t.dashboard.card.reviewReply.subtitle}</p>
        </div>
      </div>

      {/* Settings Panel */}
      <div className={cn(DESIGN_TOKENS.glass.default, "rounded-2xl p-6 bg-gradient-to-br from-white/80 to-indigo-50/30")}>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-gray-700">
              <Settings2 className="w-4 h-4" />
              {t.dashboard.card.reviewReply.toneLabel}
            </div>
            <div className="flex flex-wrap gap-2">
              {tones.map(toneItem => (
                <button key={toneItem.key} type="button" onClick={() => setTone(toneItem.key)}
                  className={cn(
                    "text-sm px-4 py-2 rounded-xl border transition-all duration-200",
                    tone === toneItem.key
                      ? 'bg-primary text-white border-primary shadow-lg shadow-primary/20 scale-105'
                      : 'border-gray-200 bg-white text-gray-700 hover:border-primary/50 hover:bg-primary/5'
                  )}>
                  {toneItem.label}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-gray-700">
              <Globe className="w-4 h-4" />
              {t.dashboard.card.reviewReply.languageLabel}
            </div>
            <Select value={language} onValueChange={setLanguage}>
              <SelectTrigger className="w-full h-10 rounded-xl bg-white border-gray-200 focus:ring-primary/20">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {LANGUAGE_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="mt-8 space-y-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-gray-700">
            <Quote className="w-4 h-4" />
            {t.dashboard.card.reviewReply.examplesLabel}
          </div>
          <div className="flex gap-2">
            <Input
              value={exampleInput}
              onChange={(e) => setExampleInput(e.target.value)}
              placeholder={t.dashboard.card.reviewReply.examplesPlaceholder}
              className="rounded-xl border-gray-200 focus:ring-primary/20"
            />
            <Button variant="outline" onClick={addExample} className="rounded-xl border-gray-200 bg-white hover:bg-gray-50">
              <Plus className="w-4 h-4 mr-2" />
              {t.dashboard.card.reviewReply.addExample}
            </Button>
          </div>
          {examples.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {examples.map(e => (
                <div key={e.id} className="flex items-center gap-2 text-sm text-gray-700 bg-white border border-gray-200 rounded-lg px-3 py-1.5 shadow-sm">
                  <span>{e.text}</span>
                  <button className="text-gray-400 hover:text-red-500 transition-colors" onClick={() => deleteExample(e.id)}>
                    <X className="w-3 h-3" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Manual Generation Block */}
      <div className={cn("bg-white rounded-2xl border border-gray-200 p-6 shadow-sm")}>
        <h4 className="text-md font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-amber-500" />
          Quick Generator
        </h4>
        <Textarea
          rows={4}
          value={review}
          onChange={(e) => setReview(e.target.value)}
          placeholder={t.dashboard.card.reviewReply.reviewPlaceholder}
          className="rounded-xl border-gray-200 bg-gray-50 focus:bg-white transition-all mb-4 resize-none"
        />

        {error && (
          <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl text-sm">
            {error}
          </div>
        )}

        <div className="flex justify-end">
          <Button onClick={() => handleGenerate()} disabled={loading || !review.trim()} className="rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-700 hover:to-indigo-700 text-white shadow-lg shadow-indigo-500/20">
            {loading ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent mr-2"></div>
                {t.dashboard.card.reviewReply.generating}
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4 mr-2" />
                {t.dashboard.card.reviewReply.generate}
              </>
            )}
          </Button>
        </div>

        {reply && (
          <div className="mt-6 bg-indigo-50/50 border border-indigo-100 p-5 rounded-2xl animate-in fade-in slide-in-from-top-2">
            <div className="text-xs font-bold uppercase tracking-wider text-indigo-400 mb-3 flex items-center gap-1">
              <Sparkles className="w-3 h-3" />
              Generated Reply
            </div>
            {isEditing ? (
              <div className="space-y-3">
                <Textarea
                  value={editableReply}
                  onChange={(e) => setEditableReply(e.target.value)}
                  rows={4}
                  className="w-full rounded-xl border-indigo-200 focus:ring-indigo-500/20"
                  placeholder={t.dashboard.card.reviewReply.editPlaceholder}
                />
                <div className="flex gap-2 justify-end">
                  <Button
                    onClick={handleCancelEdit}
                    variant="ghost"
                    size="sm"
                    className="text-gray-600 hover:bg-gray-100 rounded-lg"
                  >
                    {t.common.cancel || "Cancel"}
                  </Button>
                  <Button
                    onClick={handleSaveReply}
                    disabled={saving || !editableReply.trim()}
                    size="sm"
                    className="bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg"
                  >
                    {saving ? t.dashboard.card.reviewReply.saving : t.dashboard.card.reviewReply.save}
                  </Button>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="text-gray-800 leading-relaxed whitespace-pre-wrap font-medium">{reply}</div>
                <div className="flex gap-2 justify-end">
                  <Button
                    onClick={handleEditReply}
                    variant="outline"
                    size="sm"
                    className="bg-white border-indigo-200 text-indigo-700 hover:bg-indigo-50 rounded-lg"
                  >
                    <Edit3 className="w-3.5 h-3.5 mr-2" />
                    Edit
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => navigator.clipboard.writeText(reply)}
                    className="bg-white border-indigo-200 text-indigo-700 hover:bg-indigo-50 rounded-lg"
                  >
                    <Copy className="w-3.5 h-3.5 mr-2" />
                    Copy
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* External Reviews List */}
      <div className="pt-8 border-t border-gray-100">
        <h4 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
          <Globe className="w-5 h-5 text-gray-400" />
          {t.dashboard.card.reviewReply.externalTitle}
        </h4>

        {loadingReviews ? (
          <div className="flex justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-2 border-primary border-t-transparent"></div>
          </div>
        ) : externalReviews.length === 0 ? (
          <div className="text-center py-12 bg-gray-50 rounded-2xl border border-dashed border-gray-200">
            <MessageSquare className="w-12 h-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500 font-medium">{t.dashboard.card.reviewReply.noReviews}</p>
          </div>
        ) : (
          <div className="space-y-6">
            {externalReviews
              .slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage)
              .map((reviewItem) => (
                <div key={reviewItem.id} className="bg-white border border-gray-200 rounded-2xl p-6 shadow-sm hover:shadow-md transition-shadow">
                  <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6 pb-4 border-b border-gray-100">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-gradient-to-br from-indigo-100 to-violet-100 flex items-center justify-center text-indigo-600 font-bold">
                        {(reviewItem.author_name || 'A')[0].toUpperCase()}
                      </div>
                      <div>
                        <div className="font-semibold text-gray-900">{reviewItem.author_name || t.dashboard.card.reviewReply.anonymous}</div>
                        <div className="flex items-center gap-2 text-xs text-gray-500">
                          {reviewItem.published_at && (
                            <span className="flex items-center gap-1">
                              <Calendar className="w-3 h-3" />
                              {new Date(reviewItem.published_at).toLocaleDateString(interfaceLanguage === 'ru' ? 'ru-RU' : 'en-US')}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    {reviewItem.rating && (
                      <div className="flex items-center gap-1 bg-amber-50 px-3 py-1.5 rounded-lg border border-amber-100">
                        {[...Array(5)].map((_, i) => (
                          <Star key={i} className={cn("w-3.5 h-3.5", i < reviewItem.rating! ? "text-amber-500 fill-amber-500" : "text-gray-200 fill-gray-200")} />
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                    {/* Client Review */}
                    <div className="space-y-2">
                      <div className="text-xs font-bold uppercase tracking-wider text-gray-400">
                        {t.dashboard.card.reviewReply.clientReview}
                      </div>
                      <div className="bg-gray-50 rounded-xl p-4 text-gray-800 text-sm leading-relaxed min-h-[120px] relative">
                        <Quote className="absolute top-3 right-3 w-4 h-4 text-gray-300 transform rotate-180" />
                        {reviewItem.text || <span className="text-gray-400 italic">{t.dashboard.card.reviewReply.noReviewText}</span>}
                      </div>
                    </div>

                    {/* Organization Reply */}
                    <div className="space-y-2">
                      <div className="text-xs font-bold uppercase tracking-wider text-primary">
                        {t.dashboard.card.reviewReply.organizationReply}
                      </div>

                      {reviewItem.has_response && reviewItem.response_text ? (
                        <div className="bg-emerald-50/50 border border-emerald-100 rounded-xl p-4 text-emerald-900 text-sm leading-relaxed min-h-[120px] relative">
                          <div className="absolute top-2 right-2 p-1 bg-emerald-100 rounded-md">
                            <Send className="w-3 h-3 text-emerald-600" />
                          </div>
                          {reviewItem.response_text}
                        </div>
                      ) : (
                        <div className="flex flex-col h-full gap-2">
                          <Textarea
                            rows={4}
                            value={generatedReplies[reviewItem.id] || ''}
                            onChange={(e) => setGeneratedReplies(prev => ({ ...prev, [reviewItem.id]: e.target.value }))}
                            placeholder={t.dashboard.card.reviewReply.replyPlaceholder}
                            className="flex-1 min-h-[120px] rounded-xl border-indigo-200 focus:ring-indigo-500/20 bg-white"
                          />
                          <div className="flex gap-2">
                            <Button
                              onClick={(e) => {
                                e.preventDefault();
                                handleGenerate(reviewItem.text || '', reviewItem.id);
                              }}
                              disabled={generatingForReviewId === reviewItem.id || !reviewItem.text}
                              size="sm"
                              className="flex-1 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-700 hover:to-indigo-700 text-white rounded-lg"
                            >
                              {generatingForReviewId === reviewItem.id ? (
                                <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></div>
                              ) : (
                                <> <Sparkles className="w-3.5 h-3.5 mr-2" /> {t.dashboard.card.reviewReply.generate} </>
                              )}
                            </Button>
                            {generatedReplies[reviewItem.id] && (
                              <Button
                                onClick={() => navigator.clipboard.writeText(generatedReplies[reviewItem.id])}
                                size="sm"
                                variant="outline"
                                className="bg-white border-gray-200 hover:bg-gray-50 text-gray-700 rounded-lg px-3"
                                title="Copy"
                              >
                                <Copy className="w-4 h-4" />
                              </Button>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}

            {/* Pagination */}
            {externalReviews.length > itemsPerPage && (
              <div className="flex items-center justify-between pt-6">
                <div className="text-sm text-gray-500 font-medium">
                  {((currentPage - 1) * itemsPerPage) + 1}-{Math.min(currentPage * itemsPerPage, externalReviews.length)} / {externalReviews.length}
                </div>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                    disabled={currentPage === 1}
                    className="rounded-lg h-9 w-9 p-0"
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setCurrentPage(prev => Math.min(Math.ceil(externalReviews.length / itemsPerPage), prev + 1))}
                    disabled={currentPage >= Math.ceil(externalReviews.length / itemsPerPage)}
                    className="rounded-lg h-9 w-9 p-0"
                  >
                    <ChevronRight className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
