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
from potehinsonnet.net_models.system_models import Service
from potehinsonnet.setup.button_registrator import ButtonRegistrator
from potehinsonnet.setup.command_registrator import CommandRegistrator

CommandHandler = Callable[[ExecutedCommand], Awaitable[ExecutedCommandResponse | None]]
ButtonHandler = Callable[[ExecutedComponent], Awaitable[ExecutedComponentResponse | None]]


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
