import React, { useEffect, useState } from 'react';
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';
import { Input } from './ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { useLanguage } from '@/i18n/LanguageContext';
import {
  Newspaper,
  Sparkles,
  Plus,
  Trash2,
  Copy,
  Edit3,
  Check,
  Globe,
  Briefcase,
  CreditCard,
  FileText,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  Calendar
} from 'lucide-react';
import { DESIGN_TOKENS, cn } from '@/lib/design-tokens';

type ServiceLite = { id: string; name: string };

export default function NewsGenerator({ services, businessId, externalPosts }: { services: ServiceLite[]; businessId?: string; externalPosts?: any[] }) {
  const [useService, setUseService] = useState(false);
  const [useTransaction, setUseTransaction] = useState(false);
  const [serviceId, setServiceId] = useState<string>('');
  const [transactionId, setTransactionId] = useState<string>('');
  const [transactions, setTransactions] = useState<any[]>([]);
  const [loadingTransactions, setLoadingTransactions] = useState(false);
  const [rawInfo, setRawInfo] = useState('');
  const [loading, setLoading] = useState(false);
  const [generated, setGenerated] = useState<string>('');
  const [news, setNews] = useState<any[]>([]);
  const [exampleInput, setExampleInput] = useState('');
  const [examples, setExamples] = useState<{ id: string, text: string }[]>([]);
  const { language: interfaceLanguage, t } = useLanguage();
  const [language, setLanguage] = useState<string>(interfaceLanguage);
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

  const loadNews = async () => {
    // Сбрасываем страницу при загрузке новых новостей
    setCurrentPage(1);
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${window.location.origin}/api/news/list`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await res.json();
      if (data.success) setNews(data.news || []);
    } catch { }
  };

  useEffect(() => { loadNews(); }, []);
  useEffect(() => {
    (async () => {
      try {
        const token = localStorage.getItem('auth_token');
        const res = await fetch(`${window.location.origin}/api/news-examples`, { headers: { 'Authorization': `Bearer ${token}` } });
        const data = await res.json();
        if (data.success) setExamples((data.examples || []).map((e: any) => ({ id: e.id, text: e.text })));
      } catch { }
    })();
  }, []);

  // Загрузка транзакций
  const loadTransactions = async () => {
    if (!businessId) return;
    setLoadingTransactions(true);
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${window.location.origin}/api/finance/transactions?business_id=${businessId}&limit=20`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await res.json();
      if (data.success) {
        setTransactions(data.transactions || []);
      }
    } catch (e) {
      console.error('Ошибка загрузки транзакций:', e);
    } finally {
      setLoadingTransactions(false);
    }
  };

  useEffect(() => {
    if (useTransaction && businessId) {
      loadTransactions();
    }
  }, [useTransaction, businessId]);

  const generate = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${window.location.origin}/api/news/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({
          use_service: useService,
          use_transaction: useTransaction,
          service_id: serviceId || undefined,
          transaction_id: transactionId || undefined,
          raw_info: rawInfo,
          language
        })
      });
      const data = await res.json();
      if (data.success) {
        setGenerated(data.generated_text || '');
        await loadNews();
      }
    } finally {
      setLoading(false);
    }
  };

  const approve = async (id: string) => {
    const token = localStorage.getItem('auth_token');
    const res = await fetch(`${window.location.origin}/api/news/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ news_id: id })
    });
    const data = await res.json();
    if (data.success) await loadNews();
  };

  const saveEdited = async (id: string, text: string) => {
    const token = localStorage.getItem('auth_token');
    const res = await fetch(`${window.location.origin}/api/news/update`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ news_id: id, text })
    });
    const data = await res.json();
    if (data.success) await loadNews();
  };

  const deleteNews = async (id: string) => {
    if (!confirm(t.dashboard.card.newsGenerator.deleteConfirm)) return;
    const token = localStorage.getItem('auth_token');
    const res = await fetch(`${window.location.origin}/api/news/delete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ news_id: id })
    });
    const data = await res.json();
    if (data.success) await loadNews();
  };

  const addExample = async () => {
    const text = exampleInput.trim();
    if (!text) return;
    const token = localStorage.getItem('auth_token');
    const res = await fetch(`${window.location.origin}/api/news-examples`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` }, body: JSON.stringify({ text })
    });
    const data = await res.json();
    if (data.success) {
      setExampleInput('');
      const list = await fetch(`${window.location.origin}/api/news-examples`, { headers: { 'Authorization': `Bearer ${token}` } });
      const json = await list.json();
      if (json.success) setExamples((json.examples || []).map((e: any) => ({ id: e.id, text: e.text })));
    }
  };

  const deleteExample = async (id: string) => {
    const token = localStorage.getItem('auth_token');
    const res = await fetch(`${window.location.origin}/api/news-examples/${id}`, { method: 'DELETE', headers: { 'Authorization': `Bearer ${token}` } });
    const data = await res.json();
    if (data.success) {
      const list = await fetch(`${window.location.origin}/api/news-examples`, { headers: { 'Authorization': `Bearer ${token}` } });
      const json = await list.json();
      if (json.success) setExamples((json.examples || []).map((e: any) => ({ id: e.id, text: e.text })));
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h3 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Newspaper className="w-6 h-6 text-primary" />
            {t.dashboard.card.newsGenerator.title}
          </h3>
          <p className="text-gray-600 mt-1">Generate engaging news posts for social media based on your services.</p>
        </div>
      </div>

      {/* Generator Panel */}
      <div className={cn(DESIGN_TOKENS.glass.default, "rounded-2xl p-6 bg-gradient-to-br from-white/80 to-blue-50/30")}>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-8">
          {/* Left Column: Sources */}
          <div className="space-y-6">
            <div className="text-sm font-bold uppercase tracking-wider text-gray-400">Source Material</div>

            <div className="space-y-4">
              {/* Service Selection */}
              <div className={cn("p-4 rounded-xl border transition-all cursor-pointer", useService ? "bg-white border-blue-500 shadow-md ring-1 ring-blue-500/20" : "bg-white/50 border-gray-200 hover:bg-white")}>
                <label className="flex items-center gap-3 text-sm font-semibold text-gray-700 cursor-pointer mb-2">
                  <input type="checkbox" className="rounded text-blue-600 w-4 h-4 focus:ring-blue-500" checked={useService} onChange={(e) => { setUseService(e.target.checked); if (e.target.checked) setUseTransaction(false); }} />
                  <Briefcase className="w-4 h-4 text-blue-500" />
                  {t.dashboard.card.newsGenerator.generateFromService}
                </label>
                {useService && (
                  <div className="pl-7 animate-in fade-in slide-in-from-top-1">
                    <select className="w-full rounded-lg border-gray-200 text-sm focus:ring-blue-500/20" value={serviceId} onChange={(e) => setServiceId(e.target.value)}>
                      <option value="">— {t.common.select} —</option>
                      {services.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                    </select>
                  </div>
                )}
              </div>

              {/* Transaction Selection */}
              <div className={cn("p-4 rounded-xl border transition-all cursor-pointer", useTransaction ? "bg-white border-blue-500 shadow-md ring-1 ring-blue-500/20" : "bg-white/50 border-gray-200 hover:bg-white")}>
                <label className="flex items-center gap-3 text-sm font-semibold text-gray-700 cursor-pointer mb-2">
                  <input type="checkbox" className="rounded text-blue-600 w-4 h-4 focus:ring-blue-500" checked={useTransaction} onChange={(e) => { setUseTransaction(e.target.checked); if (e.target.checked) setUseService(false); }} />
                  <CreditCard className="w-4 h-4 text-blue-500" />
                  {t.dashboard.card.newsGenerator.generateFromTransaction}
                </label>
                {useTransaction && (
                  <div className="pl-7 animate-in fade-in slide-in-from-top-1">
                    {loadingTransactions ? (
                      <div className="text-xs text-gray-500 py-2 flex items-center gap-2">
                        <div className="animate-spin rounded-full h-3 w-3 border-2 border-primary border-t-transparent"></div>
                        {t.dashboard.card.newsGenerator.loadingTransactions}
                      </div>
                    ) : transactions.length === 0 ? (
                      <div className="text-xs text-gray-500 py-2">{t.dashboard.card.newsGenerator.noTransactions}</div>
                    ) : (
                      <select className="w-full rounded-lg border-gray-200 text-sm focus:ring-blue-500/20" value={transactionId} onChange={(e) => setTransactionId(e.target.value)}>
                        <option value="">— {t.common.select} —</option>
                        {transactions.map(t => (
                          <option key={t.id} value={t.id}>
                            {t.transaction_date} - {t.services?.join(', ') || t.dashboard.card.services} - {t.amount}₽
                          </option>
                        ))}
                      </select>
                    )}
                  </div>
                )}
              </div>

              {/* Raw Text */}
              <div className="p-4 rounded-xl bg-white border border-gray-200">
                <div className="flex items-center gap-2 mb-2">
                  <FileText className="w-4 h-4 text-gray-400" />
                  <label className="text-sm font-semibold text-gray-700">{t.dashboard.card.newsGenerator.rawInfoLabel}</label>
                </div>
                <Textarea
                  rows={3}
                  value={rawInfo}
                  onChange={(e) => setRawInfo(e.target.value)}
                  placeholder={t.dashboard.card.newsGenerator.transactionPlaceholder}
                  className="w-full rounded-lg border-gray-200 focus:ring-blue-500/20 text-sm"
                />
              </div>
            </div>
          </div>

          {/* Right Column: Settings & Examples */}
          <div className="space-y-6">
            <div className="text-sm font-bold uppercase tracking-wider text-gray-400">Settings</div>

            <div className="space-y-4">
              <div>
                <label className="flex items-center gap-2 text-sm font-semibold text-gray-700 mb-2">
                  <Globe className="w-4 h-4 text-gray-500" />
                  {t.dashboard.card.newsGenerator.newsLanguage}
                </label>
                <Select value={language} onValueChange={setLanguage}>
                  <SelectTrigger className="w-full rounded-xl bg-white border-gray-200">
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

              <div>
                <label className="flex items-center gap-2 text-sm font-semibold text-gray-700 mb-2">
                  <Sparkles className="w-4 h-4 text-amber-500" />
                  {t.dashboard.card.newsGenerator.examplesLabel}
                </label>
                <div className="flex gap-2">
                  <Input
                    value={exampleInput}
                    onChange={(e) => setExampleInput(e.target.value)}
                    placeholder={t.dashboard.card.newsGenerator.examplesPlaceholder}
                    className="rounded-xl border-gray-200"
                  />
                  <Button variant="outline" onClick={addExample} className="rounded-xl border-gray-200 bg-white hover:bg-gray-50">
                    <Plus className="w-4 h-4" />
                  </Button>
                </div>
                {examples.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-3">
                    {examples.map(e => (
                      <div key={e.id} className="flex items-center gap-2 text-xs text-gray-600 bg-white border border-gray-200 rounded-lg px-2.5 py-1.5 shadow-sm">
                        <span>{e.text}</span>
                        <button className="text-gray-400 hover:text-red-500 transition-colors" onClick={() => deleteExample(e.id)}>
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        <div className="pt-6 border-t border-blue-100 flex justify-end">
          <Button
            onClick={generate}
            disabled={loading}
            className="w-full md:w-auto px-8 py-6 rounded-xl text-lg font-medium shadow-xl shadow-orange-500/20 bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700 text-white"
          >
            {loading ? (
              <>
                <div className="animate-spin rounded-full h-5 w-5 border-2 border-white border-t-transparent mr-2"></div>
                Generating Magic...
              </>
            ) : (
              <>
                <Sparkles className="w-5 h-5 mr-3" />
                {t.dashboard.card.newsGenerator.generate}
              </>
            )}
          </Button>
        </div>

        {generated && (
          <div className="mt-8 bg-white border border-blue-200 rounded-2xl p-6 shadow-md animate-in fade-in slide-in-from-top-4 ring-4 ring-blue-500/5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2 text-blue-700 font-bold uppercase text-xs tracking-wider">
                <Sparkles className="w-4 h-4" />
                {t.dashboard.card.newsGenerator.result}
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setGenerated('')}
                className="text-red-500 hover:text-red-700 hover:bg-red-50"
              >
                <Trash2 className="w-4 h-4 mr-2" />
                Discard
              </Button>
            </div>
            <div className="text-gray-800 text-base leading-relaxed whitespace-pre-wrap font-medium p-4 bg-gray-50 rounded-xl border border-gray-100">
              {generated}
            </div>
            <div className="mt-2 text-center text-xs text-gray-400">
              The news post has been added to the list below automatically
            </div>
          </div>
        )}
      </div>

      {/* History & External Posts */}
      <div className="space-y-4">
        <h4 className="text-xl font-bold text-gray-900 flex items-center gap-2">
          <Globe className="w-5 h-5 text-gray-500" />
          {t.dashboard.card.newsGenerator.yourNews}
        </h4>

        {(news.length === 0 && (!externalPosts || externalPosts.length === 0)) ? (
          <div className="text-center py-12 bg-gray-50 rounded-2xl border border-dashed border-gray-200">
            <Newspaper className="w-12 h-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500 font-medium">{t.dashboard.card.newsGenerator.noNews}</p>
          </div>
        ) : (() => {
          // Объединяем все новости в один список для пагинации
          const allNews: any[] = [];
          if (externalPosts && externalPosts.length > 0) {
            externalPosts.forEach((post: any) => {
              allNews.push({ ...post, isExternal: true });
            });
          }
          news.forEach((n: any) => {
            allNews.push({ ...n, isExternal: false });
          });
          const totalItems = allNews.length;
          const paginatedNews = allNews.slice((currentPage - 1) * itemsPerPage, currentPage * itemsPerPage);

          return (
            <div className="space-y-6">
              <div className="space-y-4">
                {paginatedNews.map((item: any) => {
                  if (item.isExternal) {
                    // Спарсенные публикации из внешних источников
                    return (
                      <div key={`external-${item.id}`} className="bg-white border border-gray-200 rounded-2xl p-6 shadow-sm hover:shadow-md transition-all">
                        <div className="flex items-center gap-2 mb-3">
                          <span className="px-2.5 py-0.5 rounded-full bg-blue-50 text-blue-700 text-xs font-bold uppercase tracking-wider border border-blue-100">
                            {item.source === 'yandex_business' ? t.dashboard.card.newsGenerator.yandexBusiness : item.source || 'External'}
                          </span>
                          {item.published_at && (
                            <span className="text-xs text-gray-500 flex items-center gap-1">
                              <Calendar className="w-3 h-3" />
                              {new Date(item.published_at).toLocaleDateString(interfaceLanguage === 'ru' ? 'ru-RU' : 'en-US')}
                            </span>
                          )}
                        </div>

                        {item.title && (
                          <h5 className="font-bold text-gray-900 mb-2">{item.title}</h5>
                        )}

                        <div className="text-gray-700 whitespace-pre-wrap text-sm leading-relaxed">
                          {item.text || <span className="text-gray-400 italic">No text content</span>}
                        </div>

                        {item.url && (
                          <div className="mt-4 pt-4 border-t border-gray-100 flex justify-end">
                            <a href={item.url} target="_blank" rel="noopener noreferrer" className="text-xs font-medium text-blue-600 hover:text-blue-800 flex items-center gap-1">
                              View Original <ExternalLink className="w-3 h-3" />
                            </a>
                          </div>
                        )}
                      </div>
                    );
                  } else {
                    // Сгенерированные новости
                    return (
                      <div key={item.id} className="bg-white border border-gray-200 rounded-2xl p-6 shadow-sm hover:shadow-md transition-all group">
                        <div className="flex items-center justify-between mb-3">
                          <span className="px-2.5 py-0.5 rounded-full bg-purple-50 text-purple-700 text-xs font-bold uppercase tracking-wider border border-purple-100 flex items-center gap-1">
                            <Sparkles className="w-3 h-3" /> Generated
                          </span>
                          <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => deleteNews(item.id)}
                              className="h-8 w-8 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg"
                            >
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </div>
                        </div>

                        <Textarea
                          id={`news-textarea-${item.id}`}
                          rows={3}
                          defaultValue={item.generated_text}
                          onBlur={(e) => saveEdited(item.id, e.target.value)}
                          className="border-0 bg-transparent p-0 text-gray-800 text-sm leading-relaxed resize-none focus:ring-0 w-full"
                        />

                        <div className="mt-4 flex gap-2 pt-4 border-t border-gray-50">
                          {!item.approved && (
                            <Button size="sm" variant="outline" onClick={() => approve(item.id)} className="text-xs bg-white hover:bg-green-50 text-gray-700 hover:text-green-700 hover:border-green-200">
                              <Check className="w-3.5 h-3.5 mr-2" />
                              {t.dashboard.card.newsGenerator.copy} / Approve
                            </Button>
                          )}
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              const textarea = document.getElementById(`news-textarea-${item.id}`) as HTMLTextAreaElement;
                              textarea?.focus();
                            }}
                            className="text-xs bg-white hover:bg-blue-50 text-gray-700 hover:text-blue-700 hover:border-blue-200"
                          >
                            <Edit3 className="w-3.5 h-3.5 mr-2" />
                            {t.dashboard.card.newsGenerator.edit}
                          </Button>
                        </div>
                      </div>
                    );
                  }
                })}
              </div>

              {/* Pagination */}
              {totalItems > itemsPerPage && (
                <div className="flex items-center justify-between pt-6">
                  <div className="text-sm text-gray-500 font-medium">
                    {((currentPage - 1) * itemsPerPage) + 1}-{Math.min(currentPage * itemsPerPage, totalItems)} / {totalItems}
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
                      onClick={() => setCurrentPage(prev => Math.min(Math.ceil(totalItems / itemsPerPage), prev + 1))}
                      disabled={currentPage >= Math.ceil(totalItems / itemsPerPage)}
                      className="rounded-lg h-9 w-9 p-0"
                    >
                      <ChevronRight className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              )}
            </div>
          );
        })()}
      </div>
    </div>
  );
}
