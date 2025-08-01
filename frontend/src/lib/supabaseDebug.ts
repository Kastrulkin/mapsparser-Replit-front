import { supabase } from './supabase';

export class SupabaseDebug {
  static async checkAuthStatus() {
    try {
      const { data: { user }, error } = await supabase.auth.getUser();
      console.log('Current user:', user);
      console.log('Auth error:', error);
      return { user, error };
    } catch (error) {
      console.error('Auth check error:', error);
      return { user: null, error };
    }
  }

  static async testSignUp(email: string, password: string) {
    console.log('Testing signup with:', { email, password: password.substring(0, 3) + '...' });
    
    try {
      const { data, error } = await supabase.auth.signUp({
        email,
        password,
        options: {
          emailRedirectTo: 'https://beautybot.pro/set-password'
        }
      });

      console.log('Signup result:', { 
        success: !error, 
        userId: data?.user?.id,
        emailConfirmed: data?.user?.email_confirmed_at,
        error: error?.message,
        errorCode: error?.status
      });

      return { data, error };
    } catch (error) {
      console.error('Signup test error:', error);
      return { data: null, error };
    }
  }

  static async checkEmailSettings() {
    // Проверяем настройки email в Supabase
    console.log('Supabase URL:', import.meta.env.VITE_SUPABASE_URL);
    console.log('Supabase Key type:', import.meta.env.VITE_SUPABASE_KEY?.substring(0, 10) + '...');
    
    // Проверяем, есть ли пользователи в базе
    try {
      const { data, error } = await supabase
        .from('Users')
        .select('count')
        .limit(1);
      
      console.log('Database connection test:', { success: !error, error: error?.message });
    } catch (error) {
      console.error('Database test error:', error);
    }
  }

  static async getRateLimitInfo() {
    // Получаем информацию о текущих лимитах
    const info = {
      timestamp: new Date().toISOString(),
      userAgent: navigator.userAgent,
      url: window.location.href,
      supabaseUrl: import.meta.env.VITE_SUPABASE_URL
    };
    
    console.log('Rate limit info:', info);
    return info;
  }
} 