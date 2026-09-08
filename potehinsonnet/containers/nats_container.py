from contextlib import asynccontextmanager
from typing import AsyncGenerator

from dependency_injector import containers,providers
from dependency_injector.providers import Configuration,Singleton,Resource
from potehinsonnet.monitoring.health import Health
from potehinsonnet.net import NatsClient
from potehinsonnet.net_models.system_models import Service
from potehinsonnet.setup.command_registrator import CommandRegistrator


@asynccontextmanager
async def _init_health(client:NatsClient,plugin:Service)->AsyncGenerator[Health, None]:
    health = Health(client=client,plugin=plugin)
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
    plugin: Singleton[Service] = providers.Singleton(Service,
                                                    type= config.plugin.type,
                                                    name = config.plugin.name,
                                                    label = config.plugin.label,
                                                    description = config.plugin.description,
                                                    author = config.plugin.author,
                                                    version = config.plugin.version,
                                                    icon = config.plugin.icon,
                                                    site = config.plugin.site
                                                    )
    health: Resource[Health] = providers.Resource(_init_health,
                                                  client = nats,
                                                  plugin = plugin,
                                                  )
    command_registrator: Singleton[CommandRegistrator] = providers.Singleton(CommandRegistrator,
                                                                             nats_client = nats,
                                                                             plugin = plugin,
                                                                             )