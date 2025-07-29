class RateLimiter {
  private attempts: Map<string, { count: number; lastAttempt: number }> = new Map();
  private readonly maxAttempts = 3; // Максимум попыток за период
  private readonly windowMs = 60000; // 1 минута

  canAttempt(key: string): boolean {
    const now = Date.now();
    const attempt = this.attempts.get(key);

    if (!attempt) {
      this.attempts.set(key, { count: 1, lastAttempt: now });
      return true;
    }

    // Сброс счетчика, если прошло больше времени
    if (now - attempt.lastAttempt > this.windowMs) {
      this.attempts.set(key, { count: 1, lastAttempt: now });
      return true;
    }

    // Проверка лимита
    if (attempt.count >= this.maxAttempts) {
      return false;
    }

    // Увеличение счетчика
    attempt.count++;
    attempt.lastAttempt = now;
    return true;
  }

  getRemainingTime(key: string): number {
    const attempt = this.attempts.get(key);
    if (!attempt) return 0;

    const timePassed = Date.now() - attempt.lastAttempt;
    return Math.max(0, this.windowMs - timePassed);
  }

  reset(key: string): void {
    this.attempts.delete(key);
  }
}

export const rateLimiter = new RateLimiter(); 