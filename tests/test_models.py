import time

from potehinsonnet.net_models.discord_models import (
    ActionRow,
    ComponentButton,
    ComponentThumbnail,
    Container,
    ExecutedCommandResponse,
    MediaGallery,
    NatsMessage,
    Section,
    Separator,
    TextDisplay,
)
from potehinsonnet.net_models.system_models import ServiceHealthMessage, ServiceRegistrationRequest


def test_health_message_timestamp_is_fresh():
    first = ServiceHealthMessage(name="a", status="s")
    time.sleep(0.01)
    second = ServiceHealthMessage(name="a", status="s")

    assert second.time > first.time


def test_registration_request_timestamp_is_fresh():
    first = ServiceRegistrationRequest(name="a", label="l", author="x", version="1", status="s")
    time.sleep(0.01)
    second = ServiceRegistrationRequest(name="a", label="l", author="x", version="1", status="s")

    assert second.time > first.time


def test_container_roundtrip_keeps_component_types():
    container = Container(
        accent_color=0xFF0000,
        components=[
            TextDisplay(content="text"),
            Section(content="s", accessory=ComponentThumbnail(url="https://x/y.png")),
            Section(content="s", accessory=ComponentButton(label="b", custom_id="id")),
            MediaGallery(),
            Separator(),
            ActionRow(components=[ComponentButton(label="b", custom_id="c", context={"a": 1})]),
        ],
    )

    message = NatsMessage(service="s", text="", channel_id=1, containers=[container])
    restored = NatsMessage.model_validate(message.model_dump(mode="json"))

    components = restored.containers[0].components
    assert [type(c).__name__ for c in components] == [
        "TextDisplay", "Section", "Section", "MediaGallery", "Separator", "ActionRow",
    ]
    assert isinstance(components[1].accessory, ComponentThumbnail)
    assert isinstance(components[2].accessory, ComponentButton)
    assert components[5].components[0].context == {"a": 1}


def test_command_response_is_not_final_by_default():
    assert ExecutedCommandResponse().is_final is False
