import asyncio

from potehinsonnet.net_models.system_models import ServiceHealthMessage
from potehinsonnet.net import NatsClient

class Health:
    def __init__(self,client: NatsClient,plugin_name:str):
        self.nats_client = client
        self.plugin_name = plugin_name
        asyncio.create_task(self._init({}))
    async def send_status(self,message:dict):
        await self.nats_client.publish("system.info.request",ServiceHealthMessage(name=self.plugin_name,status="ENABLED✅").model_dump(mode="json"))
        print("send status")

    async def _init(self,message:dict):
        await self.send_status({})
        await self.nats_client.subscribe("system.info.response", self.send_status)