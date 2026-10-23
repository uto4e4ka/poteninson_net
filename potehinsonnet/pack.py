"""Собрать zip плагина для установки через панель: код и данные (data/), без окружений, секретов и мусора.

    python -m potehinsonnet.pack                          # из папки плагина → dist/<имя>-<версия>.zip
    python -m potehinsonnet.pack --bump patch --no-data   # поднять версию и собрать только код
    python -m potehinsonnet.pack ../my_plugin --out .     # другую папку, архив — в текущую

--bump patch|minor|major поднимает версию в plugin.toml (и в pyproject.toml, если там такая же) до сборки.
Данные в архиве — стартовые: бот положит их, только если у плагина данных ещё нет (первая установка);
при обновлении серверные данные не трогаются, поэтому для обновлений хватит --no-data.
"""
import argparse
import re
import sys
import tomllib
import zipfile
from pathlib import Path

SKIP_DIRS = {".venv", "venv", "__pycache__", ".git", ".idea", ".pytest_cache", "node_modules", "backups", "tests",
             "dist"}
SKIP_SUFFIXES = {".pyc", ".log", ".tmp"}
SKIP_NAMES = {".env", "settings.json", "make_zip.py"}   # секреты, настройки владельца и сам скрипт сборки
VERSION_LINE = re.compile(r'^(version\s*=\s*")(\d+)\.(\d+)\.(\d+)(")', re.M)


def bump(version: str, part: str) -> str:
    major, minor, patch = (int(x) for x in version.split("."))
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def set_version(file: Path, old: str, new: str) -> bool:
    """Поменять первую строку version = "…" в файле, если там old. Остальной текст не трогаем."""
    if not file.exists():
        return False
    text = file.read_text(encoding="utf-8")
    match = VERSION_LINE.search(text)
    if not match or ".".join(match.groups()[1:4]) != old:
        return False
    file.write_text(text[:match.start()] + f"{match.group(1)}{new}{match.group(5)}" + text[match.end():],
                    encoding="utf-8")
    return True


def skipped(relative: Path, with_data: bool) -> bool:
    parts = relative.parts
    if any(part in SKIP_DIRS for part in parts) or not with_data and parts[0] == "data":
        return True
    return relative.name in SKIP_NAMES or relative.suffix in SKIP_SUFFIXES or ".broken-" in relative.name


def pack(folder: Path, out: Path | None = None, bump_part: str | None = None, with_data: bool = True) -> Path:
    """Собрать архив; вернуть путь к нему. out — папка для архива (по умолчанию <плагин>/dist)."""
    root = Path(folder).resolve()
    manifest = root / "plugin.toml"
    if not manifest.exists():
        raise FileNotFoundError(f"В {root} нет plugin.toml")
    version = tomllib.loads(manifest.read_text(encoding="utf-8"))["plugin"]["version"]
    if bump_part:
        new = bump(version, bump_part)
        set_version(manifest, version, new)
        also = " и pyproject.toml" if set_version(root / "pyproject.toml", version, new) else ""
        print(f"Версия {version} → {new} (plugin.toml{also})")
        version = new

    out = Path(out) if out is not None else root / "dist"
    out.mkdir(parents=True, exist_ok=True)
    target = out.resolve() / f"{root.name}-{version}.zip"
    count = 0
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root)
            if path.is_dir() or path == target or skipped(relative, with_data):
                continue
            zf.write(path, relative.as_posix())
            count += 1
    print(f"{target}: {count} файлов, {target.stat().st_size // 1024} КБ, {'с data/' if with_data else 'без data/'}")
    return target


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m potehinsonnet.pack", description="Собрать zip плагина для панели")
    parser.add_argument("folder", nargs="?", default=".", help="папка плагина (где plugin.toml)")
    parser.add_argument("--bump", choices=["patch", "minor", "major"], help="поднять версию перед сборкой")
    parser.add_argument("--no-data", action="store_true", help="не класть data/ (для обновлений)")
    parser.add_argument("--out", help="куда положить архив (по умолчанию <плагин>/dist)")
    args = parser.parse_args(argv)
    try:
        pack(Path(args.folder), Path(args.out) if args.out else None, args.bump, with_data=not args.no_data)
    except FileNotFoundError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
