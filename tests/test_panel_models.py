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


def test_action_request_accepts_multiselect_lists():
    from potehinsonnet.net_models.panel_ui import ActionRequest, PanelActor

    request = ActionRequest(guild_id=1, user=PanelActor(id=1, name="admin"), page="p", action="save",
                            values={"items": ["pet:a", "case:b"], "empty": [], "count": 2.0, "on": True})

    assert request.values["items"] == ["pet:a", "case:b"]
    assert request.values["empty"] == []
    # Через NATS запрос едет JSON — списки должны пережить дорогу туда и обратно
    assert ActionRequest.model_validate_json(request.model_dump_json()).values["items"] == ["pet:a", "case:b"]


def test_page_scope_default_and_owner_override():
    from potehinsonnet import Plugin
    from potehinsonnet.net_models.panel_models import PageScopes, page_key
    from potehinsonnet.net_models.system_models import Service
    from potehinsonnet.testing import FakeNats

    plugin = Plugin(Service(name="pets", label="Pets", author="", version="0"), nats=FakeNats().client())

    @plugin.panel_page("characters", title="Персонажи", scope="bot")
    async def characters(ctx):
        ...

    @plugin.panel_page("balance", title="Баланс")
    async def balance(ctx):
        ...

    infos = {info.id: info for info, _ in plugin._pages.values()}
    assert (infos["characters"].scope, infos["balance"].scope) == ("bot", "guild")   # по умолчанию — сервер

    overrides = PageScopes(scopes={page_key("pets", "balance"): "hidden"})
    assert overrides.effective("pets", infos["characters"]) == "bot"
    assert overrides.effective("pets", infos["balance"]) == "hidden"


def test_bot_page_context_has_no_guild():
    from potehinsonnet.net_models.panel_ui import PageRequest
    request = PageRequest.model_validate({"user": {"id": 1, "name": "owner"}, "page": "characters"})
    assert request.guild_id is None


def test_form_extra_buttons_roundtrip():
    from potehinsonnet.net_models.panel_ui import Form, FormButton, MultiSelect, PanelPage
    page = PanelPage(blocks=[Form(action="download", fields=[MultiSelect(name="files", label="Файлы")],
                                  buttons=[FormButton(action="delete", label="Удалить", style="danger", confirm="?")])])
    form = PanelPage.model_validate(page.model_dump(mode="json")).blocks[0]
    assert [(b.action, b.style) for b in form.buttons] == [("delete", "danger")]
    assert Form(action="x").buttons == []                     # старые формы — без изменений


def test_textarea_field_roundtrip():
    from potehinsonnet.net_models.panel_ui import Form, PanelPage, TextArea
    page = PanelPage(blocks=[Form(action="save", fields=[TextArea(name="text", label="JSON", value='{"a": 1}\n', rows=20)])])
    field = PanelPage.model_validate(page.model_dump(mode="json")).blocks[0].fields[0]
    assert type(field).__name__ == "TextArea" and field.value == '{"a": 1}\n' and field.monospace
