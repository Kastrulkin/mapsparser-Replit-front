import React, { useEffect, useState } from 'react';
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';
import { Input } from './ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { useLanguage } from '@/i18n/LanguageContext';

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
  const [examples, setExamples] = useState<{id:string, text:string}[]>([]);
  const { language: interfaceLanguage } = useLanguage();
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
    } catch {}
  };

  useEffect(()=>{ loadNews(); }, []);
  useEffect(()=>{ (async()=>{
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${window.location.origin}/api/news-examples`, { headers: { 'Authorization': `Bearer ${token}` } });
      const data = await res.json();
      if (data.success) setExamples((data.examples||[]).map((e:any)=>({ id: e.id, text: e.text })));
    } catch {}
  })(); }, []);
  
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
    if (!confirm('Вы уверены, что хотите удалить эту новость?')) return;
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
      if (json.success) setExamples((json.examples||[]).map((e:any)=>({ id: e.id, text: e.text })));
    }
  };

  const deleteExample = async (id: string) => {
    const token = localStorage.getItem('auth_token');
    const res = await fetch(`${window.location.origin}/api/news-examples/${id}`, { method: 'DELETE', headers: { 'Authorization': `Bearer ${token}` } });
    const data = await res.json();
    if (data.success) {
      const list = await fetch(`${window.location.origin}/api/news-examples`, { headers: { 'Authorization': `Bearer ${token}` } });
      const json = await list.json();
      if (json.success) setExamples((json.examples||[]).map((e:any)=>({ id: e.id, text: e.text })));
    }
  };

  return (
    <div>
      <h2 className="text-xl font-semibold text-gray-900 mb-2">Новости</h2>
      <div className="mb-3">
        <label className="block text-sm text-gray-600 mb-1">Примеры новостей (до 5)</label>
        <div className="flex gap-2">
          <Input value={exampleInput} onChange={(e)=> setExampleInput(e.target.value)} placeholder="Например: Запустили экспресс-маникюр — запись уже открыта" />
          <Button variant="outline" onClick={addExample}>Добавить</Button>
        </div>
        {examples.length>0 && (
          <ul className="mt-2 space-y-1">
            {examples.map(e => (
              <li key={e.id} className="flex items-center justify-between text-sm text-gray-700 bg-gray-50 border border-gray-200 rounded px-2 py-1">
                <span className="mr-2 truncate">{e.text}</span>
                <button className="text-xs text-red-600" onClick={()=> deleteExample(e.id)}>Удалить</button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="space-y-3 mb-3">
        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input type="checkbox" checked={useService} onChange={(e)=> { setUseService(e.target.checked); if (e.target.checked) setUseTransaction(false); }} />
          Сгенерировать новость на основе услуги
        </label>
        {useService && (
          <div className="ml-6">
            <label className="block text-sm text-gray-600 mb-1">Выберите услугу</label>
            <select className="border rounded px-2 py-2 w-full" value={serviceId} onChange={(e)=> setServiceId(e.target.value)}>
              <option value="">— выбрать —</option>
              {services.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
        )}
        
        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input type="checkbox" checked={useTransaction} onChange={(e)=> { setUseTransaction(e.target.checked); if (e.target.checked) setUseService(false); }} />
          Сгенерировать новость на основе выполненной работы (из транзакций)
        </label>
        {useTransaction && (
          <div className="ml-6">
            <label className="block text-sm text-gray-600 mb-1">Выберите транзакцию</label>
            {loadingTransactions ? (
              <div className="text-sm text-gray-500">Загрузка транзакций...</div>
            ) : transactions.length === 0 ? (
              <div className="text-sm text-gray-500">Нет транзакций. Добавьте транзакции во вкладке Финансы.</div>
            ) : (
              <select className="border rounded px-2 py-2 w-full" value={transactionId} onChange={(e)=> setTransactionId(e.target.value)}>
                <option value="">— выбрать —</option>
                {transactions.map(t => (
                  <option key={t.id} value={t.id}>
                    {t.transaction_date} - {t.services?.join(', ') || 'Услуги'} - {t.amount}₽ {t.notes ? `(${t.notes})` : ''}
                  </option>
                ))}
              </select>
            )}
          </div>
        )}
      </div>
      <div className="mb-3">
        <label className="block text-sm text-gray-600 mb-1">Неотформатированная информация (необязательно)</label>
        <Textarea rows={3} value={rawInfo} onChange={(e)=> setRawInfo(e.target.value)} placeholder="Например: Новый сотрудник, акция, праздник и т.п." />
      </div>

      <div className="mb-3">
        <label className="block text-sm text-gray-600 mb-1">Язык новости</label>
        <Select value={language} onValueChange={setLanguage}>
          <SelectTrigger>
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
        <p className="text-xs text-gray-500 mt-1">
          Язык, на котором будет сгенерирована новость. По умолчанию — язык интерфейса (
          {LANGUAGE_OPTIONS.find((l) => l.value === interfaceLanguage)?.label || interfaceLanguage}).
        </p>
      </div>
      <Button onClick={generate} disabled={loading}>{loading ? 'Генерация…' : 'Сгенерировать новость'}</Button>

      {generated && (
        <div className="mt-3 p-3 bg-blue-50 border border-blue-200 rounded text-sm text-blue-900">
          <div className="flex items-center justify-between mb-2">
            <div className="font-medium">Сгенерированный вариант</div>
            <button 
              onClick={() => setGenerated('')}
              className="text-xs text-red-600 hover:text-red-800 underline"
            >
              Удалить
            </button>
          </div>
          <div className="mb-2">{generated}</div>
        </div>
      )}

      <div className="mt-4">
        <div className="text-sm font-medium text-gray-900 mb-2">Ваши новости</div>
        {(news.length === 0 && (!externalPosts || externalPosts.length === 0)) ? (
          <div className="text-sm text-gray-500">Пока нет новостей</div>
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
            <>
              {/* Пагинация сверху */}
              {totalItems > itemsPerPage && (
                <div className="flex items-center justify-between mb-4 pb-4 border-b border-gray-200">
                  <div className="text-sm text-gray-600">
                    Показано {((currentPage - 1) * itemsPerPage) + 1}-{Math.min(currentPage * itemsPerPage, totalItems)} из {totalItems}
                  </div>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                      disabled={currentPage === 1}
                    >
                      Назад
                    </Button>
                    <span className="px-3 py-1 text-sm text-gray-700">
                      Страница {currentPage} из {Math.ceil(totalItems / itemsPerPage)}
                    </span>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setCurrentPage(prev => Math.min(Math.ceil(totalItems / itemsPerPage), prev + 1))}
                      disabled={currentPage >= Math.ceil(totalItems / itemsPerPage)}
                    >
                      Вперед
                    </Button>
                  </div>
                </div>
              )}
              
              <ul className="space-y-2">
                {paginatedNews.map((item: any) => {
                  if (item.isExternal) {
                    // Спарсенные публикации из внешних источников
                    return (
                      <li key={`external-${item.id}`} className="border border-blue-200 rounded p-3 text-sm bg-blue-50">
                        <div className="flex items-start justify-between mb-2">
                          <div className="flex-1">
                            {item.title && (
                              <div className="font-semibold text-gray-900 mb-1">{item.title}</div>
                            )}
                            <div className="text-gray-700 whitespace-pre-wrap">{item.text || 'Без текста'}</div>
                            {item.published_at && (
                              <div className="text-xs text-gray-500 mt-2">
                                Опубликовано: {new Date(item.published_at).toLocaleDateString('ru-RU')}
                              </div>
                            )}
                            {item.source && (
                              <div className="text-xs text-gray-500">
                                Источник: {item.source === 'yandex_business' ? 'Яндекс.Бизнес' : item.source}
                              </div>
                            )}
                          </div>
                        </div>
                      </li>
                    );
                  } else {
                    // Сгенерированные новости
                    return (
                      <li key={item.id} className="border border-gray-200 rounded p-2 text-sm">
                        <Textarea 
                          id={`news-textarea-${item.id}`}
                          rows={3} 
                          defaultValue={item.generated_text} 
                          onBlur={(e)=> saveEdited(item.id, e.target.value)} 
                        />
                        <div className="mt-2 flex gap-2">
                          {!item.approved && (
                            <Button size="sm" variant="outline" onClick={()=> approve(item.id)}>Принять</Button>
                          )}
                          <Button 
                            size="sm" 
                            variant="outline" 
                            onClick={() => {
                              const textarea = document.getElementById(`news-textarea-${item.id}`) as HTMLTextAreaElement;
                              textarea?.focus();
                            }}
                          >
                            Редактировать
                          </Button>
                          <Button 
                            size="sm"
                            variant="outline" 
                            onClick={() => deleteNews(item.id)}
                            className="text-red-600 hover:text-red-700"
                          >
                            Удалить
                          </Button>
                        </div>
                      </li>
                    );
                  }
                })}
              </ul>
              
              {/* Пагинация внизу */}
              {totalItems > itemsPerPage && (
                <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-200">
                  <div className="text-sm text-gray-600">
                    Показано {((currentPage - 1) * itemsPerPage) + 1}-{Math.min(currentPage * itemsPerPage, totalItems)} из {totalItems}
                  </div>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                      disabled={currentPage === 1}
                    >
                      Назад
                    </Button>
                    <span className="px-3 py-1 text-sm text-gray-700">
                      Страница {currentPage} из {Math.ceil(totalItems / itemsPerPage)}
                    </span>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setCurrentPage(prev => Math.min(Math.ceil(totalItems / itemsPerPage), prev + 1))}
                      disabled={currentPage >= Math.ceil(totalItems / itemsPerPage)}
                    >
                      Вперед
                    </Button>
                  </div>
                </div>
              )}
            </>
          );
        })()}
      </div>
    </div>
  );
}


