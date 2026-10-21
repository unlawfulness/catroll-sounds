"""
Сборка каталога «Общих треков» Catroll Player.

Читает sources.json (что взять и как назвать), для каждой записи:
  1. открывает страницу источника и проверяет, что лицензия — CC0 1.0
     (записи с любой другой лицензией пропускаются с ошибкой — в каталог они не попадут):
       • Freesound ("freesound": id) — звуки и эмбиент, файл — HQ-превью Ogg Vorbis (полная длина);
       • OpenGameArt ("oga": "/content/…", "fileUrl") — музыка, оригинальный файл .ogg или .mp3;
  2. скачивает файл в release/<release>/<id>.<ext> (файлы прошлых выпусков берутся из release/*/);
  3. записывает в catalog.json название, категорию, теги, длительность, размер, автора, ссылку и лицензию;
  4. обновляет LICENSES/ATTRIBUTION.md и tools/downloads.json — откуда и с какой SHA-256 взят каждый файл
     (по нему GitHub Actions собирает релиз — workflow .github/workflows/library-release.yml).

Запуск:  python tools/build_catalog.py           (уже скачанные файлы не перекачиваются)
Нужен mutagen (длительность музыки): pip install mutagen
Сайты ограничивают частоту запросов — между страницами пауза в несколько секунд.
"""
import hashlib
import html
import json
import re
import shutil
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "CatrollPlayer catalog builder (+https://github.com/unlawfulness/catroll-sounds)"}
CC0 = "creativecommons.org/publicdomain/zero/1.0"
PAGE_DELAY = 4


def fetch(url: str, binary: bool = False):
    for attempt in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                data = r.read()
                return data if binary else data.decode("utf-8")
        except Exception as e:  # 429 Too Many Requests и сетевые сбои — ждём и повторяем
            print(f"  повтор через 45 с ({e})", flush=True)
            time.sleep(45)
    raise RuntimeError(f"не удалось загрузить {url}")


def page_info(freesound_id: int) -> dict:
    page = fetch(f"https://freesound.org/s/{freesound_id}/")
    licenses = set(re.findall(r'href="https?://(creativecommons\.org/[^"]+)"', page))
    player = re.search(r'data-sound-id="%d"(.*?)>' % freesound_id, page, re.S)
    attrs = dict(re.findall(r'data-([a-z-]+)="([^"]*)"', player.group(1))) if player else {}
    title = re.search(r"<title>Freesound - (.*?) by ([^<]*?)</title>", page, re.S)
    return {
        "cc0": any(l.rstrip("/").endswith("publicdomain/zero/1.0") for l in licenses),
        "licenses": sorted(licenses),
        "author": html.unescape(attrs.get("username") or (title.group(2).strip() if title else "")),
        "title": html.unescape(title.group(1).strip()) if title else "",
        "duration": float(attrs.get("duration", "0") or 0),
        "ogg": attrs.get("ogg", "").replace("-lq.ogg", "-hq.ogg"),
    }


def oga_info(href: str) -> dict:
    """Страница OpenGameArt: лицензия CC0 среди лицензий работы, автор и название."""
    page = fetch("https://opengameart.org" + href)
    lic = page.split("field-name-field-art-licenses", 1)[-1].split("field-name-collect", 1)[0]
    title = re.search(r"<title>(.*?) \| OpenGameArt\.org</title>", page, re.S)
    author = re.search(r'field-name-author-submitter.*?<a href="/users/[^"]+">([^<]+)</a>', page, re.S)
    return {
        "cc0": "publicdomain/zero/1.0" in lic,
        "licenses": sorted(set(re.findall(r"href='?\"?https?://(creativecommons\.org/[^'\"]+)", lic))),
        "author": html.unescape(author.group(1).strip()) if author else "",
        "title": html.unescape(title.group(1).strip()) if title else href,
    }


def audio_duration(path: Path) -> float:
    try:
        import mutagen
        info = mutagen.File(str(path))
        return float(info.info.length) if info is not None else 0.0
    except ImportError:
        print("  (нет mutagen — длительность музыки не посчитана: pip install mutagen)", flush=True)
        return 0.0


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reuse_previous(file_name: str, out_dir: Path) -> bool:
    """Файл уже скачан для прошлого выпуска — копируем, а не качаем заново."""
    for other in sorted((ROOT / "release").glob("*/" + file_name)):
        if other.parent != out_dir:
            shutil.copy2(other, out_dir / file_name)
            return True
    return False


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sources = json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))
    release = sources["release"]
    out_dir = ROOT / "release" / release
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_file = ROOT / "tools" / ".pages.json"  # кэш разобранных страниц (не в git)
    cache = json.loads(cache_file.read_text(encoding="utf-8")) if cache_file.exists() else {}

    sounds, errors, downloads = [], [], []
    for src in sources["sounds"]:
        oga = src.get("oga")
        key = f"oga:{oga}" if oga else str(src["freesound"])
        print(f"{src['id']}  ({key})", flush=True)
        if key not in cache:
            time.sleep(PAGE_DELAY)
            cache[key] = oga_info(oga) if oga else page_info(src["freesound"])
            cache_file.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
        info = cache[key]

        if not info["cc0"]:
            errors.append(f"{src['id']}: лицензия не CC0 ({info['licenses']}) — пропущен")
            continue
        file_url = src["fileUrl"] if oga else info["ogg"]
        if not file_url:
            errors.append(f"{src['id']}: не найден файл — пропущен")
            continue

        ext = Path(urllib.parse.urlparse(file_url).path).suffix.lower().lstrip(".") or "ogg"
        file_name = f"{src['id']}.{ext}"
        target = out_dir / file_name
        if not target.exists() and not reuse_previous(file_name, out_dir):
            target.write_bytes(fetch(file_url, binary=True))

        duration = audio_duration(target) if oga else info["duration"]
        downloads.append({"file": file_name, "url": file_url, "size": target.stat().st_size, "sha256": sha256(target)})
        sounds.append({
            "id": src["id"],
            "name": src["name"],
            "category": src["category"],
            "tags": src.get("tags", []),
            "duration": round(duration, 1),
            "size": target.stat().st_size,
            "format": ext,
            "loop": bool(src.get("loop", False)),
            "file": file_name,
            "license": "CC0-1.0",
            "source": {
                "site": "OpenGameArt" if oga else "Freesound",
                "author": info["author"],
                "title": info["title"],
                "url": f"https://opengameart.org{oga}" if oga else f"https://freesound.org/s/{src['freesound']}/",
            },
        })

    catalog = {
        "schema": 1,
        "release": release,
        "assetsBaseUrl": sources["assetsBaseUrl"],
        "categories": sources["categories"],
        "sounds": sounds,
    }
    (ROOT / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_attribution(sounds)
    (ROOT / "tools" / "downloads.json").write_text(
        json.dumps({"release": release, "files": downloads}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    total = sum(s["size"] for s in sounds)
    print(f"\nВ каталоге: {len(sounds)} звуков, {total / 1024 / 1024:.1f} МБ → {out_dir}")
    for e in errors:
        print("ОШИБКА:", e)
    return 1 if errors else 0


def write_attribution(sounds: list) -> None:
    lines = [
        "# Источники и лицензии / Sources and licenses",
        "",
        "Все звуки каталога распространяются по лицензии **CC0 1.0 Universal** (общественное достояние):",
        "их можно использовать, изменять и распространять без разрешения и без указания автора,",
        "в том числе в коммерческих целях. Авторов перечисляем из уважения к их работе.",
        "",
        "All sounds are released under **CC0 1.0 Universal** (public domain dedication). Attribution",
        "is not required; the authors are credited below out of courtesy.",
        "",
        "Звуки — HQ-превью Freesound (Ogg Vorbis) исходных записей; музыка — оригинальные файлы с OpenGameArt.",
        "Sounds are Freesound HQ previews (Ogg Vorbis); music files are the originals from OpenGameArt.",
        "",
        "| id | Название / Name | Автор / Author | Оригинал / Original | Лицензия |",
        "|---|---|---|---|---|",
    ]
    for s in sounds:
        src = s["source"]
        title = src["title"].replace("|", "\\|")
        lines.append(f"| `{s['id']}` | {s['name']['ru']} / {s['name']['en']} | {src['author']} "
                     f"| [{title}]({src['url']}) | [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) |")
    (ROOT / "LICENSES").mkdir(exist_ok=True)
    (ROOT / "LICENSES" / "ATTRIBUTION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
