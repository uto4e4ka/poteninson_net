from potehinsonnet.net_models import panel_models as panel


def test_topics_are_unique_and_namespaced():
    topics = [value for name, value in vars(panel).items() if name.isupper() and isinstance(value, str)]

    assert len(topics) == len(set(topics))
    assert all(topic.startswith("panel.") for topic in topics)


def test_permission_change_roundtrip():
    change = panel.PermissionChange(guild_id=1, permission="sound_core.*", type="ROLE", target_id=5)

    restored = panel.PermissionChange.model_validate(change.model_dump(mode="json"))

    assert restored.type is panel.PermissionTarget.ROLE
    assert restored.target_id == 5


def test_music_state_defaults_to_nothing_playing():
    state = panel.MusicState()

    assert not state.playing and state.track is None and state.queue == []


def test_music_control_accepts_string_action():
    assert panel.MusicControl(guild_id=1, action="shuffle").action is panel.MusicAction.SHUFFLE
