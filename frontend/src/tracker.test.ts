import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { waitFor } from '@testing-library/dom';
import { describe, expect, it, vi } from 'vitest';


describe('standalone tracker consent and transport contract', () => {
  it('creates no identifiers before consent, stops after revoke, and falls back when beacon declines', async () => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 202 });
    const beaconMock = vi.fn().mockReturnValue(false);
    Reflect.set(window, 'fetch', fetchMock);
    Object.defineProperty(window.navigator, 'sendBeacon', { configurable: true, value: beaconMock });

    const script = document.createElement('script');
    script.src = 'https://localos.pro/tracker.js';
    script.setAttribute('data-business', 'pub_public-not-secret');
    script.setAttribute('data-consent', 'denied');
    Object.defineProperty(document, 'currentScript', { configurable: true, value: script });
    const source = readFileSync(join(process.cwd(), 'public', 'tracker.js'), 'utf8');
    window.eval(source);

    expect(window.localStorage.getItem('localos_visitor_id')).toBeNull();
    expect(window.sessionStorage.getItem('localos_session_id')).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();

    const tracker = Reflect.get(window, 'LocalOSTracker');
    tracker.setConsent(true);
    tracker.flush();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(window.localStorage.getItem('localos_visitor_id')).toMatch(/^v_[a-f0-9]{24}$/);
    expect(window.sessionStorage.getItem('localos_session_id')).toMatch(/^s_[a-f0-9]{24}$/);
    window.history.replaceState({}, '', window.location.pathname);
    await new Promise((resolve) => window.setTimeout(resolve, 10));
    tracker.flush();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    tracker.setConsent(true);
    tracker.flush();
    expect(fetchMock).toHaveBeenCalledTimes(1);

    tracker.setConsent(false);
    document.body.innerHTML = '<button data-localos-cta>Action</button>';
    document.querySelector('button')?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    tracker.flush();
    expect(fetchMock).toHaveBeenCalledTimes(1);

    tracker.setConsent(true);
    window.dispatchEvent(new Event('pagehide'));
    await waitFor(() => expect(beaconMock).toHaveBeenCalled());
    await waitFor(() => expect(fetchMock.mock.calls.length).toBeGreaterThan(1));
  });

  it('enables collection only on public marketing routes', async () => {
    const indexSource = readFileSync(join(process.cwd(), 'index.html'), 'utf8');
    const parsed = new DOMParser().parseFromString(indexSource, 'text/html');
    const consentSource = parsed.querySelector('#localos-public-tracking-consent')?.textContent || '';
    const setConsent = vi.fn();
    Reflect.set(window, 'LocalOSTracker', { setConsent });

    window.history.replaceState({}, '', '/dashboard/today');
    window.eval(consentSource);
    expect(Reflect.get(window, 'localosTrackingConsent')).toBe(false);

    window.history.pushState({}, '', '/articles/how-local-seo-works');
    await new Promise((resolve) => window.setTimeout(resolve, 10));
    expect(Reflect.get(window, 'localosTrackingConsent')).toBe(true);
    expect(setConsent).toHaveBeenLastCalledWith(true, { emitPageView: false });

    window.history.pushState({}, '', '/login');
    await new Promise((resolve) => window.setTimeout(resolve, 10));
    expect(Reflect.get(window, 'localosTrackingConsent')).toBe(false);
    expect(setConsent).toHaveBeenLastCalledWith(false, { emitPageView: false });
  });
});
