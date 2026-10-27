import asyncio
import inspect
from typing import Awaitable, Callable

from nats.aio.subscription import Subscription

from potehinsonnet.net import NatsClient
from potehinsonnet.net_models.discord_models import ExecutedComponentResponse, ExecutedComponent, ExecutedCommand

from types import TracebackType

from typing import AsyncIterator, Awaitable, Callable, TypeVar

T = TypeVar("T")

ButtonMethod = Callable[
    [T, ExecutedComponent],
    Awaitable[ExecutedComponentResponse | None] | AsyncIterator[ExecutedComponentResponse],
]

# custom_id в одном сообщении должны быть разными. Для кнопок-списков (по одной на предмет)
# пишите "base|что-угодно": найдётся обработчик @button("base"), полный id — в ExecutedComponent.id
ID_SEPARATOR = "|"


def button(custom_id: str):
    def decorator(
        func: ButtonMethod[T],
    ) -> ButtonMethod[T]:
        func.__custom_id__ = custom_id
        return func

    return decorator


class ButtonRegistrator:
    def __init__(self, nats_client: NatsClient):
        self.nats_client = nats_client
        self.sub:Subscription|None =  None
        self.components:dict[str,Callable[[ExecutedComponent], Awaitable[ExecutedComponentResponse|None]]] = {}
        self._tasks: set[asyncio.Task] = set()


    async def register_instance(self,instance:object):
        for attr_name in dir(instance):
            method = getattr(instance, attr_name)

            # Проверяем, есть ли у метода метка от декоратора @command
            if hasattr(method, "__custom_id__"):
                custom_id: str = getattr(method, "__custom_id__")
                self.components[custom_id] = method

    def _find(self, custom_id: str):
        method = self.components.get(custom_id)
        if method is None and ID_SEPARATOR in custom_id:
            method = self.components.get(custom_id.split(ID_SEPARATOR, 1)[0])
        return method

    async def on_click(self,body:dict):
        executed = ExecutedComponent.model_validate(body)
        method = self._find(executed.id)
        if method is None:
            return
        # Отдельной задачей: NATS отдаёт сообщения подписки по одному, и долгий обработчик
        # (анимация) иначе держал бы нажатия всех остальных игроков
        task = asyncio.create_task(self._handle(method, executed))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _handle(self, method, executed: ExecutedComponent):
        reply = f"discord.component.{executed.task_id}.reply"
        try:
            result = method(executed)
            if inspect.isasyncgen(result):
                # Генератор — несколько ответов подряд (анимация): is_finish=False у всех, кроме последнего
                last = None
                async for frame in result:
                    last = frame
                    await self.nats_client.publish(reply, frame.model_dump(mode="json"))
                if last is not None and not last.is_finish:
                    # Бот держит подписку до is_finish — закрываем её, если последний кадр не пометили
                    await self.nats_client.publish(
                        reply, last.model_copy(update={"is_finish": True}).model_dump(mode="json"),
                    )
                return
            result = await result
        except Exception as e:
            result = ExecutedComponentResponse(message=f"{e}",ephemeral=True)
        await self.nats_client.publish(
            reply,
            result.model_dump(mode="json") if result else None,
        )

    async def subscribe(self):
        self.sub = await self.nats_client.subscribe("discord.component.execute",self.on_click)

    async def unsubscribe(self):
        if self.sub:
            await self.sub.unsubscribe()

    async def __aenter__(self):
        await self.subscribe()
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None):
        await self.unsubscribe()

