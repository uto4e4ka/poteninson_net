# potehinsonnet

Библиотека для плагинов Discord-бота **Potehinson**. Плагин — отдельный процесс: бот держит соединение
с Discord, а плагин общается с ним через [NATS](https://nats.io) — регистрирует слэш-команды и кнопки,
отвечает на них, отдаёт страницы веб-панели и хранит свои данные.

```bash
pip install potehinsonnet
```

Нужен Python 3.14+.

## Плагин за минуту

`plugin.toml` в корне плагина:

```toml
[plugin]
name = "beer_plugin"
label = "🍺 Пивная биржа"
version = "1.0.0"

[runtime]
entry = "beer_plugin.main:create_plugin"
potehinsonnet = ">=0.19,<1.0"

[permissions]
discord = ["send_message"]
commands = true
panel = true

[settings.api_key]
label = "Ключ API"
secret = true
```

`beer_plugin/main.py`:

```python
from potehinsonnet import Plugin, PluginContext
from potehinsonnet.net_models.discord_models import Command, ExecutedCommand, ExecutedCommandResponse
from potehinsonnet.net_models.panel_ui import Button, PanelContext, PanelPage, Text
from pydantic import BaseModel


class Price(BaseModel):
    beer: str
    rub: int


def create_plugin(ctx: PluginContext) -> Plugin:
    plugin = Plugin.from_context(ctx)
    prices = ctx.data.collection("prices.json", Price, key="beer")      # файл в папке данных плагина

    @plugin.command(Command(name="beer", description="Цена пива", tag="beer"))
    async def beer(cmd: ExecutedCommand) -> ExecutedCommandResponse:
        price = prices.get("лагер")
        return ExecutedCommandResponse(message=f"{price.rub if price else '?'} ₽", is_final=True)

    @plugin.panel_page("beer", title="Пиво", icon="🍺")              # страница в веб-панели
    async def beer_page(panel: PanelContext) -> PanelPage:
        return PanelPage(blocks=[Text(f"Сортов: {len(prices.all())}"), Button(action="reset", label="Сбросить")])

    @plugin.panel_action("reset")
    async def reset(panel: PanelContext, values: dict) -> str:
        prices.replace_all([])
        return "Цены сброшены"

    return plugin
```

Запуск: хост бота ставит и запускает плагин сам (zip через панель). Для разработки —
`python -m potehinsonnet.run .` из папки плагина (нужен NATS на `localhost:4222`).

## Что внутри

| Модуль | Для чего |
|---|---|
| `Plugin`, `PluginContext` | плагин, его настройки (`ctx.settings`), папка данных, адрес NATS — всё от хоста |
| `@plugin.command`, `@plugin.button` | слэш-команды и кнопки Discord; ответ — один или поток кадров (анимация) |
| `plugin.discord` | отправить, изменить, удалить сообщение; голосовые каналы |
| `@plugin.panel_page`, `panel_action` | страницы веб-панели из блоков (`net_models.panel_ui`): текст, таблицы, формы, кнопки, разделы, загрузка файлов |
| `ctx.data` (`storage`) | данные плагина в JSON: `collection`, `document`, `file` — проверка моделью pydantic, атомарная запись, битые файлы откладываются, а не затираются |
| `plugin.files` (`files`) | большие файлы через NATS Object Store: загрузка из панели и выдача на скачивание |
| `python -m potehinsonnet.pack` | собрать zip плагина для установки через панель (`--bump patch`, `--no-data`) |
| `potehinsonnet.testing` | `FakeNats` — NATS в памяти для тестов плагина |
