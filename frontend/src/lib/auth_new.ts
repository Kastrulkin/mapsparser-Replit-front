export interface User {
  id: string;
  email: string;
  name?: string;
  phone?: string;
  is_superadmin?: boolean;
  businesses?: any[];
  session_kind?: 'standard' | 'demo';
  demo_mode?: boolean;
  demo_scope_business_id?: string | null;
  demo_room_slug?: string;
}

export interface AuthResponse {
  id: string;
  email: string;
  name?: string;
  phone?: string;
  token?: string;
  error?: string;
}

import { API_URL } from '../config/api';

export class NewAuth {
  private static instance: NewAuth;
  private currentUser: User | null = null;
  private token: string | null = null;
  private apiBaseUrl = `${API_URL}/api`;
  private readonly standardTokenKey = 'auth_token';
  private readonly demoTokenKey = 'demo_auth_token';
  private readonly demoModeKey = 'localos_demo_mode';

  static getInstance(): NewAuth {
    if (!NewAuth.instance) {
      NewAuth.instance = new NewAuth();
    }
    return NewAuth.instance;
  }

  constructor() {
    this.token = this.getStoredActiveToken();
    if (this.token) {
      this.getCurrentUser();
    }
  }

  private getStoredActiveToken(): string | null {
    if (this.isDemoModeActive()) {
      return localStorage.getItem(this.demoTokenKey);
    }
    return localStorage.getItem(this.standardTokenKey);
  }

  private clearActiveToken(): void {
    if (this.isDemoModeActive()) {
      localStorage.removeItem(this.demoTokenKey);
      sessionStorage.removeItem(this.demoModeKey);
    } else {
      localStorage.removeItem(this.standardTokenKey);
    }
    this.token = null;
    this.currentUser = null;
  }

  public isDemoModeActive(): boolean {
    return typeof window !== 'undefined' && sessionStorage.getItem(this.demoModeKey) === '1';
  }

  public activateDemoSession(token?: string): void {
    if (token) {
      localStorage.setItem(this.demoTokenKey, token);
    }
    sessionStorage.setItem(this.demoModeKey, '1');
    this.token = token || localStorage.getItem(this.demoTokenKey);
    this.currentUser = null;
  }

  public deactivateDemoSession(clearToken = false): void {
    sessionStorage.removeItem(this.demoModeKey);
    if (clearToken) {
      localStorage.removeItem(this.demoTokenKey);
    }
    this.token = localStorage.getItem(this.standardTokenKey);
    this.currentUser = null;
  }

  public async makeRequest(endpoint: string, options: RequestInit = {}): Promise<any> {
    const url = `${this.apiBaseUrl}${endpoint}`;
    let responseReceived = false;
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    const liveToken = this.getStoredActiveToken();
    if (liveToken !== this.token) {
      this.token = liveToken;
    }

    const isPublicSalesRoomRequest = endpoint.startsWith('/sales-rooms/public/');
    if (this.token && !(this.isDemoModeActive() && isPublicSalesRoomRequest)) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    try {
      const response = await fetch(url, {
        ...options,
        headers,
      });
      responseReceived = true;

      // Проверяем Content-Type перед парсингом JSON
      const contentType = response.headers.get('content-type');
      const isJson = contentType && contentType.includes('application/json');

      let data: any = {};

      if (isJson) {
        const text = await response.text();
        if (text.trim()) {
          try {
            data = JSON.parse(text);
          } catch (parseError) {
            console.error('Ошибка парсинга JSON:', parseError, 'Ответ:', text);
            throw new Error(`Ошибка парсинга ответа сервера: ${text.substring(0, 100)}`);
          }
        }
      } else {
        // Если ответ не JSON, читаем как текст
        const text = await response.text();
        console.error('Сервер вернул не-JSON ответ:', text.substring(0, 200));
        throw new Error(`Сервер вернул неверный формат ответа (${response.status}): ${text.substring(0, 100)}`);
      }

      if (!response.ok) {
        const backendError = String(data.error || '');
        if (response.status === 401 && backendError.toLowerCase().includes('invalid token')) {
          this.clearActiveToken();
          throw new Error('Сессия истекла. Войдите снова.');
        }
        throw new Error(data.message || data.error || `Ошибка запроса (${response.status})`);
      }

      return data;
    } catch (error) {
      // Если сервер ответил, показываем его прикладную ошибку без маскировки под сетевой сбой.
      if (responseReceived || (error instanceof Error && error.message.includes('Ошибка'))) {
        throw error;
      }
      // Иначе это сетевая ошибка или другая проблема
      console.error('Ошибка запроса:', error);
      throw new Error(`Ошибка соединения с сервером: ${error instanceof Error ? error.message : 'Неизвестная ошибка'}`);
    }
  }

  async signUp(email: string, password: string, name?: string, phone?: string, yandexUrl?: string, personalDataConsent?: boolean): Promise<{ user: User | null; error: any }> {
    this.deactivateDemoSession();
    try {
      const response = await this.makeRequest('/auth/register', {
        method: 'POST',
        body: JSON.stringify({
          email,
          password,
          name,
          phone,
          yandexUrl,
          personal_data_consent: Boolean(personalDataConsent),
          consent_version: 'localos-personal-data-v1-2026-05-11',
        }),
      });

      if (response.error) {
        return { user: null, error: response.error };
      }

      const u = response.user || response;
      this.currentUser = {
        id: u.id,
        email: u.email,
        name: u.name,
        phone: u.phone,
      };

      if (response.token) {
        this.token = response.token;
        localStorage.setItem(this.standardTokenKey, this.token);
      }

      return { user: this.currentUser, error: null };
    } catch (error) {
      return { user: null, error: error.message };
    }
  }

  async signUpWithBusiness(
    email: string,
    password: string,
    name?: string,
    phone?: string,
    business_name?: string,
    business_address?: string,
    business_city?: string,
    business_country?: string,
    personalDataConsent?: boolean
  ): Promise<{ user: User | null; business: any | null; error: any }> {
    this.deactivateDemoSession();
    try {
      const response = await this.makeRequest('/auth/register-with-business', {
        method: 'POST',
        body: JSON.stringify({
          email,
          password,
          name,
          phone,
          business_name,
          business_address,
          business_city,
          business_country,
          personal_data_consent: Boolean(personalDataConsent),
          consent_version: 'localos-personal-data-v1-2026-05-11',
        }),
      });

      if (response.error) {
        return { user: null, business: null, error: response.error };
      }

      const u = response.user || response;
      this.currentUser = {
        id: u.id,
        email: u.email,
        name: u.name,
        phone: u.phone,
      };

      if (response.token) {
        this.token = response.token;
        localStorage.setItem(this.standardTokenKey, this.token);
      }

      return {
        user: this.currentUser,
        business: response.business || null,
        error: null
      };
    } catch (error) {
      return { user: null, business: null, error: error.message };
    }
  }

  async signIn(email: string, password: string): Promise<{ user: User | null; error: any }> {
    this.deactivateDemoSession();
    try {
      const response = await this.makeRequest('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      });

      if (response.error) {
        return { user: null, error: response.error };
      }

      const u2 = response.user || response;
      this.currentUser = {
        id: u2.id,
        email: u2.email,
        name: u2.name,
        phone: u2.phone,
      };

      if (response.token) {
        this.token = response.token;
        localStorage.setItem(this.standardTokenKey, this.token);
      }

      return { user: this.currentUser, error: null };
    } catch (error) {
      return { user: null, error: error.message };
    }
  }

  async signOut(): Promise<void> {
    const signingOutDemo = this.isDemoModeActive();
    try {
      if (this.token) {
        await this.makeRequest('/auth/logout', {
          method: 'POST',
        });
      }
    } catch (error) {
      console.error('Ошибка при выходе:', error);
    } finally {
      if (signingOutDemo) {
        this.deactivateDemoSession(true);
      } else {
        this.currentUser = null;
        this.token = null;
        localStorage.removeItem(this.standardTokenKey);
      }
    }
  }

  async getCurrentUser(): Promise<User | null> {
    this.token = this.getStoredActiveToken();
    if (!this.token) {
      return null;
    }

    try {
      const response = await this.makeRequest('/auth/me');
      const u = response.user || response;
      this.currentUser = {
        id: u.id,
        email: u.email,
        name: u.name,
        phone: u.phone,
        is_superadmin: u.is_superadmin,
        businesses: response.businesses || [],
        session_kind: u.session_kind || 'standard',
        demo_mode: Boolean(u.demo_mode),
        demo_scope_business_id: u.demo_scope_business_id || null,
        demo_room_slug: u.demo_room_slug || '',
      };

      return this.currentUser;
    } catch (error) {
      console.error('Ошибка при получении пользователя:', error);
      this.clearActiveToken();
      return null;
    }
  }

  getCurrentUserSync(): User | null {
    return this.currentUser;
  }

  async updateProfile(updates: Partial<User>): Promise<{ user: User | null; error: any }> {
    if (!this.currentUser) {
      return { user: null, error: 'Пользователь не авторизован' };
    }

    try {
      const response = await this.makeRequest('/users/profile', {
        method: 'PUT',
        body: JSON.stringify(updates),
      });

      if (response.error) {
        return { user: null, error: response.error };
      }

      // Обновляем локальные данные
      this.currentUser = { ...this.currentUser, ...updates };
      return { user: this.currentUser, error: null };
    } catch (error) {
      return { user: null, error: error.message };
    }
  }

  async changePassword(oldPassword: string, newPassword: string): Promise<{ success: boolean; error: any }> {
    try {
      const response = await this.makeRequest('/users/change-password', {
        method: 'POST',
        body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
      });

      if (response.error) {
        return { success: false, error: response.error };
      }

      return { success: true, error: null };
    } catch (error) {
      return { success: false, error: error.message };
    }
  }

  async getUserReports(): Promise<{ reports: any[]; error: any }> {
    try {
      const response = await this.makeRequest('/users/reports');
      return { reports: response.reports, error: null };
    } catch (error) {
      return { reports: [], error: error.message };
    }
  }

  async getUserQueue(): Promise<{ queue: any[]; error: any }> {
    try {
      const response = await this.makeRequest('/users/queue');
      return { queue: response.queue, error: null };
    } catch (error) {
      return { queue: [], error: error.message };
    }
  }

  async addToQueue(url: string): Promise<{ queue_id: string; error: any }> {
    try {
      const response = await this.makeRequest('/users/add-to-queue', {
        method: 'POST',
        body: JSON.stringify({ url }),
      });

      if (response.error) {
        return { queue_id: '', error: response.error };
      }

      return { queue_id: response.queue_id, error: null };
    } catch (error) {
      return { queue_id: '', error: error.message };
    }
  }

  async createInvite(email: string): Promise<{ invite: any; error: any }> {
    try {
      const response = await this.makeRequest('/users/invite', {
        method: 'POST',
        body: JSON.stringify({ email }),
      });

      if (response.error) {
        return { invite: null, error: response.error };
      }

      return { invite: response, error: null };
    } catch (error) {
      return { invite: null, error: error.message };
    }
  }

  async verifyInvite(token: string): Promise<{ email: string; error: any }> {
    try {
      const response = await this.makeRequest(`/auth/verify-invite/${token}`);
      return { email: response.email, error: null };
    } catch (error) {
      return { email: '', error: error.message };
    }
  }

  async acceptInvite(token: string, password: string, name?: string): Promise<{ user: User | null; error: any }> {
    try {
      const response = await this.makeRequest('/auth/accept-invite', {
        method: 'POST',
        body: JSON.stringify({ token, password, name }),
      });

      if (response.error) {
        return { user: null, error: response.error };
      }

      this.currentUser = {
        id: response.id,
        email: response.email,
        name: response.name,
        phone: response.phone,
      };

      if (response.token) {
        this.token = response.token;
        localStorage.setItem(this.standardTokenKey, this.token);
      }

      return { user: this.currentUser, error: null };
    } catch (error) {
      return { user: null, error: error.message };
    }
  }

  async setPassword(
    email: string,
    password: string,
    token?: string,
    personalDataConsent?: boolean,
    consentVersion?: string
  ): Promise<{ user: User | null; error: any }> {
    try {
      const response = await this.makeRequest('/auth/set-password', {
        method: 'POST',
        body: JSON.stringify({
          email,
          password,
          token,
          personal_data_consent: Boolean(personalDataConsent),
          consent_version: consentVersion,
        }),
      });

      if (response.error) {
        return { user: null, error: response.error };
      }

      this.currentUser = {
        id: response.id,
        email: response.email,
        name: response.name,
        phone: response.phone,
      };

      if (response.token) {
        this.token = response.token;
        localStorage.setItem(this.standardTokenKey, this.token);
      }

      return { user: this.currentUser, error: null };
    } catch (error) {
      return { user: null, error: error.message };
    }
  }

  isAuthenticated(): boolean {
    return !!this.token && !!this.currentUser;
  }

  getToken(): string | null {
    this.token = this.getStoredActiveToken();
    return this.token;
  }
}

export const newAuth = NewAuth.getInstance();
