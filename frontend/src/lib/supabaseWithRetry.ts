import { supabase } from './supabase';

interface RetryOptions {
  maxRetries?: number;
  baseDelay?: number;
  maxDelay?: number;
}

export class SupabaseWithRetry {
  private static async delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  private static calculateDelay(attempt: number, baseDelay: number, maxDelay: number): number {
    const delay = baseDelay * Math.pow(2, attempt);
    return Math.min(delay, maxDelay);
  }

  static async signUp(email: string, password: string, options?: any, retryOptions?: RetryOptions) {
    const { maxRetries = 3, baseDelay = 1000, maxDelay = 10000 } = retryOptions || {};

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        const result = await supabase.auth.signUp({
          email,
          password,
          options
        });

        // Если успешно, возвращаем результат
        if (!result.error) {
          return result;
        }

        // Если ошибка rate limit, пробуем повторить
        if (result.error?.message?.includes('rate limit') && attempt < maxRetries) {
          const delay = this.calculateDelay(attempt, baseDelay, maxDelay);
          console.log(`Rate limit error, retrying in ${delay}ms (attempt ${attempt + 1}/${maxRetries + 1})`);
          await this.delay(delay);
          continue;
        }

        // Если другая ошибка или превышено количество попыток
        return result;

      } catch (error) {
        if (attempt < maxRetries) {
          const delay = this.calculateDelay(attempt, baseDelay, maxDelay);
          console.log(`Error, retrying in ${delay}ms (attempt ${attempt + 1}/${maxRetries + 1})`);
          await this.delay(delay);
          continue;
        }
        throw error;
      }
    }

    throw new Error('Max retries exceeded');
  }

  static async signInWithPassword(email: string, password: string, retryOptions?: RetryOptions) {
    const { maxRetries = 3, baseDelay = 1000, maxDelay = 10000 } = retryOptions || {};

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      try {
        const result = await supabase.auth.signInWithPassword({
          email,
          password
        });

        if (!result.error) {
          return result;
        }

        if (result.error?.message?.includes('rate limit') && attempt < maxRetries) {
          const delay = this.calculateDelay(attempt, baseDelay, maxDelay);
          console.log(`Rate limit error, retrying in ${delay}ms (attempt ${attempt + 1}/${maxRetries + 1})`);
          await this.delay(delay);
          continue;
        }

        return result;

      } catch (error) {
        if (attempt < maxRetries) {
          const delay = this.calculateDelay(attempt, baseDelay, maxDelay);
          console.log(`Error, retrying in ${delay}ms (attempt ${attempt + 1}/${maxRetries + 1})`);
          await this.delay(delay);
          continue;
        }
        throw error;
      }
    }

    throw new Error('Max retries exceeded');
  }
} 