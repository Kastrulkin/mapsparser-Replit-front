import { supabase } from './supabase';

export interface User {
  id: string;
  email: string;
  name?: string;
  phone?: string;
  yandex_url?: string;
}

export class SimpleAuth {
  private static instance: SimpleAuth;
  private currentUser: User | null = null;

  static getInstance(): SimpleAuth {
    if (!SimpleAuth.instance) {
      SimpleAuth.instance = new SimpleAuth();
    }
    return SimpleAuth.instance;
  }

  async signUp(email: string, password: string): Promise<{ user: User | null; error: any }> {
    try {
      // Создаем пользователя в таблице Users
      const { data, error } = await supabase
        .from('Users')
        .insert({ email })
        .select('*')
        .single();

      if (error) {
        return { user: null, error };
      }

      // Сохраняем пароль локально (в реальном приложении нужно хешировать)
      localStorage.setItem(`user_${data.id}_password`, password);
      
      this.currentUser = data;
      return { user: data, error: null };
    } catch (error) {
      return { user: null, error };
    }
  }

  async signIn(email: string, password: string): Promise<{ user: User | null; error: any }> {
    try {
      // Ищем пользователя по email
      const { data, error } = await supabase
        .from('Users')
        .select('*')
        .eq('email', email)
        .single();

      if (error || !data) {
        return { user: null, error: 'Пользователь не найден' };
      }

      // Проверяем пароль (в реальном приложении нужно хешировать)
      const storedPassword = localStorage.getItem(`user_${data.id}_password`);
      if (password !== storedPassword) {
        return { user: null, error: 'Неверный пароль' };
      }

      this.currentUser = data;
      return { user: data, error: null };
    } catch (error) {
      return { user: null, error };
    }
  }

  async signOut(): Promise<void> {
    this.currentUser = null;
    localStorage.removeItem('currentUser');
  }

  getCurrentUser(): User | null {
    return this.currentUser;
  }

  async updateProfile(updates: Partial<User>): Promise<{ user: User | null; error: any }> {
    if (!this.currentUser) {
      return { user: null, error: 'Пользователь не авторизован' };
    }

    try {
      const { data, error } = await supabase
        .from('Users')
        .update(updates)
        .eq('id', this.currentUser.id)
        .select('*')
        .single();

      if (error) {
        return { user: null, error };
      }

      this.currentUser = data;
      return { user: data, error: null };
    } catch (error) {
      return { user: null, error };
    }
  }

  async findUserByEmail(email: string): Promise<{ data: User | null; error: any }> {
    try {
      const { data, error } = await supabase
        .from('Users')
        .select('*')
        .eq('email', email)
        .single();

      return { data, error };
    } catch (error) {
      return { data: null, error };
    }
  }
}

export const auth = SimpleAuth.getInstance(); 