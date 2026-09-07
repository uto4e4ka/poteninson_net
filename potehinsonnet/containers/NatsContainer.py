from contextlib import asynccontextmanager
from typing import AsyncGenerator

from dependency_injector import containers,providers
from dependency_injector.providers import Configuration,Singleton,Resource
from potehinsonnet.monitoring.health import Health

from potehinsonnet.monitoring.health import Health
from potehinsonnet.net import NatsClient
from potehinsonnet.steup.command_registrator import CommandRegistrator


@asynccontextmanager
async def _init_health(client:NatsClient,plugin_name:str,plugin_label:str)->AsyncGenerator[Health, None]:
    health = Health(client,plugin_name,plugin_label)
    await health.start()
    yield health
    await health.stop()

@asynccontextmanager
async def _init_nats(url:str)->AsyncGenerator[NatsClient, None]:
    nats = NatsClient(url)
    await nats.connect()
    yield nats
    await nats.close()

class NatsContainer(containers.DeclarativeContainer):
    config: Configuration = providers.Configuration(
        default={
            "nats": {
                "url": "nats://localhost:4222",
            },
        }
    )
    nats: Resource[NatsClient] = providers.Resource(_init_nats,
                                                                url = config.nats.url)
    health: Resource[Health] = providers.Resource(_init_health,
                                                  client = nats,
                                                  plugin_name = config.plugin.name,
                                                  plugin_label = config.plugin.label
                                                  )
    command_registrator: Singleton[CommandRegistrator] = providers.Singleton(CommandRegistrator,
                                                                             nats_client = nats,
                                                                             plugin_name = config.plugin.name,
                                                                             plugin_label = config.plugin.label
                                                                             )