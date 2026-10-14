"""Страницы плагинов в веб-панели.

Плагин описывает страницу блоками, а панель рисует их своими шаблонами — так плагин
не может подсунуть в панель свой HTML или скрипт, а все страницы выглядят одинаково.

    PanelPage(blocks=[
        Text("Цена сегодня: 120 ₽", style="title"),
        KeyValue(items={"Канал": "#общий", "Рассылка": "каждый день в 10:00"}),
        Form(action="save", submit="Сохранить", fields=[
            Select(name="channel_id", label="Канал", options=[Option(value="1", label="#общий")]),
            Toggle(name="daily", label="Каждый день"),
        ]),
        Button(action="send_now", label="Отправить сейчас"),
    ])
"""
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from potehinsonnet.net_models.discord_models import Attachment

# ============================================================
# ТЕМЫ
# ============================================================


def page_subject(plugin: str) -> str:
    """Запрос страницы плагина. Тело — PageRequest, ответ — PanelPage."""
    return f"panel.page.{plugin}"


def action_subject(plugin: str) -> str:
    """Кнопка или форма на странице плагина. Тело — ActionRequest, ответ — PanelResult."""
    return f"panel.action.{plugin}"


# ============================================================
# ОПИСАНИЕ СТРАНИЦ (при регистрации плагина)
# ============================================================

class PanelPageInfo(BaseModel):
    id: str
    title: str
    icon: str = "🧩"
    # Карточки с одной группой панель показывает рядом под общим заголовком; пусто — группа по плагину
    group: str = ""


# ============================================================
# БЛОКИ
# ============================================================

class Text(BaseModel):
    type: Literal["text"] = "text"
    content: str
    style: Literal["normal", "title", "muted"] = "normal"

    def __init__(self, content: str = "", **data):
        super().__init__(content=content, **data)


class KeyValue(BaseModel):
    """Список "название — значение"."""

    type: Literal["key_value"] = "key_value"
    items: dict[str, str] = Field(default_factory=dict)


# Картинки: https://… или маленькая картинка прямо в адресе — data:image/jpeg;base64,…
# (так плагин показывает свои файлы: браузер не может открыть файл с диска плагина).
# Страница целиком едет через NATS (до ~1 МБ), поэтому в data: — только уменьшенные копии.

class Image(BaseModel):
    type: Literal["image"] = "image"
    url: str
    alt: str = ""


class Media(BaseModel):
    """Картинка слева, заголовок и подписи справа — например, трек с обложкой."""

    type: Literal["media"] = "media"
    title: str
    subtitle: str = ""
    caption: str = ""
    image_url: str = ""
    url: str = ""          # ссылка на заголовке


class Link(BaseModel):
    type: Literal["link"] = "link"
    url: str
    label: str


class Button(BaseModel):
    """Кнопка: вызывает действие плагина, values уходят вместе с ним."""

    type: Literal["button"] = "button"
    action: str
    label: str
    style: Literal["normal", "primary", "danger"] = "normal"
    confirm: str = ""
    values: dict[str, str] = Field(default_factory=dict)
    disabled: bool = False
    active: bool = False   # подсветка "включено", например для перемешивания


class TableRow(BaseModel):
    cells: list[str]
    actions: list[Button] = Field(default_factory=list)


class ListItem(BaseModel):
    title: str
    subtitle: str = ""
    image_url: str = ""    # маленькая картинка слева: https://… или data:image/…
    actions: list[Button] = Field(default_factory=list)


class ItemList(BaseModel):
    """Компактный список: картинка, название, подпись и кнопки в одну строку.

    Если строк больше max_visible, панель ограничивает высоту и включает прокрутку внутри списка —
    блоки ниже (например, форма добавления) остаются на виду.
    """

    type: Literal["item_list"] = "item_list"
    items: list[ListItem] = Field(default_factory=list)
    empty: str = "Пусто"
    max_visible: int = 8


class Table(BaseModel):
    type: Literal["table"] = "table"
    columns: list[str]
    rows: list[TableRow] = Field(default_factory=list)
    empty: str = "Пусто"


# --- поля формы ---

class TextField(BaseModel):
    type: Literal["text"] = "text"
    name: str
    label: str
    value: str = ""
    placeholder: str = ""
    required: bool = False


class NumberField(BaseModel):
    type: Literal["number"] = "number"
    name: str
    label: str
    value: float | None = None
    min: float | None = None
    max: float | None = None
    step: float | None = None


class Option(BaseModel):
    value: str
    label: str
    group: str = ""   # раздел в списке: подряд идущие варианты с одной группой показываются вместе


class Select(BaseModel):
    type: Literal["select"] = "select"
    name: str
    label: str
    options: list[Option] = Field(default_factory=list)
    value: str = ""


class MultiSelect(BaseModel):
    """Выбор нескольких вариантов: поиск, выбранное — «чипами». Плагин получает list[str] (пустой — ничего)."""

    type: Literal["multiselect"] = "multiselect"
    name: str
    label: str
    options: list[Option] = Field(default_factory=list)
    value: list[str] = Field(default_factory=list)
    placeholder: str = "Найти…"


class Toggle(BaseModel):
    type: Literal["toggle"] = "toggle"
    name: str
    label: str
    value: bool = False


# --- выбор участника, роли, канала: списки панель берёт у бота сама ---

class MemberPicker(BaseModel):
    """Участник сервера с поиском по имени. Плагин получает ID (int)."""

    type: Literal["member"] = "member"
    name: str
    label: str
    value: int | None = None


class RolePicker(BaseModel):
    """Роль сервера. Плагин получает ID (int)."""

    type: Literal["role"] = "role"
    name: str
    label: str
    value: int | None = None


class ChannelPicker(BaseModel):
    """Канал сервера. Плагин получает ID (int)."""

    type: Literal["channel"] = "channel"
    name: str
    label: str
    value: int | None = None
    kind: Literal["text", "voice", "any"] = "text"


class FileField(BaseModel):
    """Загрузка файла. Плагин получает Attachment (или None, если файл не выбран)."""

    type: Literal["file"] = "file"
    name: str
    label: str
    accept: str = ""          # например "image/*"
    required: bool = False


FormField = Annotated[
    TextField | NumberField | Select | MultiSelect | Toggle | MemberPicker | RolePicker | ChannelPicker | FileField,
    Field(discriminator="type"),
]


class Form(BaseModel):
    """Форма: при отправке плагин получает значения полей.

    Числа — float, переключатели — bool, несколько вариантов (MultiSelect) — list[str],
    выбор участника/роли/канала — int (или None),
    файл — Attachment (или None). Файл едет через NATS: до 700 КБ.
    """

    type: Literal["form"] = "form"
    action: str
    fields: list[FormField] = Field(default_factory=list)
    submit: str = "Сохранить"


Block = Annotated[
    Text | KeyValue | Image | Media | Link | Button | ItemList | Table | Form,
    Field(discriminator="type"),
]


class PanelPage(BaseModel):
    blocks: list[Block] = Field(default_factory=list)
    # Если задано — панель сама обновляет страницу раз в N секунд
    refresh_seconds: int | None = None


# ============================================================
# ЗАПРОСЫ
# ============================================================

class PanelActor(BaseModel):
    """Кто из администраторов открыл страницу или нажал кнопку."""

    id: int
    name: str


class PanelContext(BaseModel):
    guild_id: int
    user: PanelActor


class PageRequest(PanelContext):
    page: str


class ActionRequest(PanelContext):
    page: str
    action: str
    values: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    # Загруженные файлы (FileField); плагин получает их в values под тем же именем
    files: dict[str, Attachment] = Field(default_factory=dict)
