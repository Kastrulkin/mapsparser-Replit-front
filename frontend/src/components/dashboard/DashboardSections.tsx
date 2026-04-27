import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import InviteFriendForm from "@/components/InviteFriendForm";
import ServiceOptimizer from "@/components/ServiceOptimizer";
import ReviewReplyAssistant from "@/components/ReviewReplyAssistant";
import NewsGenerator from "@/components/NewsGenerator";
import FinancialMetrics from "@/components/FinancialMetrics";
import NetworkHealthDashboard from "@/components/NetworkHealthDashboard";
import ROICalculator from "@/components/ROICalculator";
import TransactionForm from "@/components/TransactionForm";
import TelegramConnection from "@/components/TelegramConnection";
import { ExternalIntegrations } from "@/components/ExternalIntegrations";
import { NetworkSwitcher } from "@/components/NetworkSwitcher";
import { NetworkDashboard } from "@/components/NetworkDashboard";

export type DashboardMapLink = {
  id?: string;
  url: string;
  mapType?: string;
  createdAt?: string;
};

export type DashboardClientInfo = {
  businessName: string;
  businessType: string;
  address: string;
  workingHours: string;
  mapLinks: DashboardMapLink[];
};

export type DashboardBusiness = {
  id: string;
  name: string;
  description?: string;
  business_type?: string;
  address?: string;
  working_hours?: string;
  yandex_url?: string;
  network_id?: string;
  moderation_status?: string;
  entity_group?: string;
  is_lead_business?: boolean;
  owner_name?: string;
};

export type DashboardService = {
  id: string;
  category?: string;
  name: string;
  description?: string;
  price?: string;
};

export type DashboardTabId = 'overview' | 'finance' | 'progress' | 'network' | 'settings';

type NewServiceState = {
  category: string;
  name: string;
  description: string;
  keywords: string;
  price: string;
};

type ProfileFormState = {
  email: string;
  phone: string;
  name: string;
  yandexUrl: string;
};

type DashboardWelcomeSectionProps = {
  currentBusiness: DashboardBusiness | null;
  profileCompletion: number;
};

export const DashboardWelcomeSection = ({
  currentBusiness,
  profileCompletion,
}: DashboardWelcomeSectionProps) => (
  <div className="mb-6 bg-gradient-to-br from-white via-gray-50/50 to-white rounded-lg border-2 border-gray-200 shadow-md p-4">
    <p className="text-gray-800 mb-2">👋 Добро пожаловать в <span className="font-semibold">ЛокалОС</span>!</p>
    {currentBusiness ? (
      <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
        <p className="text-sm text-blue-800">
          <span className="font-medium">Текущий бизнес:</span> {currentBusiness.name}
          {currentBusiness.description ? (
            <span className="block text-xs text-blue-600 mt-1">{currentBusiness.description}</span>
          ) : null}
        </p>
      </div>
    ) : null}
    <p className="text-gray-600 text-sm">
      Это ваш личный центр управления ростом салона.
    </p>
    <p className="text-gray-600 text-sm mt-2">
      Заполните данные о себе и бизнесе — это первый шаг. Далее вы сможете совершенствовать процесс и отслеживать положительные изменения.
    </p>
    <p className="text-gray-600 text-sm mt-2">💡 Помните: вы платите только за результат — 7% от реального роста.</p>

    <div className="mt-4">
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm text-gray-700">Заполненность профиля</span>
        <span className="text-sm font-medium text-orange-600">{profileCompletion}%</span>
      </div>
      <div className="w-full bg-gray-200 rounded h-3 overflow-hidden">
        <div
          className={`h-3 rounded ${profileCompletion >= 80 ? 'bg-green-500' : profileCompletion >= 50 ? 'bg-yellow-500' : 'bg-orange-500'}`}
          style={{ width: `${profileCompletion}%` }}
        />
      </div>
    </div>
  </div>
);

type DashboardTabsShellProps = {
  activeTab: DashboardTabId;
  onTabChange: (tab: DashboardTabId) => void;
};

const dashboardTabs: Array<{ id: DashboardTabId; label: string }> = [
  { id: 'overview', label: '📊 Обзор' },
  { id: 'finance', label: '💰 Финансы' },
  { id: 'progress', label: '🎯 Прогресс' },
  { id: 'settings', label: '⚙️ Настройки' },
];

export const DashboardTabsShell = ({
  activeTab,
  onTabChange,
}: DashboardTabsShellProps) => (
  <div className="mb-6 bg-gradient-to-r from-gray-50 to-white rounded-lg border-2 border-gray-200 shadow-sm p-4">
    <div className="flex space-x-1 bg-gray-100 p-1 rounded-lg">
      {dashboardTabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onTabChange(tab.id)}
          className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-colors ${activeTab === tab.id
            ? 'bg-white text-gray-900 shadow-sm'
            : 'text-gray-600 hover:text-gray-900'
            }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  </div>
);

type DashboardProfileSectionProps = {
  form: ProfileFormState;
  editMode: boolean;
  onEdit: () => void;
  onCancel: () => void;
  onSave: () => void;
  onFormChange: (next: ProfileFormState) => void;
};

export const DashboardProfileSection = ({
  form,
  editMode,
  onEdit,
  onCancel,
  onSave,
  onFormChange,
}: DashboardProfileSectionProps) => (
  <div className="mb-8 bg-gradient-to-br from-white via-gray-50 to-white rounded-lg border-2 border-gray-300 shadow-md p-4">
    <div className="flex items-center justify-between mb-4">
      <h2 className="text-xl font-semibold text-gray-900">Профиль</h2>
      {!editMode && <Button onClick={onEdit}>Редактировать</Button>}
    </div>
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
        <input
          type="email"
          value={form.email}
          disabled
          className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-50"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Имя</label>
        <input
          type="text"
          value={form.name}
          onChange={(event) => onFormChange({ ...form, name: event.target.value })}
          disabled={!editMode}
          className="w-full px-3 py-2 border border-gray-300 rounded-md"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Телефон</label>
        <input
          type="tel"
          value={form.phone}
          onChange={(event) => onFormChange({ ...form, phone: event.target.value })}
          disabled={!editMode}
          className="w-full px-3 py-2 border border-gray-300 rounded-md"
        />
      </div>
    </div>
    {editMode && (
      <div className="mt-4 flex justify-end">
        <div className="flex gap-2">
          <Button onClick={onSave}>Сохранить</Button>
          <Button onClick={onCancel} variant="outline">Отмена</Button>
        </div>
      </div>
    )}
  </div>
);

type DashboardBusinessInfoSectionProps = {
  clientInfo: DashboardClientInfo;
  editClientInfo: boolean;
  savingClientInfo: boolean;
  onEdit: () => void;
  onCancel: () => void;
  onSave: () => void;
  onClientInfoChange: (next: DashboardClientInfo) => void;
};

export const DashboardBusinessInfoSection = ({
  clientInfo,
  editClientInfo,
  savingClientInfo,
  onEdit,
  onCancel,
  onSave,
  onClientInfoChange,
}: DashboardBusinessInfoSectionProps) => (
  <div className="mb-8 bg-gradient-to-br from-white via-orange-50/30 to-white rounded-lg border-2 border-orange-200/50 shadow-md p-4">
    <div className="flex items-center justify-between mb-4">
      <h2 className="text-xl font-semibold text-gray-900">Информация о бизнесе</h2>
      {!editClientInfo && <Button onClick={onEdit}>Редактировать</Button>}
    </div>
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Название бизнеса</label>
        <input
          type="text"
          value={clientInfo.businessName}
          onChange={(event) => onClientInfoChange({ ...clientInfo, businessName: event.target.value })}
          disabled={!editClientInfo}
          className="w-full px-3 py-2 border border-gray-300 rounded-md"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Тип бизнеса</label>
        {editClientInfo ? (
          <Select
            value={clientInfo.businessType || "other"}
            onValueChange={(value) => onClientInfoChange({ ...clientInfo, businessType: value })}
          >
            <SelectTrigger>
              <SelectValue placeholder="Выберите тип" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="beauty_salon">Салон красоты</SelectItem>
              <SelectItem value="barbershop">Барбершоп</SelectItem>
              <SelectItem value="spa">SPA/Wellness</SelectItem>
              <SelectItem value="nail_studio">Ногтевая студия</SelectItem>
              <SelectItem value="cosmetology">Косметология</SelectItem>
              <SelectItem value="massage">Массаж</SelectItem>
              <SelectItem value="brows_lashes">Брови и ресницы</SelectItem>
              <SelectItem value="makeup">Макияж</SelectItem>
              <SelectItem value="tanning">Солярий</SelectItem>
              <SelectItem value="auto_service">СТО (Автосервис)</SelectItem>
              <SelectItem value="gas_station">АЗС (Автозаправка)</SelectItem>
              <SelectItem value="cafe">Кафе</SelectItem>
              <SelectItem value="school">Школа</SelectItem>
              <SelectItem value="workshop">Мастерская</SelectItem>
              <SelectItem value="shoe_repair">Ремонт обуви</SelectItem>
              <SelectItem value="gym">Спортзал</SelectItem>
              <SelectItem value="shawarma">Шаверма</SelectItem>
              <SelectItem value="theater">Театр</SelectItem>
              <SelectItem value="hotel">Отель</SelectItem>
              <SelectItem value="guest_house">Гостевой дом</SelectItem>
              <SelectItem value="other">Другое</SelectItem>
            </SelectContent>
          </Select>
        ) : (
          <input
            type="text"
            value={clientInfo.businessType}
            disabled
            className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-50"
            readOnly
          />
        )}
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Адрес</label>
        <input
          type="text"
          value={clientInfo.address}
          onChange={(event) => onClientInfoChange({ ...clientInfo, address: event.target.value })}
          disabled={!editClientInfo}
          className="w-full px-3 py-2 border border-gray-300 rounded-md"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Режим работы</label>
        <input
          type="text"
          value={clientInfo.workingHours}
          onChange={(event) => onClientInfoChange({ ...clientInfo, workingHours: event.target.value })}
          disabled={!editClientInfo}
          className="w-full px-3 py-2 border border-gray-300 rounded-md"
        />
      </div>
    </div>
    {editClientInfo && (
      <div className="mt-4 flex justify-end">
        <div className="flex gap-2">
          <Button onClick={onSave} disabled={savingClientInfo}>
            {savingClientInfo ? 'Сохранение...' : 'Сохранить'}
          </Button>
          <Button onClick={onCancel} variant="outline">Отмена</Button>
        </div>
      </div>
    )}
  </div>
);

type DashboardMapsToolsSectionProps = {
  currentBusinessId: string | null;
  clientInfo: DashboardClientInfo;
  connectedMapTypes: string[];
  connectedMapLabels: string[];
  refreshingMapsData: boolean;
  onRefreshMapsData: () => void;
  userServices: DashboardService[];
};

export const DashboardMapsToolsSection = ({
  currentBusinessId,
  clientInfo,
  connectedMapTypes,
  connectedMapLabels,
  refreshingMapsData,
  onRefreshMapsData,
  userServices,
}: DashboardMapsToolsSectionProps) => (
  <div className="mb-8 bg-gradient-to-br from-white via-gray-50 to-white rounded-lg border-2 border-gray-300 shadow-md">
    <Accordion type="single" collapsible defaultValue="yamaps-tools">
      <AccordionItem value="yamaps-tools">
        <AccordionTrigger className="px-4">
          <span className="text-xl font-semibold text-gray-900">Работа с картами</span>
        </AccordionTrigger>
        <AccordionContent>
          <div className="space-y-8">
            <div className="bg-white rounded-lg border border-gray-200 p-4">
              <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                <div className="space-y-2">
                  <div className="text-lg font-semibold text-gray-900">Обновить данные с карт</div>
                  <p className="text-sm text-gray-600">
                    Кнопка запускает Apify-парсинг по уже добавленным ссылкам на карты для текущего бизнеса.
                    Для каждой подключённой карты используется свой коннектор: Яндекс, 2ГИС, Google Maps или Apple Maps.
                  </p>
                  <p className="text-sm text-gray-500">
                    Сейчас подключено: {connectedMapLabels.length > 0 ? connectedMapLabels.join(', ') : 'карты ещё не добавлены'}.
                  </p>
                  <p className="text-xs text-gray-500">
                    После запуска задачи попадают в очередь парсинга. Когда Apify завершит сбор данных, показатели карточки и рекомендации обновятся.
                  </p>
                </div>
                <div className="flex flex-col items-stretch gap-2 md:min-w-[260px]">
                  <Button
                    onClick={onRefreshMapsData}
                    disabled={refreshingMapsData || !currentBusinessId || connectedMapTypes.length === 0}
                  >
                    {refreshingMapsData ? 'Запускаем обновление…' : 'Обновить данные с карт'}
                  </Button>
                  <div className="text-xs text-gray-500">
                    Запускается только по тем картам, которые уже сохранены в профиле бизнеса.
                  </div>
                </div>
              </div>
            </div>
            <div className="bg-white rounded-lg border border-gray-200 p-4">
              <ServiceOptimizer businessName={clientInfo.businessName} businessId={currentBusinessId} />
            </div>
            <div className="bg-white rounded-lg border border-gray-200 p-4">
              <ReviewReplyAssistant businessName={clientInfo.businessName} />
            </div>
            <div className="bg-white rounded-lg border border-gray-200 p-4">
              <NewsGenerator services={userServices.map((service) => ({ id: service.id, name: service.name }))} />
            </div>
          </div>
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  </div>
);

type DashboardOverviewSectionProps = {
  showAddService: boolean;
  newService: NewServiceState;
  loadingServices: boolean;
  userServices: DashboardService[];
  onShowAddService: () => void;
  onHideAddService: () => void;
  onNewServiceChange: (next: NewServiceState) => void;
  onAddService: () => void;
  onDeleteService: (serviceId: string) => void;
};

export const DashboardOverviewSection = ({
  showAddService,
  newService,
  loadingServices,
  userServices,
  onShowAddService,
  onHideAddService,
  onNewServiceChange,
  onAddService,
  onDeleteService,
}: DashboardOverviewSectionProps) => (
  <div className="mb-8 bg-gradient-to-br from-white via-orange-50/20 to-white rounded-lg border-2 border-orange-200/50 shadow-md p-4">
    <div className="flex justify-between items-center mb-4">
      <div className="flex-1 pr-4">
        <h2 className="text-xl font-semibold text-gray-900">Услуги</h2>
        <p className="text-sm text-gray-600 mt-1">
          📋 Ниже в блоке "Настройте описания услуг для карточки компании на картах" загрузите ваш прайс-лист, мы обработаем наименования и описания услуг так, чтобы чаще появляться в поиске.
          <br /><br />
          Эти наименования сохранятся в ваш список услуг автоматически.
          <br /><br />
          Вы также можете внести их вручную или потом отредактировать.
        </p>
      </div>
      <Button onClick={onShowAddService}>+ Добавить услугу</Button>
    </div>

    {showAddService && (
      <div className="mb-6 bg-gray-50 border border-gray-200 rounded-lg p-4">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Добавить новую услугу</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Категория</label>
            <input
              type="text"
              value={newService.category}
              onChange={(event) => onNewServiceChange({ ...newService, category: event.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
              placeholder="Например: Стрижки"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Название *</label>
            <input
              type="text"
              value={newService.name}
              onChange={(event) => onNewServiceChange({ ...newService, name: event.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
              placeholder="Например: Женская стрижка"
            />
          </div>
          <div className="md:col-span-2">
            <label className="block text-sm font-medium text-gray-700 mb-1">Описание</label>
            <textarea
              value={newService.description}
              onChange={(event) => onNewServiceChange({ ...newService, description: event.target.value })}
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
              onChange={(event) => onNewServiceChange({ ...newService, keywords: event.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
              placeholder="стрижка, укладка, окрашивание"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Цена</label>
            <input
              type="text"
              value={newService.price}
              onChange={(event) => onNewServiceChange({ ...newService, price: event.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
              placeholder="Например: 2000 руб"
            />
          </div>
        </div>
        <div className="flex gap-2 mt-4">
          <Button onClick={onAddService}>Добавить</Button>
          <Button onClick={onHideAddService} variant="outline">Отмена</Button>
        </div>
      </div>
    )}

    <div className="overflow-x-auto bg-white border border-gray-200 rounded-lg">
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
                      onClick={() => onDeleteService(service.id)}
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
);

type DashboardInviteSectionProps = {
  inviteSuccess: boolean;
  onSuccess: () => void;
  onError: (message: string) => void;
};

export const DashboardInviteSection = ({
  inviteSuccess,
  onSuccess,
  onError,
}: DashboardInviteSectionProps) => (
  <div className="mb-8">
    <h2 className="text-xl font-semibold text-gray-900 mb-4">Пригласить друга</h2>
    <InviteFriendForm
      onSuccess={onSuccess}
      onError={onError}
    />
    {inviteSuccess ? (
      <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded mt-4">
        Приглашение отправлено!
      </div>
    ) : null}
  </div>
);

type DashboardFinanceSectionProps = {
  showTransactionForm: boolean;
  onToggleTransactionForm: () => void;
  onTransactionSuccess: () => void;
  onTransactionCancel: () => void;
};

export const DashboardFinanceSection = ({
  showTransactionForm,
  onToggleTransactionForm,
  onTransactionSuccess,
  onTransactionCancel,
}: DashboardFinanceSectionProps) => (
  <div className="space-y-6">
    <div className="flex justify-between items-center">
      <h2 className="text-xl font-semibold text-gray-900">💰 Финансовая панель</h2>
      <Button
        onClick={onToggleTransactionForm}
        className="bg-green-600 hover:bg-green-700"
      >
        {showTransactionForm ? 'Скрыть форму' : '+ Добавить транзакцию'}
      </Button>
    </div>

    {showTransactionForm ? (
      <TransactionForm
        onSuccess={onTransactionSuccess}
        onCancel={onTransactionCancel}
      />
    ) : null}

    <FinancialMetrics />
    <ROICalculator />
  </div>
);

type DashboardProgressSectionProps = {
  currentNetworkId: string | null;
  currentBusinessId: string | null;
};

export const DashboardProgressSection = ({
  currentNetworkId,
  currentBusinessId,
}: DashboardProgressSectionProps) => (
  <div className="space-y-6">
    <h2 className="text-xl font-semibold text-gray-900">📊 Состояние сети</h2>
    <NetworkHealthDashboard
      networkId={currentNetworkId}
      businessId={currentBusinessId}
    />
    <FinancialMetrics />
  </div>
);

type DashboardSettingsSectionProps = {
  currentBusinessId: string | null;
};

export const DashboardSettingsSection = ({
  currentBusinessId,
}: DashboardSettingsSectionProps) => (
  <div className="space-y-6">
    <h2 className="text-xl font-semibold text-gray-900">⚙️ Настройки</h2>
    <TelegramConnection />
    <ExternalIntegrations currentBusinessId={currentBusinessId} />
  </div>
);

type DashboardNetworkSectionProps = {
  currentNetworkId: string | null;
  currentLocationId?: string | null;
  onLocationChange: (locationId: string) => void;
};

export const DashboardNetworkSection = ({
  currentNetworkId,
  currentLocationId,
  onLocationChange,
}: DashboardNetworkSectionProps) => {
  if (!currentNetworkId) {
    return null;
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-semibold text-gray-900">🌐 Дашборд сети</h2>
        <NetworkSwitcher
          networkId={currentNetworkId}
          currentLocationId={currentLocationId || undefined}
          onLocationChange={onLocationChange}
        />
      </div>
      <NetworkDashboard networkId={currentNetworkId} />
    </div>
  );
};

type DashboardTabContentProps = {
  activeTab: DashboardTabId;
  showTransactionForm: boolean;
  onToggleTransactionForm: () => void;
  onTransactionSuccess: () => void;
  onTransactionCancel: () => void;
  currentNetworkId: string | null;
  currentBusinessId: string | null;
  currentLocationId?: string | null;
  onLocationChange: (locationId: string) => void;
  showAddService: boolean;
  newService: NewServiceState;
  loadingServices: boolean;
  userServices: DashboardService[];
  onShowAddService: () => void;
  onHideAddService: () => void;
  onNewServiceChange: (next: NewServiceState) => void;
  onAddService: () => void;
  onDeleteService: (serviceId: string) => void;
};

export const DashboardTabContent = ({
  activeTab,
  showTransactionForm,
  onToggleTransactionForm,
  onTransactionSuccess,
  onTransactionCancel,
  currentNetworkId,
  currentBusinessId,
  currentLocationId,
  onLocationChange,
  showAddService,
  newService,
  loadingServices,
  userServices,
  onShowAddService,
  onHideAddService,
  onNewServiceChange,
  onAddService,
  onDeleteService,
}: DashboardTabContentProps) => {
  if (activeTab === 'finance') {
    return (
      <DashboardFinanceSection
        showTransactionForm={showTransactionForm}
        onToggleTransactionForm={onToggleTransactionForm}
        onTransactionSuccess={onTransactionSuccess}
        onTransactionCancel={onTransactionCancel}
      />
    );
  }

  if (activeTab === 'progress') {
    return (
      <DashboardProgressSection
        currentNetworkId={currentNetworkId}
        currentBusinessId={currentBusinessId}
      />
    );
  }

  if (activeTab === 'settings') {
    return <DashboardSettingsSection currentBusinessId={currentBusinessId} />;
  }

  if (activeTab === 'network' && currentNetworkId) {
    return (
      <DashboardNetworkSection
        currentNetworkId={currentNetworkId}
        currentLocationId={currentLocationId}
        onLocationChange={onLocationChange}
      />
    );
  }

  return (
    <DashboardOverviewSection
      showAddService={showAddService}
      newService={newService}
      loadingServices={loadingServices}
      userServices={userServices}
      onShowAddService={onShowAddService}
      onHideAddService={onHideAddService}
      onNewServiceChange={onNewServiceChange}
      onAddService={onAddService}
      onDeleteService={onDeleteService}
    />
  );
};

type DashboardWizardModalProps = {
  open: boolean;
  wizardStep: 1 | 2 | 3;
  yandexCardUrl: string;
  onYandexCardUrlChange: (value: string) => void;
  onClose: () => void;
  onPrevious: () => void;
  onNext: () => void;
  onComplete: () => void;
};

export const DashboardWizardModal = ({
  open,
  wizardStep,
  yandexCardUrl,
  onYandexCardUrlChange,
  onClose,
  onPrevious,
  onNext,
  onComplete,
}: DashboardWizardModalProps) => {
  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 bg-black/30 backdrop-blur-sm flex items-center justify-center z-[100]" onClick={onClose}>
      <div className="bg-white/95 backdrop-blur-md rounded-lg max-w-4xl max-h-[90vh] w-full mx-4 overflow-hidden shadow-2xl border-2 border-gray-300" onClick={(event) => event.stopPropagation()}>
        <div className="flex justify-between items-center p-4 border-b border-gray-200 bg-gradient-to-r from-white to-gray-50">
          <div className="flex items-center gap-3">
            <h2 className="text-2xl font-bold text-gray-900">Мастер оптимизации бизнеса</h2>
            <span className="text-sm text-gray-600 bg-gray-100 px-2 py-1 rounded">Шаг {wizardStep}/3</span>
          </div>
          <Button onClick={onClose} variant="outline" size="sm">✕</Button>
        </div>
        <div className="p-6 overflow-auto max-h-[calc(90vh-120px)] bg-gradient-to-br from-white to-gray-50/50">
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
                    onChange={(event) => onYandexCardUrlChange(event.target.value)}
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
                    {['Еженедельно', 'Ежемесячно', 'Раз в квартал', 'Редко', 'Не знаю'].map((value) => (
                      <span key={value} className="px-3 py-1 rounded-md bg-gray-100 text-gray-700 text-sm cursor-pointer hover:bg-gray-200">{value}</span>
                    ))}
                  </div>
                </div>
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-2">Новости (наличие/частота)</label>
                  <div className="flex flex-wrap gap-2 mb-3">
                    {['Да', 'Нет'].map((value) => (
                      <span key={value} className="px-3 py-1 rounded-md bg-gray-100 text-gray-700 text-sm cursor-pointer hover:bg-gray-200">{value}</span>
                    ))}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {['Еженедельно', 'Ежемесячно', 'Реже', 'По событию'].map((value) => (
                      <span key={value} className="px-3 py-1 rounded-md bg-gray-100 text-gray-700 text-sm cursor-pointer hover:bg-gray-200">{value}</span>
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
                    {[1, 2, 3, 4, 5].map((value) => (
                      <input key={value} className="w-full px-3 py-2 border border-gray-300 rounded-md" placeholder="Например: Стрижка, которая держит форму и не требует укладки" />
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
          {wizardStep === 3 && (
            <div className="space-y-4">
              <p className="text-gray-600 mb-4">Немного цифр, чтобы план был реалистичным. Можно заполнить позже.</p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Как давно работаете</label>
                  <div className="flex flex-wrap gap-2">
                    {['0–6 мес', '6–12 мес', '1–3 года', '3+ лет'].map((value) => (
                      <span key={value} className="px-3 py-1 rounded-md bg-gray-100 text-gray-700 text-sm cursor-pointer hover:bg-gray-200">{value}</span>
                    ))}
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
                    {['Дом', 'ТЦ', 'Двор', 'Магистраль', 'Центр', 'Спальник', 'Около метро'].map((value) => (
                      <span key={value} className="px-3 py-1 rounded-md bg-gray-100 text-gray-700 text-sm cursor-pointer hover:bg-gray-200">{value}</span>
                    ))}
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
            <Button variant="outline" onClick={onPrevious} disabled={wizardStep === 1}>Назад</Button>
            {wizardStep < 3 ? (
              <Button onClick={onNext}>Продолжить</Button>
            ) : (
              <Button onClick={onComplete}>Сформировать план</Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

type DashboardReportModalProps = {
  reportId: string | null;
  loading: boolean;
  reportContent: string;
  onClose: () => void;
};

export const DashboardReportModal = ({
  reportId,
  loading,
  reportContent,
  onClose,
}: DashboardReportModalProps) => {
  if (!reportId) {
    return null;
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg max-w-4xl max-h-[90vh] w-full mx-4 overflow-hidden">
        <div className="flex justify-between items-center p-4 border-b">
          <h3 className="text-lg font-semibold">Просмотр отчёта</h3>
          <Button onClick={onClose} variant="outline">
            Закрыть
          </Button>
        </div>
        <div className="p-4 overflow-auto max-h-[calc(90vh-80px)]">
          {loading ? (
            <div className="text-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mx-auto"></div>
              <p className="mt-2 text-gray-600">Загрузка отчёта...</p>
            </div>
          ) : (
            <div dangerouslySetInnerHTML={{ __html: reportContent }} />
          )}
        </div>
      </div>
    </div>
  );
};
