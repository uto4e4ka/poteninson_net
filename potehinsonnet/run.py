"""Запуск плагина по манифесту: python -m potehinsonnet.run [папка плагина]

Одинаково и у разработчика, и у хоста: читает plugin.toml, проверяет совместимость,
вызывает функцию из runtime.entry с PluginContext и запускает плагин, который она вернула.
"""
import asyncio
import importlib
import inspect
import logging
import sys
from pathlib import Path

from potehinsonnet.context import PluginContext
from potehinsonnet.manifest import ManifestError
from potehinsonnet.plugin import Plugin

log = logging.getLogger("potehinsonnet.run")


async def build(ctx: PluginContext) -> Plugin:
    """Импортировать entry и собрать плагин. Функция может быть и обычной, и async."""
    module_name, _, func_name = ctx.manifest.runtime.entry.partition(":")
    if str(ctx.root) not in sys.path:
        sys.path.insert(0, str(ctx.root))  # пакет плагина лежит в его корне
    try:
        factory = getattr(importlib.import_module(module_name), func_name)
    except (ImportError, AttributeError) as e:
        raise ManifestError(f"{ctx.manifest.name}: не найден {ctx.manifest.runtime.entry} — {e}") from e
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
