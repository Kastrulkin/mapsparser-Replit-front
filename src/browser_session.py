from __future__ import annotations

"""
browser_session.py — вспомогательный модуль для управления Playwright-сессиями.

Задача:
- инкапсулировать lifecycle Playwright (start/stop, launch/close браузера)
- предоставить простой объект BrowserSession, который использует парсер
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional
import uuid

from playwright.sync_api import sync_playwright


@dataclass
class BrowserSession:
    """Единая сессия браузера для human-in-the-loop капчи и парсинга."""

    session_id: str
    playwright: Any
    browser: Any
    context: Any
    page: Any
    created_at: datetime
    keep_open: bool = False


class BrowserSessionManager:
    """Управление жизненным циклом BrowserSession.

    ВАЖНО: менеджер не хранит состояние, registry передаётся снаружи.
    """

    def open_session(
        self,
        *,
        headless: bool = True,
        cookies: Optional[list[dict]] = None,
        user_agent: Optional[str] = None,
        viewport: Optional[Dict[str, int]] = None,
        locale: Optional[str] = None,
        timezone_id: Optional[str] = None,
        proxy: Optional[Dict[str, Any]] = None,
        launch_args: Optional[list[str]] = None,
        init_scripts: Optional[list[str]] = None,
        keep_open: bool = False,
    ) -> BrowserSession:
        """Создать новую Playwright-сессию (единый источник правды по stealth)."""
        playwright = sync_playwright().start()
        browser = None
        context = None
        try:
            args = launch_args or [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-images",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
            ]

            browser = playwright.chromium.launch(
                headless=headless,
                proxy=proxy,
                args=args,
            )

            context_kwargs: Dict[str, Any] = {}
            if user_agent:
                context_kwargs["user_agent"] = user_agent
            if viewport:
                context_kwargs["viewport"] = viewport
                context_kwargs["device_scale_factor"] = 1
            if locale:
                context_kwargs["locale"] = locale
            if timezone_id:
                context_kwargs["timezone_id"] = timezone_id

            context = browser.new_context(**context_kwargs)

            scripts = init_scripts if init_scripts is not None else default_stealth_scripts()
            for script in scripts:
                try:
                    context.add_init_script(script)
                except Exception:
                    # init_script — best-effort
                    pass

            if cookies:
                try:
                    context.add_cookies(cookies)
                except Exception:
                    # Куки — best-effort, не валим сессию
                    pass

            page = context.new_page()

            session = BrowserSession(
                session_id=str(uuid.uuid4()),
                playwright=playwright,
                browser=browser,
                context=context,
                page=page,
                created_at=datetime.utcnow(),
                keep_open=keep_open,
            )
            return session
        except Exception:
            # Если что-то пошло не так — корректно закрываем все уровни
            try:
                if context is not None:
                    context.close()
            except Exception:
                pass
            try:
                if browser is not None:
                    browser.close()
            except Exception:
                pass
            try:
                playwright.stop()
            except Exception:
                pass
            raise

    def close_session(self, session: Optional[BrowserSession]) -> None:
        """Безопасно закрыть сессию браузера."""
        if not session:
            return

        # Закрываем по цепочке: page -> context -> browser -> playwright
        for obj, close_method in (
            (getattr(session, "page", None), "close"),
            (getattr(session, "context", None), "close"),
            (getattr(session, "browser", None), "close"),
        ):
            if obj is None:
                continue
            try:
                getattr(obj, close_method)()
            except Exception:
                # Закрываем best-effort, не ломаем основной поток
                pass

        try:
            if getattr(session, "playwright", None) is not None:
                session.playwright.stop()
        except Exception:
            pass

    def park(self, registry: Dict[str, BrowserSession], session: BrowserSession) -> str:
        """Положить сессию в registry по её session_id."""
        registry[session.session_id] = session
        return session.session_id

    def get(self, registry: Dict[str, BrowserSession], session_id: str) -> Optional[BrowserSession]:
        """Достать сессию из registry по session_id."""
        return registry.get(session_id)


def default_stealth_scripts() -> list[str]:
    """Базовые anti-detect скрипты для всех Playwright-сессий."""
    return [
        """
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
        });
        try {
            delete navigator.__proto__.webdriver;
        } catch (e) {}
        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        window.chrome = { runtime: {} };
        Object.defineProperty(navigator, 'languages', {get: () => ['ru-RU', 'ru']});
        """
    ]


