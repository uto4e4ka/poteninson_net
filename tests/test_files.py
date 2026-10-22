"""Большие файлы через хранилище NATS: положить, забрать, протухшая ссылка."""
import io

import pytest

from potehinsonnet import Plugin
from potehinsonnet.files import UPLOADS_BUCKET, FileStore
from potehinsonnet.net_models.panel_ui import ActionRequest, FileRef
from potehinsonnet.net_models.system_models import Service
from potehinsonnet.testing import FakeNats


async def test_put_save_read_delete(tmp_path):
    bus = FakeNats()
    files = FileStore(bus.client())
    content = bytes(range(256)) * 10_000                              # 2.5 МБ — больше сообщения NATS

    ref = await files.put(io.BytesIO(content), "dir/plugin.zip")
    assert (ref.bucket, ref.filename, ref.size) == (UPLOADS_BUCKET, "plugin.zip", len(content))

    saved = await files.save(ref, tmp_path / "out" / "x.zip")
    assert saved.read_bytes() == content and await files.read(ref) == content

    await files.delete(ref)
    with pytest.raises(FileNotFoundError, match="загрузите ещё раз"):
        await files.save(ref, tmp_path / "gone.zip")
    assert not (tmp_path / "gone.zip").exists()


async def test_plugin_action_gets_file_ref_and_reads_it():
    bus = FakeNats()
    plugin = Plugin(Service(name="p", label="P", author="", version="0"), nats=bus.client())
    got = []

    @plugin.panel_action("upload")
    async def upload(ctx, values):
        got.append(await plugin.files.read(values["archive"]))
        return "ok"

    ref = await FileStore(bus.client()).put(b"zip-bytes", "a.zip")
    request = ActionRequest(user={"id": 1, "name": "a"}, page="x", action="upload", values={"archive": ref})
    result = await plugin.panel.on_action(request.model_dump(mode="json"))

    assert result["ok"] and got == [b"zip-bytes"]
    assert isinstance(ActionRequest.model_validate(request.model_dump(mode="json")).values["archive"], FileRef)


async def test_action_can_return_a_file_to_download():
    bus = FakeNats()
    plugin = Plugin(Service(name="p", label="P", author="", version="0"), nats=bus.client())

    @plugin.panel_action("export")
    async def export(ctx, values):
        from potehinsonnet.net_models.panel_models import PanelResult
        return PanelResult(message="Готово", download=await plugin.files.put(b"data", "export.zip"))

    request = ActionRequest(user={"id": 1, "name": "a"}, page="x", action="export")
    result = await plugin.panel.on_action(request.model_dump(mode="json"))

    ref = FileRef.model_validate(result["download"])
    assert result["ok"] and ref.filename == "export.zip" and await plugin.files.read(ref) == b"data"
