import { afterEach, describe, expect, it, vi } from 'vitest';
import { safeCheckoutReturn, downloadMiniAppFile, miniAppChannel, miniAppPath, miniWebApp, requestMiniAppMicrophone } from './miniAppPlatform';

afterEach(() => { window.history.replaceState({}, '', '/'); delete window.WebApp; delete window.Telegram; });

describe('messenger platform isolation', () => {
  it('uses MAX bridge and channel only on MAX routes', () => {
    window.history.replaceState({}, '', '/max/control');
    window.WebApp = { initData: 'max-signed-data' };
    window.Telegram = { WebApp: { initData: 'telegram-signed-data' } };
    expect(miniWebApp()?.initData).toBe('max-signed-data');
    expect(miniAppPath()).toBe('/max/control');
    expect(miniAppChannel()).toBe('max_mini_app');
    window.history.replaceState({}, '', '/telegram/control');
    expect(miniWebApp()?.initData).toBe('telegram-signed-data');
    expect(miniAppChannel()).toBe('telegram_mini_app');
  });

  it('does not fall back to Telegram identity when MAX SDK is missing', () => {
    window.history.replaceState({}, '', '/max/control');
    window.Telegram = { WebApp: { initData: 'signed-telegram' } };
    expect(miniWebApp()).toBeUndefined();
  });

  it('downloads through the native MAX signature', () => {
    window.history.replaceState({}, '', '/max/control');
    const download = vi.fn(); window.WebApp = { downloadFile: download };
    expect(downloadMiniAppFile('https://localos.test/file', 'plan.xlsx')).toBe(true);
    expect(download).toHaveBeenCalledWith('https://localos.test/file', 'plan.xlsx');
  });

  it('propagates a microphone permission refusal before recording', async () => {
    window.history.replaceState({}, '', '/max/control');
    const init = vi.fn().mockResolvedValue(undefined);
    const requestAccess = vi.fn().mockRejectedValue(new Error('permission denied'));
    window.WebApp = { PermissionsManager: { init, requestAccess } };
    await expect(requestMiniAppMicrophone()).rejects.toThrow('permission denied');
    expect(init).toHaveBeenCalledOnce();
    expect(requestAccess).toHaveBeenCalledWith(['mic'], 'Для голосового поручения LocalOS');
  });
});

it('rejects a resolved MAX permission error before browser recording', async () => {
  window.history.replaceState({}, '', '/max/control');
  window.WebApp = { PermissionsManager: { init: vi.fn(), requestAccess: vi.fn().mockResolvedValue({ error: { code: 'client.permissions_request_access.mic_app_permission_denied' } }) } };
  await expect(requestMiniAppMicrophone()).rejects.toThrow('Разрешите микрофон');
});

it('rejects an explicitly denied system microphone permission', async () => {
  window.history.replaceState({}, '', '/max/control');
  window.WebApp = { PermissionsManager: { init: vi.fn(), requestAccess: vi.fn().mockResolvedValue({ mic: { appAccessGranted: true, systemAccessGranted: false } }) } };
  await expect(requestMiniAppMicrophone()).rejects.toThrow('Разрешите микрофон');
});

it("preserves messenger checkout returns and rejects external destinations", () => {
  for (const path of ["/max/control?screen=settings", "/telegram/control?screen=content", "/dashboard/profile#subscription"]) expect(safeCheckoutReturn(path)).toBe(path);
  for (const path of ["//evil.test", "https://evil.test", "/max/control/extra", "/dashboard/\\evil", "/max/control\n"]) expect(safeCheckoutReturn(path)).toBeNull();
});
