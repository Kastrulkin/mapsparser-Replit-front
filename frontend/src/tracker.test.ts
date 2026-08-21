import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { waitFor } from '@testing-library/dom';
import { describe, expect, it, vi } from 'vitest';


describe('standalone tracker consent and transport contract', () => {
  it('creates no identifiers before consent, stops after revoke, and falls back when beacon declines', async () => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    document.body.innerHTML = '<nav><a href="#services">Услуги</a></nav><main><section id="services"><div class="tn-atom">Технический текст</div></section></main>';
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 202 });
    const beaconMock = vi.fn().mockReturnValue(false);
    let intersectionCallback: IntersectionObserverCallback | null = null;
    class IntersectionObserverMock {
      constructor(callback: IntersectionObserverCallback) {
        intersectionCallback = callback;
      }
      observe() { return undefined; }
      disconnect() { return undefined; }
    }
    Reflect.set(window, 'fetch', fetchMock);
    Reflect.set(window, 'IntersectionObserver', IntersectionObserverMock);
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

    const sectionEntry = Object.create(null);
    Reflect.set(sectionEntry, 'target', document.querySelector('#services'));
    Reflect.set(sectionEntry, 'isIntersecting', true);
    Reflect.set(sectionEntry, 'intersectionRatio', 0.2);
    Reflect.set(sectionEntry, 'boundingClientRect', { height: 3000 });
    Reflect.set(sectionEntry, 'rootBounds', { height: 900 });
    Reflect.set(sectionEntry, 'intersectionRect', { height: 600 });
    if (intersectionCallback) Reflect.apply(intersectionCallback, null, [[sectionEntry]]);
    await new Promise((resolve) => window.setTimeout(resolve, 1050));
    tracker.flush();
    const sectionEvents = fetchMock.mock.calls
      .flatMap((call) => JSON.parse(String(call[1]?.body)).events)
      .filter((event) => event.event === 'section_view');
    expect(sectionEvents).toEqual([expect.objectContaining({ section: { key: 'services', label: 'Услуги', position: 1 } })]);

    const callsBeforeSamePageReplace = fetchMock.mock.calls.length;
    const initialNow = Date.now();
    const nowSpy = vi.spyOn(Date, 'now').mockReturnValue(initialNow + 2_000);
    window.history.replaceState({}, '', window.location.pathname);
    await new Promise((resolve) => window.setTimeout(resolve, 10));
    tracker.flush();
    const eventsAfterSamePageReplace = fetchMock.mock.calls
      .slice(callsBeforeSamePageReplace)
      .flatMap((call) => JSON.parse(String(call[1]?.body)).events);
    expect(eventsAfterSamePageReplace.filter((event) => event.event === 'page_view')).toHaveLength(0);
    nowSpy.mockRestore();

    const sameSiteLink = document.createElement('a');
    sameSiteLink.href = 'https://www.localhost/internal';
    sameSiteLink.textContent = 'Internal';
    sameSiteLink.addEventListener('click', (event) => event.preventDefault());
    document.body.appendChild(sameSiteLink);
    sameSiteLink.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
    tracker.flush();
    const clickEvents = fetchMock.mock.calls
      .flatMap((call) => JSON.parse(String(call[1]?.body)).events)
      .filter((event) => event.element?.text === 'Internal');
    expect(clickEvents).toEqual([expect.objectContaining({ event: 'click' })]);

    const callsAfterInternalClick = fetchMock.mock.calls.length;
    tracker.setConsent(true);
    tracker.flush();
    expect(fetchMock).toHaveBeenCalledTimes(callsAfterInternalClick);

    tracker.setConsent(false);
    document.body.innerHTML = '<button data-localos-cta>Action</button>';
    document.querySelector('button')?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    tracker.flush();
    expect(fetchMock).toHaveBeenCalledTimes(callsAfterInternalClick);

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
