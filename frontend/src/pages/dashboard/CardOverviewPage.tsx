import { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from '@/components/ui/accordion';
import ServiceOptimizer from '@/components/ServiceOptimizer';
import ReviewReplyAssistant from '@/components/ReviewReplyAssistant';
import NewsGenerator from '@/components/NewsGenerator';
import InviteFriendForm from '@/components/InviteFriendForm';

export const CardOverviewPage = () => {
  const { user, currentBusinessId, currentBusiness } = useOutletContext<any>();
  const [userServices, setUserServices] = useState<any[]>([]);
  const [loadingServices, setLoadingServices] = useState(false);
  const [showAddService, setShowAddService] = useState(false);
  const [editingService, setEditingService] = useState<string | null>(null);
  const [newService, setNewService] = useState({
    category: '',
    name: '',
    description: '',
    keywords: '',
    price: ''
  });
  const [clientInfo, setClientInfo] = useState({
    businessName: '',
    businessType: '',
    address: '',
    workingHours: ''
  });
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [inviteSuccess, setInviteSuccess] = useState(false);
  const [showWizard, setShowWizard] = useState(false);
  const [wizardStep, setWizardStep] = useState<1 | 2 | 3>(1);
  const [yandexCardUrl, setYandexCardUrl] = useState<string>('');

  useEffect(() => {
    loadUserServices();
    loadClientInfo();
  }, [currentBusinessId]);

  const loadUserServices = async () => {
    if (!currentBusinessId) {
      setUserServices([]);
      return;
    }
    
    setLoadingServices(true);
    try {
      const token = localStorage.getItem('auth_token');
      const qs = currentBusinessId ? `?business_id=${currentBusinessId}` : '';
      const response = await fetch(`${window.location.origin}/api/services/list${qs}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await response.json();
      if (data.success) {
        setUserServices(data.services || []);
      }
    } catch (e) {
      console.error('Ошибка загрузки услуг:', e);
    } finally {
      setLoadingServices(false);
    }
  };

  const loadClientInfo = async () => {
    if (!currentBusinessId) {
      setClientInfo({
        businessName: '',
        businessType: '',
        address: '',
        workingHours: ''
      });
      return;
    }
    
    try {
      const qs = currentBusinessId ? `?business_id=${currentBusinessId}` : '';
      const response = await fetch(`${window.location.origin}/api/client-info${qs}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });
      if (response.ok) {
        const data = await response.json();
        setClientInfo({
          businessName: data.businessName || '',
          businessType: data.businessType || '',
          address: data.address || '',
          workingHours: data.workingHours || ''
        });
      }
    } catch (error) {
      console.error('Ошибка загрузки информации о бизнесе:', error);
    }
  };

  const addService = async () => {
    if (!newService.name.trim()) {
      setError('Название услуги обязательно');
      return;
    }

    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${window.location.origin}/api/services/add`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          category: newService.category || 'Общие услуги',
          name: newService.name,
          description: newService.description,
          keywords: newService.keywords.split(',').map(k => k.trim()).filter(k => k),
          price: newService.price,
          business_id: currentBusinessId
        })
      });

      const data = await response.json();
      if (data.success) {
        setNewService({ category: '', name: '', description: '', keywords: '', price: '' });
        setShowAddService(false);
        await loadUserServices();
        setSuccess('Услуга добавлена');
      } else {
        setError(data.error || 'Ошибка добавления услуги');
      }
    } catch (e: any) {
      setError('Ошибка добавления услуги: ' + e.message);
    }
  };

  const updateService = async (serviceId: string, updatedData: any) => {
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${window.location.origin}/api/services/update/${serviceId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(updatedData)
      });

      const data = await response.json();
      if (data.success) {
        setEditingService(null);
        await loadUserServices();
        setSuccess('Услуга обновлена');
      } else {
        setError(data.error || 'Ошибка обновления услуги');
      }
    } catch (e: any) {
      setError('Ошибка обновления услуги: ' + e.message);
    }
  };

  const deleteService = async (serviceId: string) => {
    if (!confirm('Вы уверены, что хотите удалить эту услугу?')) return;

    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${window.location.origin}/api/services/delete/${serviceId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });

      const data = await response.json();
      if (data.success) {
        await loadUserServices();
        setSuccess('Услуга удалена');
      } else {
        setError(data.error || 'Ошибка удаления услуги');
      }
    } catch (e: any) {
      setError('Ошибка удаления услуги: ' + e.message);
    }
  };

  const handleSaveYandexLink = async () => {
    if (!currentBusinessId) {
      setError('Сначала выберите бизнес');
      return;
    }
    if (!yandexCardUrl.trim()) {
      setError('Введите ссылку на карточку на картах');
      return;
    }

    try {
      const response = await fetch(`${window.location.origin}/api/business/${currentBusinessId}/yandex-link`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        },
        body: JSON.stringify({ yandex_url: yandexCardUrl })
      });

      const data = await response.json();
      if (response.ok && data.success) {
        setSuccess('Ссылка на карты сохранена и синхронизация запущена');
      } else {
        setError(data.error || 'Не удалось сохранить ссылку на карты');
      }
    } catch (e: any) {
      setError('Ошибка сохранения ссылки на карты: ' + e.message);
    }
  };

  const wizardNext = () => {
    if (wizardStep === 1) {
      handleSaveYandexLink();
    }
    setWizardStep((s) => (s < 3 ? ((s + 1) as 1 | 2 | 3) : s));
  };
  const wizardPrev = () => setWizardStep((s) => (s > 1 ? ((s - 1) as 1 | 2 | 3) : s));

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Обзор карточки</h1>
          <p className="text-gray-600 mt-1">Управляйте услугами и оптимизируйте карточку организации</p>
        </div>
        <Button onClick={() => setShowWizard(true)}>Мастер оптимизации</Button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      )}

      {success && (
        <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded">
          {success}
        </div>
      )}

      {/* Услуги */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex justify-between items-center mb-4">
          <div className="flex-1 pr-4">
            <h2 className="text-xl font-semibold text-gray-900">Услуги</h2>
            <p className="text-sm text-gray-600 mt-1">
              📋 Ниже в блоке "Настройте описания услуг для карточки компании на картах" загрузите ваш прайс-лист, мы обработаем наименования и описания услуг так, чтобы чаще появляться в поиске.
              <br/><br/>
              Эти наименования сохранятся в ваш список услуг автоматически.
              <br/><br/>
              Вы также можете внести их вручную или потом отредактировать.
            </p>
          </div>
          <Button onClick={() => setShowAddService(true)}>+ Добавить услугу</Button>
        </div>

        {/* Форма добавления услуги */}
        {showAddService && (
          <div className="mb-6 bg-gray-50 border border-gray-200 rounded-lg p-4">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Добавить новую услугу</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Категория</label>
                <input 
                  type="text" 
                  value={newService.category}
                  onChange={(e) => setNewService({...newService, category: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  placeholder="Например: Стрижки"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Название *</label>
                <input 
                  type="text" 
                  value={newService.name}
                  onChange={(e) => setNewService({...newService, name: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  placeholder="Например: Женская стрижка"
                />
              </div>
              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-1">Описание</label>
                <textarea 
                  value={newService.description}
                  onChange={(e) => setNewService({...newService, description: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  rows={3}
                  placeholder="Краткое описание услуги"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Ключевые слова</label>
                <input
                  type="text"
                  value={newService.keywords}
                  onChange={(e) => setNewService({...newService, keywords: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  placeholder="стрижка, укладка, окрашивание"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Цена</label>
                <input
                  type="text"
                  value={newService.price}
                  onChange={(e) => setNewService({...newService, price: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  placeholder="Например: 2000 руб"
                />
              </div>
            </div>
            <div className="flex gap-2 mt-4">
              <Button onClick={addService}>Добавить</Button>
              <Button onClick={() => setShowAddService(false)} variant="outline">Отмена</Button>
            </div>
          </div>
        )}

        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Категория</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Название</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Описание</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Цена</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Действия</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {loadingServices ? (
                <tr>
                  <td className="px-4 py-3 text-gray-500" colSpan={5}>Загрузка услуг...</td>
                </tr>
              ) : userServices.length === 0 ? (
                <tr>
                  <td className="px-4 py-3 text-gray-500" colSpan={5}>Данные появятся после добавления услуг</td>
                </tr>
              ) : (
                userServices.map((service, index) => (
                  <tr key={service.id || index}>
                    <td className="px-4 py-3 text-sm text-gray-900">{service.category}</td>
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">{service.name}</td>
                    <td className="px-4 py-3 text-sm text-gray-600">{service.description}</td>
                    <td className="px-4 py-3 text-sm text-gray-600">{service.price || '—'}</td>
                    <td className="px-4 py-3 text-sm">
                      <div className="flex gap-2">
                        <Button 
                          size="sm" 
                          variant="outline" 
                          onClick={() => setEditingService(service.id)}
                        >
                          Редактировать
                        </Button>
                        <Button 
                          size="sm"
                          variant="outline" 
                          onClick={() => deleteService(service.id)}
                          className="text-red-600 hover:text-red-700"
                        >
                          Удалить
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Работа с картами */}
      <div className="bg-white rounded-lg border border-gray-200">
        <Accordion type="single" collapsible defaultValue="yamaps-tools">
          <AccordionItem value="yamaps-tools">
            <AccordionTrigger className="px-6">
              <span className="text-xl font-semibold text-gray-900">Работа с картами</span>
            </AccordionTrigger>
            <AccordionContent>
              <div className="space-y-6 p-6">
                <div className="bg-gray-50 rounded-lg border border-gray-200 p-4">
                  <ServiceOptimizer businessName={clientInfo.businessName} businessId={currentBusinessId} />
                </div>
                <div className="bg-gray-50 rounded-lg border border-gray-200 p-4">
                  <ReviewReplyAssistant businessName={clientInfo.businessName} />
                </div>
                <div className="bg-gray-50 rounded-lg border border-gray-200 p-4">
                  <NewsGenerator services={(userServices||[]).map(s=>({ id: s.id, name: s.name }))} />
                </div>
              </div>
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </div>

      {/* Приглашения */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">Пригласить друга</h2>
        <InviteFriendForm
          onSuccess={() => setInviteSuccess(true)}
          onError={(error) => setError(error)}
        />
        {inviteSuccess && (
          <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded mt-4">
            Приглашение отправлено!
          </div>
        )}
      </div>

      {/* Модальное окно мастера оптимизации */}
      {showWizard && (
        <div className="fixed inset-0 bg-black/30 backdrop-blur-sm flex items-center justify-center z-[100]" onClick={() => setShowWizard(false)}>
          <div className="bg-white/95 backdrop-blur-md rounded-lg max-w-4xl max-h-[90vh] w-full mx-4 overflow-hidden shadow-2xl border-2 border-gray-300" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center p-4 border-b border-gray-200 bg-gradient-to-r from-white to-gray-50">
              <div className="flex items-center gap-3">
                <h2 className="text-2xl font-bold text-gray-900">Мастер оптимизации бизнеса</h2>
                <span className="text-sm text-gray-600 bg-gray-100 px-2 py-1 rounded">Шаг {wizardStep}/3</span>
              </div>
              <Button onClick={() => setShowWizard(false)} variant="outline" size="sm">✕</Button>
            </div>
            <div className="p-6 overflow-auto max-h-[calc(90vh-120px)] bg-gradient-to-br from-white to-gray-50/50">
              {/* Шаг 1 */}
              {wizardStep === 1 && (
                <div className="space-y-4">
                  <p className="text-gray-600 mb-4">Соберём ключевые данные по карточке, чтобы дать точные рекомендации.</p>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Вставьте ссылку на карточку вашего салона на картах.
                      </label>
                      <input
                        className="w-full px-3 py-2 border border-gray-300 rounded-md"
                        placeholder="https://yandex.ru/maps/org/..."
                        value={yandexCardUrl}
                        onChange={(e) => setYandexCardUrl(e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Рейтинг (0–5)</label>
                      <input className="w-full px-3 py-2 border border-gray-300 rounded-md" placeholder="4.6" />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Количество отзывов</label>
                      <input className="w-full px-3 py-2 border border-gray-300 rounded-md" placeholder="128" />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">Частота обновления фото</label>
                      <div className="flex flex-wrap gap-2">
                        {['Еженедельно','Ежемесячно','Раз в квартал','Редко','Не знаю'].map(x => (
                          <span key={x} className="px-3 py-1 rounded-md bg-gray-100 text-gray-700 text-sm cursor-pointer hover:bg-gray-200">{x}</span>
                        ))}
                      </div>
                    </div>
                    <div className="md:col-span-2">
                      <label className="block text-sm font-medium text-gray-700 mb-2">Новости (наличие/частота)</label>
                      <div className="flex flex-wrap gap-2 mb-3">
                        {['Да','Нет'].map(x => (<span key={x} className="px-3 py-1 rounded-md bg-gray-100 text-gray-700 text-sm cursor-pointer hover:bg-gray-200">{x}</span>))}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {['Еженедельно','Ежемесячно','Реже','По событию'].map(x => (
                          <span key={x} className="px-3 py-1 rounded-md bg-gray-100 text-gray-700 text-sm cursor-pointer hover:bg-gray-200">{x}</span>
                        ))}
                      </div>
                    </div>
                    <div className="md:col-span-2">
                      <label className="block text-sm font-medium text-gray-700 mb-1">Текущие тексты/услуги</label>
                      <textarea className="w-full px-3 py-2 border border-gray-300 rounded-md" rows={5} placeholder={"Стрижка мужская\nСтрижка женская\nОкрашивание"} />
                    </div>
                  </div>
                </div>
              )}
              {/* Шаг 2 */}
              {wizardStep === 2 && (
                <div className="space-y-4">
                  <p className="text-gray-600 mb-4">Опишите, как вы хотите звучать и чего избегать. Это задаст тон для всех текстов.</p>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">What do you like?</label>
                      <textarea className="w-full px-3 py-2 border border-gray-300 rounded-md" rows={4} placeholder="Лаконично, экспертно, заботливо, премиально…" />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">What do you dislike?</label>
                      <textarea className="w-full px-3 py-2 border border-gray-300 rounded-md" rows={4} placeholder="Без клише, без канцелярита, без агрессивных продаж…" />
                    </div>
                    <div className="md:col-span-2">
                      <label className="block text-sm font-medium text-gray-700 mb-2">Понравившиеся формулировки (до 5)</label>
                      <div className="space-y-2">
                        {[1,2,3,4,5].map(i => (
                          <input key={i} className="w-full px-3 py-2 border border-gray-300 rounded-md" placeholder="Например: Стрижка, которая держит форму и не требует укладки" />
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              )}
              {/* Шаг 3 */}
              {wizardStep === 3 && (
                <div className="space-y-4">
                  <p className="text-gray-600 mb-4">Немного цифр, чтобы план был реалистичным. Можно заполнить позже.</p>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Как давно работаете</label>
                      <div className="flex flex-wrap gap-2">
                        {['0–6 мес','6–12 мес','1–3 года','3+ лет'].map(x => (<span key={x} className="px-3 py-1 rounded-md bg-gray-100 text-gray-700 text-sm cursor-pointer hover:bg-gray-200">{x}</span>))}
                      </div>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Постоянные клиенты</label>
                      <input className="w-full px-3 py-2 border border-gray-300 rounded-md" placeholder="например, 150" />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">CRM</label>
                      <input className="w-full px-3 py-2 border border-gray-300 rounded-md" placeholder="Например: Yclients" />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Расположение</label>
                      <div className="flex flex-wrap gap-2">
                        {['Дом','ТЦ','Двор','Магистраль','Центр','Спальник','Около метро'].map(x => (<span key={x} className="px-3 py-1 rounded-md bg-gray-100 text-gray-700 text-sm cursor-pointer hover:bg-gray-200">{x}</span>))}
                      </div>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Средний чек (₽)</label>
                      <input className="w-full px-3 py-2 border border-gray-300 rounded-md" placeholder="2200" />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Выручка в месяц (₽)</label>
                      <input className="w-full px-3 py-2 border border-gray-300 rounded-md" placeholder="350000" />
                    </div>
                    <div className="md:col-span-2">
                      <label className="block text-sm font-medium text-gray-700 mb-1">Что нравится/не нравится в карточке</label>
                      <textarea className="w-full px-3 py-2 border border-gray-300 rounded-md" rows={4} placeholder="Нравится: фото, тон. Не нравится: мало отзывов, нет новостей…" />
                    </div>
                  </div>
                </div>
              )}
              <div className="mt-6 flex justify-between pt-4 border-t border-gray-200">
                <Button variant="outline" onClick={wizardPrev} disabled={wizardStep===1}>Назад</Button>
                {wizardStep < 3 ? (
                  <Button onClick={wizardNext}>Продолжить</Button>
                ) : (
                  <Button onClick={() => {setShowWizard(false); window.location.href = "/sprint";}}>Сформировать план</Button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

