"""
Перенести подобранное (tools/candidates.json) в sources.json для нового выпуска.

  python tools/merge_candidates.py library-v2 tools/music-names.json

Звуки берут название и теги из tools/wishlist.json; музыка — из файла с названиями
(id → ru/en/tags, ключ — адрес страницы OpenGameArt). Прежние записи остаются как есть.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    release = sys.argv[1]
    music_names = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")) if len(sys.argv) > 2 else {}
    sources = json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))
    wishlist = json.loads((ROOT / "tools" / "wishlist.json").read_text(encoding="utf-8"))
    cand = json.loads((ROOT / "tools" / "candidates.json").read_text(encoding="utf-8"))

    sources["release"] = release
    sources["assetsBaseUrl"] = f"https://github.com/unlawfulness/catroll-sounds/releases/download/{release}/"
    sources["categories"].update(wishlist.get("newCategories", {}))
    have = {s["id"] for s in sources["sounds"]}

    added = 0
    for wish in wishlist["sounds"]:
        found = cand["sounds"].get(wish["id"])
        if found is None or wish["id"] in have:
            continue
        sources["sounds"].append({
            "id": wish["id"],
            "freesound": found["freesound"],
            "name": {"ru": wish["ru"], "en": wish["en"]},
            "category": wish["category"],
            "tags": wish.get("tags", []),
        })
        added += 1

    for m in cand["music"]:
        names = music_names.get(m["oga"])
        if names is None:
            print(f"нет названия для {m['oga']} — пропущен")
            continue
        mid = names.get("id") or "music-" + re.sub(r"[^a-z0-9]+", "-", m["oga"].rsplit("/", 1)[-1].lower()).strip("-")
        if mid in have:
            continue
        sources["sounds"].append({
            "id": mid,
            "oga": m["oga"],
            "fileUrl": m["fileUrl"],
            "name": {"ru": names["ru"], "en": names["en"]},
            "category": "music",
            "tags": names.get("tags", []),
        })
        have.add(mid)
        added += 1

    (ROOT / "sources.json").write_text(json.dumps(sources, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Добавлено: {added}, всего записей: {len(sources['sounds'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
