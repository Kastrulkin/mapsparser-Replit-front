import { newAuth, type User } from "@/lib/auth_new";
import type {
  DashboardBusiness,
  DashboardClientInfo,
  DashboardService,
} from "@/components/dashboard/DashboardSections";

export type DashboardNetwork = {
  id: string;
  name?: string;
};

type DashboardServicesResponse = {
  success?: boolean;
  services?: DashboardService[];
  error?: string;
};

type DashboardNetworksResponse = {
  success?: boolean;
  networks?: DashboardNetwork[];
};

type DashboardBusinessDataResponse = {
  business?: DashboardBusiness;
  services?: DashboardService[];
  business_profile?: {
    contact_name?: string;
    contact_phone?: string;
    contact_email?: string;
  };
};

type DashboardAuthMeResponse = {
  businesses?: DashboardBusiness[];
};

type DashboardClientInfoResponse = DashboardClientInfo;

type DashboardNewService = {
  category: string;
  name: string;
  description: string;
  keywords: string;
  price: string;
};

export type DashboardBootstrapData = {
  businesses: DashboardBusiness[];
  currentBusiness: DashboardBusiness | null;
  currentBusinessId: string | null;
  userServices: DashboardService[];
  networks: DashboardNetwork[];
  currentNetworkId: string | null;
  clientInfo: DashboardClientInfo | null;
};

const isServicesResponse = (value: unknown): value is DashboardServicesResponse =>
  typeof value === 'object' && value !== null;

const isNetworksResponse = (value: unknown): value is DashboardNetworksResponse =>
  typeof value === 'object' && value !== null;

const isBusinessDataResponse = (value: unknown): value is DashboardBusinessDataResponse =>
  typeof value === 'object' && value !== null;

const isDashboardAuthMeResponse = (value: unknown): value is DashboardAuthMeResponse =>
  typeof value === 'object' && value !== null;

const isDashboardClientInfoResponse = (value: unknown): value is DashboardClientInfoResponse =>
  typeof value === 'object' && value !== null;

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
  };
};

export async function fetchDashboardNetworks(): Promise<DashboardNetwork[]> {
  const response = await fetch(`${window.location.origin}/api/networks`, {
    headers: {
      'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
    },
  });
  const payload: unknown = await response.json();
  if (!isNetworksResponse(payload) || !payload.success) {
    return [];
  }
  return payload.networks || [];
}

export async function fetchDashboardServices(): Promise<DashboardService[]> {
  const response = await fetch(`${window.location.origin}/api/services/list`, {
    headers: {
      'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
    },
  });
  const payload: unknown = await response.json();
  if (!isServicesResponse(payload) || !payload.success) {
    return [];
  }
  return payload.services || [];
}

export async function fetchDashboardBusinesses(): Promise<DashboardBusiness[]> {
  const response = await fetch('/api/auth/me', {
    headers: {
      'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
    },
  });

  if (!response.ok) {
    return [];
  }

  const payload: unknown = await response.json();
  if (!isDashboardAuthMeResponse(payload) || !Array.isArray(payload.businesses)) {
    return [];
  }

  return payload.businesses;
}

export async function fetchDashboardClientInfo(): Promise<DashboardClientInfo | null> {
  const response = await fetch(`${window.location.origin}/api/client-info`, {
    headers: {
      'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
    },
  });

  if (!response.ok) {
    return null;
  }

  const payload: unknown = await response.json();
  if (!isDashboardClientInfoResponse(payload)) {
    return null;
  }

  return payload;
}

export async function fetchDashboardBootstrap(user: User): Promise<DashboardBootstrapData> {
  const [userServices, networks, businesses, clientInfo] = await Promise.all([
    fetchDashboardServices(),
    fetchDashboardNetworks(),
    user.is_superadmin ? fetchDashboardBusinesses() : Promise.resolve([]),
    fetchDashboardClientInfo(),
  ]);

  const savedBusinessId = localStorage.getItem('selectedBusinessId');
  const currentBusiness = businesses.length > 0
    ? savedBusinessId
      ? businesses.find((business) => business.id === savedBusinessId) || businesses[0]
      : businesses[0]
    : null;

  return {
    businesses,
    currentBusiness,
    currentBusinessId: currentBusiness?.id || null,
    userServices,
    networks,
    currentNetworkId: networks.length > 0 ? networks[0].id : null,
    clientInfo,
  };
}

export async function fetchDashboardBusinessData(businessId: string): Promise<DashboardBusinessDataResponse | null> {
  const token = newAuth.getToken();
  if (!token) {
    return null;
  }

  const response = await fetch(`/api/business/${businessId}/data`, {
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    return null;
  }

  const payload: unknown = await response.json();
  if (!isBusinessDataResponse(payload)) {
    return null;
  }
  return payload;
}

export async function addDashboardService(
  currentBusinessId: string | null,
  newService: DashboardNewService,
): Promise<{ success: boolean; error?: string }> {
  const response = await fetch(`${window.location.origin}/api/services/add`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({
      category: newService.category || 'Общие услуги',
      name: newService.name,
      description: newService.description,
      keywords: newService.keywords.split(',').map((keyword) => keyword.trim()).filter(Boolean),
      price: newService.price,
      business_id: currentBusinessId,
    }),
  });

  const payload: unknown = await response.json();
  if (typeof payload === 'object' && payload !== null && 'success' in payload && payload.success) {
    return { success: true };
  }

  if (typeof payload === 'object' && payload !== null && 'error' in payload) {
    return { success: false, error: String(payload.error || 'Ошибка добавления услуги') };
  }

  return { success: false, error: 'Ошибка добавления услуги' };
}

export async function deleteDashboardService(serviceId: string): Promise<{ success: boolean; error?: string }> {
  const response = await fetch(`${window.location.origin}/api/services/delete/${serviceId}`, {
    method: 'DELETE',
    headers: { 'Authorization': `Bearer ${localStorage.getItem('auth_token')}` },
  });

  const payload: unknown = await response.json();
  if (typeof payload === 'object' && payload !== null && 'success' in payload && payload.success) {
    return { success: true };
  }

  if (typeof payload === 'object' && payload !== null && 'error' in payload) {
    return { success: false, error: String(payload.error || 'Ошибка удаления услуги') };
  }

  return { success: false, error: 'Ошибка удаления услуги' };
}

export async function saveDashboardBusinessProfile(
  businessId: string,
  form: { name: string; phone: string; email: string },
): Promise<{ success: boolean; error?: string }> {
  const response = await fetch(`${window.location.origin}/api/business/${businessId}/profile`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({
      contact_name: form.name,
      contact_phone: form.phone,
      contact_email: form.email,
    }),
  });

  if (response.ok) {
    return { success: true };
  }

  const payload: unknown = await response.json();
  if (typeof payload === 'object' && payload !== null && 'error' in payload) {
    return { success: false, error: String(payload.error || 'Ошибка обновления профиля бизнеса') };
  }
  return { success: false, error: 'Ошибка обновления профиля бизнеса' };
}

export async function saveDashboardClientInfo(
  currentBusinessId: string | null,
  clientInfo: DashboardClientInfo,
): Promise<{ success: boolean; error?: string }> {
  const response = await fetch(`${window.location.origin}/api/client-info`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({
      ...clientInfo,
      businessId: currentBusinessId,
    }),
  });

  if (response.ok) {
    return { success: true };
  }

  const payload: unknown = await response.json();
  if (typeof payload === 'object' && payload !== null && 'error' in payload) {
    return { success: false, error: String(payload.error || 'Ошибка сохранения информации') };
  }
  return { success: false, error: 'Ошибка сохранения информации' };
}

export function buildDashboardProfileForm(
  user: User | null,
  profile?: DashboardBusinessDataResponse['business_profile'],
) {
  return {
    email: profile?.contact_email || user?.email || "",
    phone: profile?.contact_phone || user?.phone || "",
    name: profile?.contact_name || user?.name || "",
    yandexUrl: "",
  };
}

export function buildDashboardClientInfo(business?: DashboardBusiness | null): DashboardClientInfo {
  return {
    businessName: business?.name || "",
    businessType: business?.business_type || "other",
    address: business?.address || "",
    workingHours: business?.working_hours || "",
    mapLinks: [],
  };
}
