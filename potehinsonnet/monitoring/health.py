import asyncio

from potehinsonnet.net_models.system_models import ServiceHealthMessage
from potehinsonnet.net import NatsClient

class Health:
    def __init__(self,client: NatsClient,plugin_label:str,plugin_name:str):
        self.nats_client = client
        self.plugin_name = plugin_name
        self.plugin_label = plugin_label
        self._sub = None

    async def send_status(self,status = "ENABLED✅"):
        await self.nats_client.publish("system.info.request",ServiceHealthMessage(name=self.plugin_name,status=status).model_dump(mode="json"))
        print("send status")

    async def _handle_request(self,body):
        await self.send_status()

    async def start(self):
        self._sub = await self.nats_client.subscribe("system.info.response", self._handle_request)
        await self.send_status()

    async def stop(self):
        await self.send_status(status="DISABLED❌")
        if self._sub:
            try:
                await self._sub.unsubscribe()
            except Exception as e:
                print(f"Failed to unsubscribe: {e}")
            self._sub = None

