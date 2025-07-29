import { supabase } from './supabase';

export interface AuthTestResult {
  success: boolean;
  data?: any;
  error?: any;
  timestamp: string;
  testName: string;
}

export class AuthTester {
  private static generateTestEmail(): string {
    const timestamp = Date.now();
    const random = Math.random().toString(36).substring(7);
    return `test-${timestamp}-${random}@example.com`;
  }

  // Тест регистрации с уникальным email
  static async testSignUp(): Promise<AuthTestResult> {
    const testEmail = this.generateTestEmail();
    const testPassword = 'TestPassword123!';

    try {
      console.log('🧪 Testing SignUp with:', testEmail);
      
      const { data, error } = await supabase.auth.signUp({
        email: testEmail,
        password: testPassword,
        options: {
          emailRedirectTo: window.location.origin + '/set-password'
        }
      });

      const result: AuthTestResult = {
        success: !error,
        data: data,
        error: error,
        timestamp: new Date().toISOString(),
        testName: 'SignUp Test'
      };

      console.log('✅ SignUp Test Result:', result);
      return result;
    } catch (error) {
      const result: AuthTestResult = {
        success: false,
        error: error,
        timestamp: new Date().toISOString(),
        testName: 'SignUp Test'
      };
      console.error('❌ SignUp Test Error:', result);
      return result;
    }
  }

  // Тест входа с существующим пользователем
  static async testSignIn(email: string, password: string): Promise<AuthTestResult> {
    try {
      console.log('🧪 Testing SignIn with:', email);
      
      const { data, error } = await supabase.auth.signInWithPassword({
        email,
        password
      });

      const result: AuthTestResult = {
        success: !error,
        data: data,
        error: error,
        timestamp: new Date().toISOString(),
        testName: 'SignIn Test'
      };

      console.log('✅ SignIn Test Result:', result);
      return result;
    } catch (error) {
      const result: AuthTestResult = {
        success: false,
        error: error,
        timestamp: new Date().toISOString(),
        testName: 'SignIn Test'
      };
      console.error('❌ SignIn Test Error:', result);
      return result;
    }
  }

  // Тест сброса пароля
  static async testPasswordReset(email: string): Promise<AuthTestResult> {
    try {
      console.log('🧪 Testing Password Reset for:', email);
      
      const { error } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo: window.location.origin + '/set-password'
      });

      const result: AuthTestResult = {
        success: !error,
        error: error,
        timestamp: new Date().toISOString(),
        testName: 'Password Reset Test'
      };

      console.log('✅ Password Reset Test Result:', result);
      return result;
    } catch (error) {
      const result: AuthTestResult = {
        success: false,
        error: error,
        timestamp: new Date().toISOString(),
        testName: 'Password Reset Test'
      };
      console.error('❌ Password Reset Test Error:', result);
      return result;
    }
  }

  // Тест получения текущего пользователя
  static async testGetUser(): Promise<AuthTestResult> {
    try {
      console.log('🧪 Testing Get User');
      
      const { data: { user }, error } = await supabase.auth.getUser();

      const result: AuthTestResult = {
        success: !error,
        data: { user },
        error: error,
        timestamp: new Date().toISOString(),
        testName: 'Get User Test'
      };

      console.log('✅ Get User Test Result:', result);
      return result;
    } catch (error) {
      const result: AuthTestResult = {
        success: false,
        error: error,
        timestamp: new Date().toISOString(),
        testName: 'Get User Test'
      };
      console.error('❌ Get User Test Error:', result);
      return result;
    }
  }

  // Тест rate limit с экспоненциальной задержкой
  static async testRateLimit(maxRetries: number = 3): Promise<AuthTestResult[]> {
    const results: AuthTestResult[] = [];
    
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      console.log(`🧪 Testing Rate Limit - Attempt ${attempt}/${maxRetries}`);
      
      const result = await this.testSignUp();
      results.push(result);
      
      if (result.success) {
        console.log('✅ Rate limit test passed on attempt:', attempt);
        break;
      }
      
      if (result.error?.message?.includes('rate limit')) {
        const delay = Math.pow(2, attempt) * 1000; // Экспоненциальная задержка
        console.log(`⏳ Rate limit hit, waiting ${delay}ms before retry...`);
        await new Promise(resolve => setTimeout(resolve, delay));
      } else {
        console.log('❌ Non-rate-limit error, stopping retries');
        break;
      }
    }
    
    return results;
  }

  // Комплексный тест всех аутентификационных потоков
  static async runFullAuthTest(): Promise<{
    signUp: AuthTestResult;
    signIn?: AuthTestResult;
    passwordReset?: AuthTestResult;
    getUser: AuthTestResult;
    rateLimit: AuthTestResult[];
  }> {
    console.log('🚀 Starting Full Authentication Test Suite');
    
    const results = {
      signUp: await this.testSignUp(),
      getUser: await this.testGetUser(),
      rateLimit: await this.testRateLimit(2)
    };

    // Если регистрация прошла успешно, тестируем вход
    if (results.signUp.success && results.signUp.data?.user) {
      const testPassword = 'TestPassword123!';
      results.signIn = await this.testSignIn(
        results.signUp.data.user.email,
        testPassword
      );
    }

    // Тестируем сброс пароля для существующего email
    const existingEmail = 'demyanovp@yandex.ru'; // Ваш email для тестирования
    results.passwordReset = await this.testPasswordReset(existingEmail);

    console.log('📊 Full Auth Test Results:', results);
    return results;
  }

  // Проверка настроек Supabase
  static async checkSupabaseConfig(): Promise<AuthTestResult> {
    try {
      console.log('🧪 Checking Supabase Configuration');
      
      const config = {
        url: import.meta.env.VITE_SUPABASE_URL,
        keyType: import.meta.env.VITE_SUPABASE_KEY?.substring(0, 10) + '...',
        hasUrl: !!import.meta.env.VITE_SUPABASE_URL,
        hasKey: !!import.meta.env.VITE_SUPABASE_KEY
      };

      const result: AuthTestResult = {
        success: config.hasUrl && config.hasKey,
        data: config,
        timestamp: new Date().toISOString(),
        testName: 'Supabase Config Test'
      };

      console.log('✅ Supabase Config Test Result:', result);
      return result;
    } catch (error) {
      const result: AuthTestResult = {
        success: false,
        error: error,
        timestamp: new Date().toISOString(),
        testName: 'Supabase Config Test'
      };
      console.error('❌ Supabase Config Test Error:', result);
      return result;
    }
  }
} 