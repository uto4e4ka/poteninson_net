import asyncio
from argparse import OPTIONAL
from typing import Callable, Awaitable, Optional, List

from potehinsonnet.net_models.system_models import ServiceHealthMessage, ServiceRegistrationRequest, Service, \
    ServiceRegistrationResponse
from potehinsonnet.net import NatsClient

class Health:
    def __init__(self,
                 client: NatsClient,plugin_label:str,
                 plugin:Service,
                 on_registration: Optional[List[Callable[[Service], Awaitable[None]]]] = None):
        self.nats_client = client
        self.plugin = plugin
        self._subs = []
        self.has_registration = False
        self._on_registration: List[Callable[[Service], Awaitable[None]]] = (
            on_registration if on_registration is not None else []
        )

    async def send_status(self,status = "ENABLED✅"):
        await self.nats_client.publish("system.info.request",
                                       ServiceHealthMessage(name=self.plugin.name,status=status).model_dump(mode="json")
                                       )

    async def _handle_request(self,body):
        await self.send_status()

    async def _handle_registration(self,body):
        service_registration = ServiceRegistrationRequest(
            **self.plugin.model_dump(),
            status="ENABLED✅"
        )
        response = await self.nats_client.request(
            "system.info.registration.init",
            service_registration.model_dump(mode="json")
        )
        response = ServiceRegistrationResponse.model_validate(response)
        if response.success:
            print("Plugin successfully registered")
            await self._notify_all()

    async def _notify_all(self):
        for callback in self._on_registration:
            await callback(self.plugin)

    async def add_listener(self,listener: Callable[[Service], Awaitable[None]])-> None:
        self._on_registration.append(listener)

    async def start(self):
        self._subs.append(await self.nats_client.subscribe("system.info.response", self._handle_request))
        self._subs.append(await self.nats_client.subscribe("system.info.registration.init", self._handle_request))
        await self.send_status()

    async def stop(self):
        await self.send_status(status="DISABLED❌")
        for sub in self._subs:
            if sub:
                try:
                    await sub.unsubscribe()
                except Exception as e:
                    print(f"Failed to unsubscribe: {e}")
        self._subs.clear()

