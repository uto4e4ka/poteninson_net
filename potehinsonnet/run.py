"""Запуск плагина по манифесту: python -m potehinsonnet.run [папка плагина]

Одинаково и у разработчика, и у хоста: читает plugin.toml, проверяет совместимость,
вызывает функцию из runtime.entry с PluginContext и запускает плагин, который она вернула.
"""
import asyncio
import importlib
import inspect
import logging
import sys
import traceback
from pathlib import Path

from potehinsonnet.context import PluginContext
from potehinsonnet.manifest import ManifestError
from potehinsonnet.plugin import Plugin

log = logging.getLogger("potehinsonnet.run")


def where(error: BaseException, root: Path) -> str:
    """Где в коде плагина случилась ошибка: последняя строка из его папки (а не из библиотек, куда она ушла)."""
    frames = traceback.extract_tb(error.__traceback__)
    own = [f for f in frames if Path(f.filename).resolve().is_relative_to(root)]
    frame = (own or [f for f in frames if "importlib" not in f.filename] or [None])[-1]
    if frame is None:
        return "место неизвестно"
    return f"{Path(frame.filename).resolve().relative_to(root) if own else frame.filename}, строка {frame.lineno}: {frame.line}"


async def build(ctx: PluginContext) -> Plugin:
    """Импортировать entry и собрать плагин. Функция может быть и обычной, и async."""
    module_name, _, func_name = ctx.manifest.runtime.entry.partition(":")
    if str(ctx.root) not in sys.path:
        sys.path.insert(0, str(ctx.root))  # пакет плагина лежит в его корне
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as e:
        if e.name and module_name.startswith(e.name):   # нет самого модуля из entry (или его пакета)
            raise ManifestError(f"{ctx.manifest.name}: не найден модуль {module_name} из runtime.entry") from e
        # Модуль есть, но внутри него не нашлась зависимость — показываем, где именно
        raise ManifestError(f"{ctx.manifest.name}: при загрузке {module_name} не нашёлся модуль "
                            f"«{e.name}» — {where(e, ctx.root)}") from e
    except Exception as e:
        raise ManifestError(f"{ctx.manifest.name}: ошибка при загрузке {module_name}: "
                            f"{type(e).__name__}: {e} — {where(e, ctx.root)}") from e
    factory = getattr(module, func_name, None)
    if factory is None:
        raise ManifestError(f"{ctx.manifest.name}: в {module_name} нет функции {func_name} из runtime.entry")
    plugin = factory(ctx)
    if inspect.isawaitable(plugin):
        plugin = await plugin
    if not isinstance(plugin, Plugin):
        raise ManifestError(f"{ctx.manifest.runtime.entry} должна вернуть Plugin, а вернула {type(plugin).__name__}")
    return plugin


async def run(root: str | Path = ".") -> None:
    ctx = PluginContext.load(root)
    ctx.manifest.check_compatible()
    plugin = await build(ctx)
    log.info("Запуск %s %s, данные: %s", ctx.manifest.name, ctx.manifest.plugin.version, ctx.data_dir)
    await plugin.serve()


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        asyncio.run(run(argv[0] if argv else "."))
    except ManifestError as e:
        log.error("%s", e)
        return 2
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
