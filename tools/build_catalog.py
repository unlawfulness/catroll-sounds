"""
Сборка каталога «Общих треков» Catroll Player.

Читает sources.json (что взять и как назвать), для каждого звука:
  1. открывает страницу на Freesound и проверяет, что лицензия — CC0 1.0
     (звуки с любой другой лицензией пропускаются с ошибкой — в каталог они не попадут);
  2. скачивает HQ-превью в формате Ogg Vorbis (полная длина, ~192 кбит/с) в release/<release>/<id>.ogg;
  3. записывает в catalog.json название, категорию, теги, длительность, размер, автора, ссылку и лицензию;
  4. обновляет LICENSES/ATTRIBUTION.md.

Запуск:  python tools/build_catalog.py           (уже скачанные файлы не перекачиваются)
Файлы из release/<release>/ загружаются как assets релиза с тем же тегом на GitHub.
Freesound ограничивает частоту запросов — между страницами пауза в несколько секунд.
"""
import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "CatrollPlayer catalog builder (+https://github.com/unlawfulness/catroll-sounds)"}
CC0 = "creativecommons.org/publicdomain/zero/1.0"
PAGE_DELAY = 8


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


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sources = json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))
    release = sources["release"]
    out_dir = ROOT / "release" / release
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_file = ROOT / "tools" / ".pages.json"  # кэш разобранных страниц (не в git)
    cache = json.loads(cache_file.read_text(encoding="utf-8")) if cache_file.exists() else {}

    sounds, errors = [], []
    for src in sources["sounds"]:
        fid = src["freesound"]
        key = str(fid)
        print(f"{src['id']}  (freesound {fid})", flush=True)
        if key not in cache:
            time.sleep(PAGE_DELAY)
            cache[key] = page_info(fid)
            cache_file.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
        info = cache[key]

        if not info["cc0"]:
            errors.append(f"{src['id']}: лицензия не CC0 ({info['licenses']}) — пропущен")
            continue
        if not info["ogg"]:
            errors.append(f"{src['id']}: не найдено превью — пропущен")
            continue

        file_name = f"{src['id']}.ogg"
        target = out_dir / file_name
        if not target.exists():
            target.write_bytes(fetch(info["ogg"], binary=True))

        sounds.append({
            "id": src["id"],
            "name": src["name"],
            "category": src["category"],
            "tags": src.get("tags", []),
            "duration": round(info["duration"], 1),
            "size": target.stat().st_size,
            "format": "ogg",
            "loop": bool(src.get("loop", False)),
            "file": file_name,
            "license": "CC0-1.0",
            "source": {
                "site": "Freesound",
                "author": info["author"],
                "title": info["title"],
                "url": f"https://freesound.org/s/{fid}/",
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
        "Файлы — HQ-превью Freesound (Ogg Vorbis) исходных записей. / Files are Freesound HQ previews (Ogg Vorbis).",
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
