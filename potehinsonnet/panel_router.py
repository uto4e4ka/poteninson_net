"""Страницы веб-панели: регистрация и ответы на запросы панели.

Плагин пользуется им через Plugin.panel_page / panel_action. Так же страницы может отдавать и сам бот
(например, «Плагины» и «Права ролей»): панели всё равно, кто отвечает на panel.page.<имя>.
"""
from typing import Awaitable, Callable

from potehinsonnet.net import NatsClient
from potehinsonnet.net_models.panel_models import PanelResult
from potehinsonnet.net_models.panel_ui import (
    ActionRequest,
    PageRequest,
    PageScope,
    PanelContext,
    PanelPage,
    PanelPageInfo,
    action_subject,
    page_subject,
)

PageHandler = Callable[[PanelContext], Awaitable[PanelPage]]
ActionHandler = Callable[[PanelContext, dict], Awaitable["PanelResult | str | None"]]


class PanelRouter:

    def __init__(self, nats: NatsClient, name: str):
        self.nats = nats
        self.name = name
        self.pages: dict[str, tuple[PanelPageInfo, PageHandler]] = {}
        self.actions: dict[str, ActionHandler] = {}
        self._subs = []

    def page(self, page_id: str, title: str, icon: str = "🧩", group: str = "",
             scope: PageScope = "guild") -> Callable[[PageHandler], PageHandler]:
        """Страница: функция получает PanelContext и возвращает PanelPage. О scope — см. Plugin.panel_page."""

        def decorator(func: PageHandler) -> PageHandler:
            info = PanelPageInfo(id=page_id, title=title, icon=icon, group=group, scope=scope)
            self.pages[page_id] = (info, func)
            return func

        return decorator

    def action(self, action: str) -> Callable[[ActionHandler], ActionHandler]:
        """Кнопка или форма: функция получает PanelContext и значения полей; вернуть — текст, PanelResult
        или ничего. Исключение покажется как ошибка."""

        def decorator(func: ActionHandler) -> ActionHandler:
            self.actions[action] = func
            return func

        return decorator

    @property
    def infos(self) -> list[PanelPageInfo]:
        return [info for info, _ in self.pages.values()]

    async def start(self) -> None:
        # Панель грузит страницы параллельно — отвечаем параллельно, а не по очереди
        self._subs = [
            await self.nats.subscribe(page_subject(self.name), self.on_page, concurrent=True),
            await self.nats.subscribe(action_subject(self.name), self.on_action, concurrent=True),
        ]

    async def stop(self) -> None:
        subs, self._subs = self._subs, []
        for sub in subs:
            await sub.unsubscribe()

    async def on_page(self, body: dict) -> dict:
        request = PageRequest.model_validate(body)
        entry = self.pages.get(request.page)
        if entry is None:
            raise ValueError(f"Страница {request.page} не найдена")
        _, handler = entry
        page = await handler(PanelContext(guild_id=request.guild_id, user=request.user))
        return page.model_dump(mode="json")

    async def on_action(self, body: dict) -> dict:
        request = ActionRequest.model_validate(body)
        handler = self.actions.get(request.action)
        if handler is None:
            return PanelResult(ok=False, message=f"Действие {request.action} не найдено").model_dump(mode="json")

        try:
            values = {**request.values, **request.files}
            result = await handler(PanelContext(guild_id=request.guild_id, user=request.user), values)
        except Exception as e:
            result = PanelResult(ok=False, message=str(e) or type(e).__name__)

        if result is None:
            result = PanelResult(message="Готово")
        elif isinstance(result, str):
            result = PanelResult(message=result)
        return result.model_dump(mode="json")
