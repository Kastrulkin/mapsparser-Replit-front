export interface User {
  id: string;
  email: string;
  name?: string;
  phone?: string;
  is_superadmin?: boolean;
  businesses?: any[];
}

export interface AuthResponse {
  id: string;
  email: string;
  name?: string;
  phone?: string;
  token?: string;
  error?: string;
}

export class NewAuth {
  private static instance: NewAuth;
  private currentUser: User | null = null;
  private token: string | null = null;
  private apiBaseUrl = `${window.location.origin}/api`;

  static getInstance(): NewAuth {
    if (!NewAuth.instance) {
      NewAuth.instance = new NewAuth();
    }
    return NewAuth.instance;
  }

  constructor() {
    // Загружаем токен из localStorage при инициализации
    this.token = localStorage.getItem('auth_token');
    if (this.token) {
      this.getCurrentUser();
    }
  }

  private async makeRequest(endpoint: string, options: RequestInit = {}): Promise<any> {
    const url = `${this.apiBaseUrl}${endpoint}`;
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    try {
      const response = await fetch(url, {
        ...options,
        headers,
      });

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
        throw new Error(data.error || `Ошибка запроса (${response.status})`);
      }

      return data;
    } catch (error) {
      // Если это уже наша ошибка, пробрасываем дальше
      if (error instanceof Error && error.message.includes('Ошибка')) {
        throw error;
      }
      // Иначе это сетевая ошибка или другая проблема
      console.error('Ошибка запроса:', error);
      throw new Error(`Ошибка соединения с сервером: ${error instanceof Error ? error.message : 'Неизвестная ошибка'}`);
    }
  }

  async signUp(email: string, password: string, name?: string, phone?: string, yandexUrl?: string): Promise<{ user: User | null; error: any }> {
    try {
      const response = await this.makeRequest('/auth/register', {
        method: 'POST',
        body: JSON.stringify({ email, password, name, phone, yandexUrl }),
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
        localStorage.setItem('auth_token', this.token);
      }

      return { user: this.currentUser, error: null };
    } catch (error) {
      return { user: null, error: error.message };
    }
  }

  async signIn(email: string, password: string): Promise<{ user: User | null; error: any }> {
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
        localStorage.setItem('auth_token', this.token);
      }

      return { user: this.currentUser, error: null };
    } catch (error) {
      return { user: null, error: error.message };
    }
  }

  async signOut(): Promise<void> {
    try {
      if (this.token) {
        await this.makeRequest('/auth/logout', {
          method: 'POST',
        });
      }
    } catch (error) {
      console.error('Ошибка при выходе:', error);
    } finally {
      this.currentUser = null;
      this.token = null;
      localStorage.removeItem('auth_token');
    }
  }

  async getCurrentUser(): Promise<User | null> {
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
      };

      return this.currentUser;
    } catch (error) {
      console.error('Ошибка при получении пользователя:', error);
      this.token = null;
      localStorage.removeItem('auth_token');
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
        localStorage.setItem('auth_token', this.token);
      }

      return { user: this.currentUser, error: null };
    } catch (error) {
      return { user: null, error: error.message };
    }
  }

  async setPassword(email: string, password: string): Promise<{ user: User | null; error: any }> {
    try {
      const response = await this.makeRequest('/auth/set-password', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
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
        localStorage.setItem('auth_token', this.token);
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
    return this.token;
  }
}

export const newAuth = NewAuth.getInstance();
