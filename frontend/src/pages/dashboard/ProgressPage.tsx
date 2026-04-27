import { useEffect, useState } from 'react';
import { useNavigate, useOutletContext } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { ArrowRight, RefreshCw } from 'lucide-react';

import { BusinessHealthWidget } from '@/components/business/BusinessHealthWidget';
import CardAuditPanel from '@/components/CardAuditPanel';
import MapParseTable from '@/components/MapParseTable';
import NetworkHealthDashboard from '@/components/NetworkHealthDashboard';
import { useLanguage } from '@/i18n/LanguageContext';
import { NetworkDashboardPage } from './network/NetworkDashboardPage';
import {
  DashboardActionPanel,
  DashboardCompactMetricsRow,
  DashboardPageHeader,
  DashboardSection,
} from '@/components/dashboard/DashboardPrimitives';

const PROGRESS_FIRST_RUN_COPY: Record<string, {
  preAuditTitle: string;
  preAuditBody: string;
  whereAuditTitle: string;
  whereAuditNoMapBody: string;
  statusMissingMap: string;
  goToProfile: string;
}> = {
  ru: {
    preAuditTitle: 'Что нужно сделать перед первым аудитом',
    preAuditBody: 'Откройте «Профиль и бизнес», сохраните ссылку на карту и вернитесь сюда для запуска сбора.',
    whereAuditTitle: 'Где смотреть аудит карточки',
    whereAuditNoMapBody: 'Сначала сохраните ссылку на карту в «Профиль и бизнес». Потом можно запускать сбор данных.',
    statusMissingMap: 'Нужна ссылка на карту',
    goToProfile: 'Перейти в «Профиль и бизнес»',
  },
  en: {
    preAuditTitle: 'What to do before the first audit',
    preAuditBody: 'Open “Profile & Business”, save the map link, and return here to start data collection.',
    whereAuditTitle: 'Where to view the card audit',
    whereAuditNoMapBody: 'First save the map link in “Profile & Business”. Then you can start data collection.',
    statusMissingMap: 'Map link required',
    goToProfile: 'Go to Profile & Business',
  },
  ar: {
    preAuditTitle: 'ما المطلوب قبل أول تدقيق',
    preAuditBody: 'افتح «الملف الشخصي والنشاط التجاري»، احفظ رابط البطاقة، ثم ارجع إلى هنا لبدء جمع البيانات.',
    whereAuditTitle: 'أين تشاهد تدقيق البطاقة',
    whereAuditNoMapBody: 'احفظ رابط البطاقة أولاً في «الملف الشخصي والنشاط التجاري»، ثم يمكنك بدء جمع البيانات.',
    statusMissingMap: 'رابط الخريطة مطلوب',
    goToProfile: 'الانتقال إلى الملف الشخصي والنشاط التجاري',
  },
  de: {
    preAuditTitle: 'Was vor dem ersten Audit zu tun ist',
    preAuditBody: 'Öffnen Sie „Profil & Unternehmen“, speichern Sie den Kartenlink und kehren Sie dann hierher zurück, um die Datenerfassung zu starten.',
    whereAuditTitle: 'Wo Sie das Karten-Audit sehen',
    whereAuditNoMapBody: 'Speichern Sie zuerst den Kartenlink in „Profil & Unternehmen“. Danach können Sie die Datenerfassung starten.',
    statusMissingMap: 'Kartenlink erforderlich',
    goToProfile: 'Zu Profil & Unternehmen',
  },
  el: {
    preAuditTitle: 'Τι πρέπει να κάνετε πριν από τον πρώτο έλεγχο',
    preAuditBody: 'Ανοίξτε το «Προφίλ & Επιχείρηση», αποθηκεύστε τον σύνδεσμο χάρτη και επιστρέψτε εδώ για να ξεκινήσει η συλλογή δεδομένων.',
    whereAuditTitle: 'Πού να δείτε τον έλεγχο της κάρτας',
    whereAuditNoMapBody: 'Αποθηκεύστε πρώτα τον σύνδεσμο χάρτη στο «Προφίλ & Επιχείρηση». Μετά μπορείτε να ξεκινήσετε τη συλλογή δεδομένων.',
    statusMissingMap: 'Απαιτείται σύνδεσμος χάρτη',
    goToProfile: 'Μετάβαση στο Προφίλ & Επιχείρηση',
  },
  es: {
    preAuditTitle: 'Qué hacer antes de la primera auditoría',
    preAuditBody: 'Abre «Perfil y negocio», guarda el enlace del mapa y vuelve aquí para iniciar la recopilación de datos.',
    whereAuditTitle: 'Dónde ver la auditoría de la ficha',
    whereAuditNoMapBody: 'Primero guarda el enlace del mapa en «Perfil y negocio». Después podrás iniciar la recopilación de datos.',
    statusMissingMap: 'Se necesita un enlace del mapa',
    goToProfile: 'Ir a Perfil y negocio',
  },
  fr: {
    preAuditTitle: 'Que faire avant le premier audit',
    preAuditBody: 'Ouvrez « Profil et entreprise », enregistrez le lien de la carte puis revenez ici pour lancer la collecte des données.',
    whereAuditTitle: 'Où voir l’audit de la fiche',
    whereAuditNoMapBody: 'Enregistrez d’abord le lien de la carte dans « Profil et entreprise ». Vous pourrez ensuite lancer la collecte des données.',
    statusMissingMap: 'Lien de carte requis',
    goToProfile: 'Aller à Profil et entreprise',
  },
  ha: {
    preAuditTitle: 'Abin da za a yi kafin binciken farko',
    preAuditBody: 'Buɗe “Profile & Business”, ajiye hanyar taswira, sannan a dawo nan don fara tara bayanai.',
    whereAuditTitle: 'Inda za a ga binciken katin',
    whereAuditNoMapBody: 'Da farko a ajiye hanyar taswira a cikin “Profile & Business”. Bayan haka za a iya fara tara bayanai.',
    statusMissingMap: 'Ana bukatar hanyar taswira',
    goToProfile: 'Je zuwa Profile & Business',
  },
  th: {
    preAuditTitle: 'สิ่งที่ต้องทำก่อนการตรวจสอบครั้งแรก',
    preAuditBody: 'เปิด “Profile & Business” บันทึกลิงก์แผนที่ แล้วกลับมาที่นี่เพื่อเริ่มเก็บข้อมูล',
    whereAuditTitle: 'ดูผลตรวจสอบการ์ดได้ที่ไหน',
    whereAuditNoMapBody: 'บันทึกลิงก์แผนที่ใน “Profile & Business” ก่อน แล้วจึงเริ่มเก็บข้อมูลได้',
    statusMissingMap: 'ต้องมีลิงก์แผนที่',
    goToProfile: 'ไปที่ Profile & Business',
  },
  tr: {
    preAuditTitle: 'İlk denetimden önce ne yapılmalı',
    preAuditBody: '“Profil ve İşletme” bölümünü açın, harita bağlantısını kaydedin ve veri toplamayı başlatmak için buraya geri dönün.',
    whereAuditTitle: 'Kart denetimi nerede görüntülenir',
    whereAuditNoMapBody: 'Önce harita bağlantısını “Profil ve İşletme” bölümüne kaydedin. Sonra veri toplamayı başlatabilirsiniz.',
    statusMissingMap: 'Harita bağlantısı gerekli',
    goToProfile: 'Profil ve İşletme bölümüne git',
  },
};

export const ProgressPage = () => {
  const navigate = useNavigate();
  const { currentBusinessId } = useOutletContext<any>();
  const [isNetworkMaster, setIsNetworkMaster] = useState(false);
  const [isNetworkMember, setIsNetworkMember] = useState(false);
  const [resolvedNetworkId, setResolvedNetworkId] = useState<string | null>(null);
  const [networkStatusLoading, setNetworkStatusLoading] = useState(true);
  const [parseStatus, setParseStatus] = useState<'idle' | 'processing' | 'completed' | 'done' | 'error' | 'queued'>('idle');
  const [parseStatusError, setParseStatusError] = useState<string | null>(null);
  const [parseRefreshPolicy, setParseRefreshPolicy] = useState<{
    can_refresh: boolean;
    reason: string | null;
    message: string | null;
    cooldown_days: number;
    last_completed_at: string | null;
    cooldown_until: string | null;
    invite_override_available: boolean;
    accepted_invites_count: number;
  }>({
    can_refresh: true,
    reason: null,
    message: null,
    cooldown_days: 7,
    last_completed_at: null,
    cooldown_until: null,
    invite_override_available: false,
    accepted_invites_count: 0,
  });
  const [refreshKey, setRefreshKey] = useState(0);
  const [hasConfiguredMapLink, setHasConfiguredMapLink] = useState(false);
  const [isMapLinkLoading, setIsMapLinkLoading] = useState(true);
  const { t, language } = useLanguage();
  const isRu = language === 'ru';
  const firstRunCopy = PROGRESS_FIRST_RUN_COPY[language] ?? PROGRESS_FIRST_RUN_COPY.en;

  const formatRefreshDate = (isoValue: string | null) => {
    if (!isoValue) {
      return null;
    }
    const parsedDate = new Date(isoValue);
    if (Number.isNaN(parsedDate.getTime())) {
      return isoValue;
    }
    return new Intl.DateTimeFormat('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(parsedDate);
  };

  const parseStatusLabel = (() => {
    if (!hasConfiguredMapLink) {
      return firstRunCopy.statusMissingMap;
    }
    if (parseRefreshPolicy.reason === 'active_parse') {
      return isRu ? 'Сейчас уже идёт сбор данных. После завершения аудит и показатели обновятся автоматически.' : 'Data collection is already running. The audit and metrics will refresh automatically when it finishes.';
    }
    if (parseStatus === 'error' && parseStatusError) {
      const raw = parseStatusError
        .replace(/^error:\s*/i, '')
        .replace(/^parsed entity mismatch for source url\s*\|?\s*/i, '')
        .trim();
      if (raw) {
        return isRu
          ? `Последний запуск не сохранил данные: ссылка ведёт на другую карточку (${raw}). Исправьте ссылку в «Профиль и бизнес».`
          : `The last run did not save data because the link points to a different listing (${raw}). Fix the map link in Profile & Business.`;
      }
    }
    if (parseRefreshPolicy.reason === 'weekly_cooldown' && parseRefreshPolicy.cooldown_until) {
      const formattedDate = formatRefreshDate(parseRefreshPolicy.cooldown_until);
      if (formattedDate) {
        return isRu
          ? `Обновить данные карточки снова можно ${formattedDate}. Если пригласить друга, обновление станет доступно раньше.`
          : `Card data can be refreshed again on ${formattedDate}. Inviting a friend unlocks it earlier.`;
      }
    }
    switch (parseStatus) {
      case 'processing':
        return isRu ? 'Сейчас собираем данные карточки.' : 'We are collecting card data now.';
      case 'queued':
        return isRu ? 'Задача поставлена в очередь.' : 'The refresh task is queued.';
      case 'completed':
      case 'done':
        return isRu ? 'Последний парсинг завершён, данные обновлены.' : 'The latest parsing run completed and data is up to date.';
      case 'error':
        return isRu ? 'Последний запуск завершился с ошибкой.' : 'The latest run ended with an error.';
      default:
        return isRu ? 'Аудит ниже показывает текущее состояние карточки по последним доступным данным.' : 'The audit below shows the current listing state based on the latest available data.';
    }
  })();

  useEffect(() => {
    const checkNetwork = async () => {
      if (!currentBusinessId) {
        setIsNetworkMaster(false);
        setIsNetworkMember(false);
        setResolvedNetworkId(null);
        setNetworkStatusLoading(false);
        return;
      }

      try {
        setNetworkStatusLoading(true);
        const token = localStorage.getItem('auth_token') || localStorage.getItem('token');
        const response = await fetch(`/api/business/${currentBusinessId}/network-locations`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        });

        if (!response.ok) {
          setIsNetworkMaster(false);
          setIsNetworkMember(false);
          setResolvedNetworkId(null);
          return;
        }

        const data = await response.json();
        setIsNetworkMaster(Boolean(data.is_network_master ?? data.is_network));
        setIsNetworkMember(Boolean(data.is_network_member));
        setResolvedNetworkId(data.network_id || null);
      } catch (error) {
        console.error('Error checking network status:', error);
        setIsNetworkMaster(false);
        setIsNetworkMember(false);
        setResolvedNetworkId(null);
      } finally {
        setNetworkStatusLoading(false);
      }
    };

    checkNetwork();
  }, [currentBusinessId]);

  useEffect(() => {
    const loadMapLinkState = async () => {
      if (!currentBusinessId) {
        setHasConfiguredMapLink(false);
        setIsMapLinkLoading(false);
        return;
      }

      try {
        setIsMapLinkLoading(true);
        const token = localStorage.getItem('auth_token') || localStorage.getItem('token');
        const response = await fetch(`/api/client-info?business_id=${currentBusinessId}`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        });
        const data = await response.json().catch(() => ({}));
        const nextHasMapLink = Array.isArray(data.mapLinks)
          ? data.mapLinks.some((link: { url?: string }) => String(link?.url || '').trim().length > 0)
          : false;
        setHasConfiguredMapLink(nextHasMapLink);
      } catch (error) {
        console.error('Error checking map link state:', error);
        setHasConfiguredMapLink(false);
      } finally {
        setIsMapLinkLoading(false);
      }
    };

    void loadMapLinkState();
  }, [currentBusinessId]);

  useEffect(() => {
    const loadParseStatus = async () => {
      if (!currentBusinessId) {
        setParseStatus('idle');
        return;
      }

      try {
        const token = localStorage.getItem('auth_token') || localStorage.getItem('token');
        const response = await fetch(`/api/business/${currentBusinessId}/parse-status`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        });

        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.success) {
          return;
        }

        setParseStatusError(String(data.error_message || '').trim() || null);
        const nextRefreshPolicy = data.refresh_policy && typeof data.refresh_policy === 'object'
          ? data.refresh_policy
          : {};
        setParseRefreshPolicy({
          can_refresh: Boolean(nextRefreshPolicy.can_refresh ?? true),
          reason: String(nextRefreshPolicy.reason || '').trim() || null,
          message: String(nextRefreshPolicy.message || '').trim() || null,
          cooldown_days: Number(nextRefreshPolicy.cooldown_days || 7),
          last_completed_at: String(nextRefreshPolicy.last_completed_at || '').trim() || null,
          cooldown_until: String(nextRefreshPolicy.cooldown_until || '').trim() || null,
          invite_override_available: Boolean(nextRefreshPolicy.invite_override_available),
          accepted_invites_count: Number(nextRefreshPolicy.accepted_invites_count || 0),
        });

        const nextStatus = String(data.status || 'idle').trim().toLowerCase();
        const normalizedStatus = (
          nextStatus === 'processing' ||
          nextStatus === 'queued' ||
          nextStatus === 'completed' ||
          nextStatus === 'done' ||
          nextStatus === 'error'
        ) ? nextStatus : 'idle';

        setParseStatus((prev) => {
          if ((prev === 'processing' || prev === 'queued') && (normalizedStatus === 'completed' || normalizedStatus === 'done')) {
            setRefreshKey((value) => value + 1);
          }
          return normalizedStatus;
        });
      } catch (error) {
        console.error('Error checking parse status:', error);
      }
    };

    void loadParseStatus();

    if (!currentBusinessId) {
      return undefined;
    }

    const timer = window.setInterval(() => {
      void loadParseStatus();
      setRefreshKey((value) => value + 1);
    }, 10000);

    return () => window.clearInterval(timer);
  }, [currentBusinessId]);

  if (networkStatusLoading && currentBusinessId) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-56 bg-gray-100 animate-pulse rounded-md" />
        <div className="h-40 w-full bg-gray-100 animate-pulse rounded-xl" />
      </div>
    );
  }

  if (isNetworkMaster) {
    return (
      <div className="space-y-6">
        <div className="rounded-xl border bg-white p-4 md:p-6">
          <NetworkDashboardPage embedded businessId={currentBusinessId} />
        </div>

        <div className="rounded-xl border bg-white p-4 md:p-6">
          <h2 className="text-3xl font-bold tracking-tight">
            📊 {t.networkHealth?.title || 'Состояние сети'}
          </h2>
          <p className="mt-2 text-sm text-muted-foreground">
            {t.networkHealth?.subtitle || 'Мониторинг ключевых метрик по всем точкам сети.'}
          </p>
        </div>

        <NetworkHealthDashboard
          networkId={resolvedNetworkId || currentBusinessId}
          businessId={null}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <DashboardPageHeader
        eyebrow={isRu ? 'Контроль состояния' : 'Operations overview'}
        title={t.dashboard?.progress?.title || 'Прогресс'}
        description={t.dashboard?.progress?.subtitle || 'Общая картина бизнеса, текущее состояние карточки и история парсинга.'}
      />

      <DashboardCompactMetricsRow
        items={[
          {
            label: isRu ? 'Ссылка на карту' : 'Map link',
            value: hasConfiguredMapLink ? (isRu ? 'Подключена' : 'Connected') : (isRu ? 'Не подключена' : 'Missing'),
            hint: hasConfiguredMapLink
              ? (isRu ? 'Можно обновлять данные карточки.' : 'Listing data can be refreshed.')
              : (isRu ? 'Сначала нужно сохранить карту в профиле.' : 'Save the map link in the profile first.'),
            tone: hasConfiguredMapLink ? 'positive' : 'warning',
          },
          {
            label: isRu ? 'Статус парсинга' : 'Parsing status',
            value: parseStatusLabel,
            hint: parseRefreshPolicy.message || (isRu ? 'Текущее состояние последнего запуска.' : 'Current state of the latest run.'),
          },
          {
            label: isRu ? 'Сетевой режим' : 'Network mode',
            value: isNetworkMember ? (isRu ? 'Сеть' : 'Network') : (isRu ? 'Одиночный бизнес' : 'Single business'),
            hint: isNetworkMember
              ? (isRu ? 'Показатели собираются по всем точкам сети.' : 'Metrics are aggregated across all network locations.')
              : (isRu ? 'Показатели отображаются по текущему бизнесу.' : 'Metrics are shown for the current business.'),
          },
          {
            label: isRu ? 'Следующее действие' : 'Next action',
            value: hasConfiguredMapLink ? (isRu ? 'Проверить аудит' : 'Review the audit') : (isRu ? 'Добавить карту' : 'Add map link'),
            hint: hasConfiguredMapLink
              ? (isRu ? 'Перейдите в аудит или обновите карточку.' : 'Open the audit or refresh the listing.')
              : (isRu ? 'Без карты аудит и история не заполнятся.' : 'Without a map link, the audit and history remain empty.'),
          },
        ]}
      />

      {!isMapLinkLoading && !hasConfiguredMapLink && (
        <DashboardActionPanel
          tone="amber"
          title={firstRunCopy.preAuditTitle}
          description={firstRunCopy.preAuditBody}
          actions={(
            <Button
              type="button"
              variant="outline"
              onClick={() => navigate('/dashboard/profile')}
              className="border-slate-200 bg-white text-slate-800 hover:bg-slate-100"
              title={isRu ? 'Открывает раздел, где нужно добавить и сохранить ссылку на карту.' : 'Opens the section where you need to add and save the map link.'}
            >
              <ArrowRight className="mr-2 h-4 w-4" />
              {firstRunCopy.goToProfile}
            </Button>
          )}
        />
      )}

      {isNetworkMember && (
        <DashboardSection
          title={isRu ? 'Обзор сети' : 'Network overview'}
          description={isRu ? 'Сводка по всем точкам сети: карта, история показателей и список локаций.' : 'Aggregated network summary: map, metrics history, and location list.'}
          contentClassName="p-4 md:p-6"
        >
          <NetworkDashboardPage embedded businessId={currentBusinessId} />
        </DashboardSection>
      )}

      <DashboardActionPanel
        tone="indigo"
        title={firstRunCopy.whereAuditTitle}
        description={isRu ? (
          <>
            {!hasConfiguredMapLink
              ? firstRunCopy.whereAuditNoMapBody
              : <>Ниже показан аудит карточки и техническая история сборов. Если нужны свежие данные, перейдите в <span className="font-semibold">«Работа с картами»</span> и запустите обновление карточки.</>}
          </>
        ) : (
          <>
            {!hasConfiguredMapLink
              ? firstRunCopy.whereAuditNoMapBody
              : <>Below you can see the current card audit and parsing history. If you need fresh listing data, go to <span className="font-semibold">Maps Management</span> and run a listing refresh.</>}
          </>
        )}
        status={<span className="font-semibold">{parseStatusLabel}</span>}
        actions={(
          <Button
            type="button"
            variant="outline"
            onClick={() => navigate(hasConfiguredMapLink ? '/dashboard/card' : '/dashboard/profile')}
            className="border-slate-200 bg-white text-slate-800 hover:bg-slate-100"
            title={hasConfiguredMapLink
              ? (isRu ? 'Открывает раздел работы с картами, где можно обновить данные карточки и запустить новый сбор.' : 'Opens maps management where you can refresh listing data and start a new collection.')
              : (isRu ? 'Открывает профиль бизнеса, где нужно сначала сохранить ссылку на карту.' : 'Opens the business profile where you need to save the map link first.')}
          >
            <RefreshCw className="mr-2 h-4 w-4" />
            {hasConfiguredMapLink
              ? (isRu ? 'Перейти в «Работа с картами»' : 'Go to Maps Management')
              : firstRunCopy.goToProfile}
          </Button>
        )}
      />

      <BusinessHealthWidget businessId={currentBusinessId} className="mb-0" />

      <CardAuditPanel businessId={currentBusinessId} refreshKey={refreshKey} />

      <MapParseTable businessId={currentBusinessId} refreshKey={refreshKey} />
    </div>
  );
};
