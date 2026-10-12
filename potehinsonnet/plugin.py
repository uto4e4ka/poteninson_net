"""Точка входа для плагинов Potehinson.

Простой плагин:

    plugin = Plugin(Service(name="beer", label="🍺 Beer", author="me", version="1.0"))

    @plugin.command(Command(name="beer", description="Цена пива", tag="beer"))
    async def beer(cmd: ExecutedCommand) -> ExecutedCommandResponse:
        return ExecutedCommandResponse(message="100 ₽", is_final=True)

    @plugin.button("beer:refresh")
    async def refresh(click: ExecutedComponent) -> ExecutedComponentResponse:
        ...

    plugin.run()

Страница в веб-панели (блоки — potehinsonnet.net_models.panel_ui):

    @plugin.panel_page("beer", title="Пиво", icon="🍺")
    async def beer_page(ctx: PanelContext) -> PanelPage:
        return PanelPage(blocks=[Text("Цена: 100 ₽"), Button(action="refresh", label="Обновить")])

    @plugin.panel_action("refresh")
    async def refresh(ctx: PanelContext, values: dict) -> str:
        return "Цена обновлена"

Плагин побольше собирает свои объекты сам и регистрирует классы с методами,
помеченными @command / @button:

    plugin = Plugin(service)
    player = MusicPlayer(Core(plugin.nats))
    plugin.register(MusicCommands(player), ButtonControl(player))
    plugin.add_lifespan(UserInteraction(...))   # любой async context manager

    async with plugin:
        await asyncio.Event().wait()
"""

import asyncio
from contextlib import AbstractAsyncContextManager, AsyncExitStack
from typing import Awaitable, Callable

from potehinsonnet.discord_provider import DiscordProvider
from potehinsonnet.monitoring.health import Health
from potehinsonnet.net import NatsClient
from potehinsonnet.net_models.discord_models import (
    Command,
    ExecutedCommand,
    ExecutedCommandResponse,
    ExecutedComponent,
    ExecutedComponentResponse,
)
from potehinsonnet.net_models.panel_models import PanelResult
from potehinsonnet.net_models.panel_ui import (
    ActionRequest,
    PageRequest,
    PanelContext,
    PanelPage,
    PanelPageInfo,
    action_subject,
    page_subject,
)
from potehinsonnet.net_models.system_models import Service
from potehinsonnet.setup.button_registrator import ButtonRegistrator
from potehinsonnet.setup.command_registrator import CommandRegistrator

CommandHandler = Callable[[ExecutedCommand], Awaitable[ExecutedCommandResponse | None]]
ButtonHandler = Callable[[ExecutedComponent], Awaitable[ExecutedComponentResponse | None]]
PageHandler = Callable[[PanelContext], Awaitable[PanelPage]]
ActionHandler = Callable[[PanelContext, dict], Awaitable[PanelResult | str | None]]


class _Handlers:
    """Хранит функции, объявленные через @plugin.command / @plugin.button.

    CommandRegistrator и ButtonRegistrator ищут помеченные методы через dir(),
    поэтому функции кладутся сюда атрибутами — так их видно так же, как методы классов.
    """


class Plugin:
    def __init__(
        self,
        service: Service,
        *,
        nats_url: str = "nats://localhost:4222",
        nats: NatsClient | None = None,
    ) -> None:
        """
        :param service: описание плагина, которое увидит бот в /health.
        :param nats_url: адрес NATS, если клиент создаёт сам плагин.
        :param nats: готовый клиент (например, в тестах). Его плагин не открывает и не закрывает.
        """
        self.service = service
        self._owns_nats = nats is None
        self.nats: NatsClient = nats if nats is not None else NatsClient(nats_url)

        self.discord = DiscordProvider(self.nats)
        self.commands = CommandRegistrator(nats_client=self.nats, plugin=service)
        self.buttons = ButtonRegistrator(nats_client=self.nats)
        self.health = Health(client=self.nats, plugin=service)

        self._handlers = _Handlers()
        self._objects: list[object] = [self._handlers]
        self._lifespans: list[AbstractAsyncContextManager] = []
        self._pages: dict[str, tuple[PanelPageInfo, PageHandler]] = {}
        self._actions: dict[str, ActionHandler] = {}
        self._stack: AsyncExitStack | None = None

    # ------------------------------------------------------------------
    # Регистрация
    # ------------------------------------------------------------------

    def command(self, cmd: Command) -> Callable[[CommandHandler], CommandHandler]:
        """Объявить слэш-команду функцией."""

        def decorator(func: CommandHandler) -> CommandHandler:
            self._ensure_not_started()
            func.__nats_command__ = cmd
            setattr(self._handlers, f"command_{cmd.tag}", func)
            return func

        return decorator

    def button(self, custom_id: str) -> Callable[[ButtonHandler], ButtonHandler]:
        """Объявить обработчик кнопки функцией."""

        def decorator(func: ButtonHandler) -> ButtonHandler:
            self._ensure_not_started()
            func.__custom_id__ = custom_id
            setattr(self._handlers, f"button_{custom_id}", func)
            return func

        return decorator

    def panel_page(self, page_id: str, title: str, icon: str = "🧩") -> Callable[[PageHandler], PageHandler]:
        """Страница плагина в веб-панели. Функция получает PanelContext и возвращает PanelPage."""

        def decorator(func: PageHandler) -> PageHandler:
            self._ensure_not_started()
            self._pages[page_id] = (PanelPageInfo(id=page_id, title=title, icon=icon), func)
            return func

        return decorator

    def panel_action(self, action: str) -> Callable[[ActionHandler], ActionHandler]:
        """Кнопка или форма на странице плагина. Функция получает PanelContext и значения полей.

        Вернуть можно текст для уведомления, PanelResult или ничего. Исключение покажется
        администратору как ошибка.
        """

        def decorator(func: ActionHandler) -> ActionHandler:
            self._ensure_not_started()
            self._actions[action] = func
            return func

        return decorator

    def register(self, *objects: object) -> None:
        """Зарегистрировать объекты с методами, помеченными @command и @button."""
        self._ensure_not_started()
        self._objects.extend(objects)

    def add_lifespan(self, context: AbstractAsyncContextManager) -> None:
        """Запустить async context manager вместе с плагином и закрыть при остановке."""
        self._ensure_not_started()
        self._lifespans.append(context)

    def _ensure_not_started(self) -> None:
        if self._stack is not None:
            raise RuntimeError("Регистрировать команды, кнопки и lifespan нужно до запуска плагина")

    # ------------------------------------------------------------------
    # Жизненный цикл
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._ensure_not_started()
        stack = AsyncExitStack()
        self._stack = stack
        try:
            if self._owns_nats:
                await self.nats.connect()
                stack.push_async_callback(self.nats.close)

            for context in self._lifespans:
                await stack.enter_async_context(context)

            await self.buttons.subscribe()
            stack.push_async_callback(self.buttons.unsubscribe)
            for obj in self._objects:
                await self.buttons.register_instance(obj)

            if self._pages:
                # Список страниц уходит боту вместе с регистрацией, а панель берёт его у бота
                self.service.panel_pages = [info for info, _ in self._pages.values()]
                page_sub = await self.nats.subscribe(page_subject(self.service.name), self._on_page)
                stack.push_async_callback(page_sub.unsubscribe)
                action_sub = await self.nats.subscribe(action_subject(self.service.name), self._on_action)
                stack.push_async_callback(action_sub.unsubscribe)

            stack.push_async_callback(self.commands.close)
            # Команды отправляются боту после регистрации и повторно, если бот перезапустился
            await self.health.add_listener(self._install_commands)
            await self.health.start()
            stack.push_async_callback(self.health.stop)
        except BaseException:
            await self.stop()
            raise

    async def stop(self) -> None:
        """Останавливает всё строго в обратном порядке запуска."""
        stack, self._stack = self._stack, None
        if stack is not None:
            await stack.aclose()

    async def _on_page(self, body: dict) -> dict:
        request = PageRequest.model_validate(body)
        entry = self._pages.get(request.page)
        if entry is None:
            raise ValueError(f"Страница {request.page} не найдена")
        _, handler = entry
        page = await handler(PanelContext(guild_id=request.guild_id, user=request.user))
        return page.model_dump(mode="json")

    async def _on_action(self, body: dict) -> dict:
        request = ActionRequest.model_validate(body)
        handler = self._actions.get(request.action)
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

    async def _install_commands(self, bot: Service) -> None:
        for obj in self._objects:
            await self.commands.register_instance_commands(obj, sync=False)
        await self.commands.sync_commands()

    async def __aenter__(self) -> "Plugin":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.stop()

    async def serve(self) -> None:
        """Работать, пока задачу не отменят (Ctrl+C или остановка сервиса)."""
        async with self:
            await asyncio.Event().wait()

    def run(self) -> None:
        """Запустить плагин в отдельном event loop. Удобно для простых плагинов."""
        try:
            asyncio.run(self.serve())
        except KeyboardInterrupt:
            pass
