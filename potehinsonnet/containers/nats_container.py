from contextlib import asynccontextmanager
from typing import AsyncGenerator

from dependency_injector import containers,providers
from dependency_injector.providers import Configuration,Singleton,Resource

from potehinsonnet.discord_provider import DiscordProvider
from potehinsonnet.monitoring.health import Health
from potehinsonnet.net import NatsClient
from potehinsonnet.net_models.system_models import Service
from potehinsonnet.setup.command_registrator import CommandRegistrator






class NatsContainer(containers.DeclarativeContainer):
    config: Configuration = providers.Configuration(
        default={
            "nats": {
                "url": "nats://localhost:4222",
            },
        }
    )
    nats: Resource[NatsClient] = providers.Resource(NatsClient,
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
    health: Resource[Health] = providers.Resource(Health,
                                                  client = nats,
                                                  plugin = plugin,
                                                  )
    command_registrator: Resource[CommandRegistrator] = providers.Resource(CommandRegistrator,
                                                                             nats_client = nats,
                                                                             plugin = plugin,
                                                                             )
    discord_provider: Singleton[DiscordProvider] = providers.Singleton(DiscordProvider,
                                                                       nats_client = nats,
                                                                       )