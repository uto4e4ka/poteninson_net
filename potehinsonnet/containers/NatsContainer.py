from typing import AsyncGenerator

from dependency_injector import containers,providers
from dependency_injector.providers import Configuration,Singleton,Resource
from potehinsonnet.monitoring.health import Health

from potehinsonnet.monitoring.health import Health
from potehinsonnet.net import NatsClient

async def _init_health(client:NatsClient,plugin_name:str)->AsyncGenerator[Health, None]:
    health = Health(client,plugin_name)
    await health.start()
    yield health
    await health.stop()

async def _init_nats(url:str)->AsyncGenerator[NatsClient, None]:
    nats = NatsClient(url)
    await nats.connect()
    yield nats
    await nats.close()

class NatsContainer(containers.DeclarativeContainer):
    config: Configuration = providers.Configuration()
    nats: Resource[NatsClient] = providers.Resource(_init_nats,
                                                                url = config.nats.url)
    health: Resource[Health] = providers.Resource(_init_health,
                                                  client = nats,
                                                  plugin_name = config.plugin.name)