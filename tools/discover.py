"""
Подбор кандидатов для каталога по tools/wishlist.json.

  Звуки — поиск Freesound с фильтром «Creative Commons 0», по убыванию скачиваний: берётся самый
  скачиваемый звук с подходящей длительностью и рейтингом, которого ещё нет в каталоге.
  Музыка — поиск OpenGameArt (тип «Music», лицензия CC0): страница проверяется на CC0,
  берётся файл .ogg (или .mp3) не больше 15 МБ.

Результат — tools/candidates.json. Лицензию каждого звука ещё раз проверяет build_catalog.py.
Запуск: python tools/discover.py
"""
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "CatrollPlayer catalog builder (+https://github.com/unlawfulness/catroll-sounds)"}
MAX_MUSIC_BYTES = 15 * 1024 * 1024
DELAY = 8
# Слова из названий, которые выдают современный или неподходящий звук (машины, город, sci-fi, речь)
SKIP_WORDS = re.compile(r"\b(voice|speech|talking|vocal|phone|cars?|traffic|synth|electronic|8-?bit|chiptune|city|street|"
                        r"london|brazil|paris|tokyo|subway|train|bus|beam|laser|sci-?fi|space ?ship|robot|guns?|rifle|"
                        r"pistol|siren|snowshoe\w*|engine|motor\w*|airplane|helicopter)\b", re.I)


def fetch(url: str) -> str:
    for attempt in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            print(f"  повтор через 30 с ({e})", flush=True)
            time.sleep(30)
    raise RuntimeError(f"не удалось загрузить {url}")


def freesound_search(query: str) -> list:
    url = ("https://freesound.org/search/?" + urllib.parse.urlencode(
        {"q": query, "f": 'license:"Creative Commons 0"', "s": "num_downloads desc"}))
    page = fetch(url)
    results = []
    for block in re.split(r'<div class="bw-search__result"', page)[1:]:
        attrs = dict(re.findall(r'data-([a-z-]+)="([^"]*)"', block[:3000]))
        rating = re.search(r'aria-label="Average rating of ([0-9.]+)"', block)
        if "sound-id" not in attrs:
            continue
        results.append({
            "freesound": int(attrs["sound-id"]),
            "title": html.unescape(attrs.get("title", "")),
            "author": html.unescape(attrs.get("username", "")),
            "duration": float(attrs.get("duration") or 0),
            "downloads": int(attrs.get("num-downloads") or 0),
            "rating": float(rating.group(1)) if rating else None,
        })
    return results


def score(r: dict) -> float:
    """Популярность с поправкой на оценку: много скачиваний и высокий рейтинг — лучше."""
    return r["downloads"] * ((r["rating"] or 3.5) / 5.0)


def pick_sound(wish: dict, used: set) -> dict | None:
    """Лучший по скачиваниям и рейтингу звук с подходящей длительностью. Пустая выдача — запрос короче."""
    words = wish["q"].split()
    while words:
        results = freesound_search(" ".join(words))
        ok = [r for r in results
              if r["freesound"] not in used
              and r["freesound"] not in wish.get("exclude", [])
              and not SKIP_WORDS.search(r["title"])
              and (r["rating"] is None or r["rating"] >= 3.5)
              and r["downloads"] >= 20]
        # Сначала строго по длительности, иначе — до двух раз длиннее (короткий эффект можно обрезать на лету)
        for limit in (wish["max"], wish["max"] * 2):
            fit = [r for r in ok if wish["min"] <= r["duration"] <= limit]
            if fit:
                return max(fit, key=score)
        if len(words) == 1:
            break
        words = words[:-1]
        time.sleep(DELAY)
    return None


def oga_search(query: str) -> list:
    url = ("https://opengameart.org/art-search-advanced?" + urllib.parse.urlencode(
        {"keys": query, "field_art_type_tid[]": "12", "field_art_licenses_tid[]": "4",
         "sort_by": "count", "sort_order": "DESC"}))
    page = fetch(url)
    seen = []
    for href in re.findall(r'href="(/content/[^"]+)"', page):
        slug = href.lower()
        if href in seen or slug in ("/content/faq",) or any(w in slug for w in ("challenge", "chiptune", "8-bit", "8bit")):
            continue
        seen.append(href)
    return seen


def oga_page(href: str) -> dict | None:
    page = fetch("https://opengameart.org" + href)
    lic = page.split("field-name-field-art-licenses", 1)[-1].split("field-name-collect", 1)[0]
    if "publicdomain/zero/1.0" not in lic:
        return None
    files_block = page.split("field-name-field-art-files", 1)[-1].split("</ul>", 1)[0]
    files = re.findall(r'<a href="(https://opengameart\.org/sites/default/files/[^"]+)" type="[^"]*?length=(\d+)"', files_block)
    files = [(u, int(n)) for u, n in files if n.isdigit() and int(n) <= MAX_MUSIC_BYTES]
    ogg = [f for f in files if f[0].lower().endswith(".ogg")]
    mp3 = [f for f in files if f[0].lower().endswith(".mp3")]
    pick = (ogg or mp3 or [None])[0]
    if pick is None:
        return None
    title = re.search(r"<title>(.*?) \| OpenGameArt\.org</title>", page, re.S)
    author = re.search(r"field-name-author-submitter.*?<a href=\"/users/[^\"]+\">([^<]+)</a>", page, re.S)
    return {
        "oga": href,
        "title": html.unescape(title.group(1).strip()) if title else href,
        "author": html.unescape(author.group(1).strip()) if author else "",
        "fileUrl": pick[0],
        "size": pick[1],
    }


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    wishlist = json.loads((ROOT / "tools" / "wishlist.json").read_text(encoding="utf-8"))
    sources = json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))
    used = {s["freesound"] for s in sources["sounds"] if "freesound" in s}
    out_file = ROOT / "tools" / "candidates.json"
    out = json.loads(out_file.read_text(encoding="utf-8")) if out_file.exists() else {"sounds": {}, "music": []}

    for wish in wishlist["sounds"]:
        if wish["id"] in out["sounds"]:
            used.add(out["sounds"][wish["id"]]["freesound"])
            continue
        print(f"звук {wish['id']}: «{wish['q']}»", flush=True)
        time.sleep(DELAY)
        found = pick_sound(wish, used)
        if found is None:
            print("  — не нашлось подходящего", flush=True)
            continue
        used.add(found["freesound"])
        out["sounds"][wish["id"]] = found
        print(f"  → {found['freesound']} «{found['title']}» ({found['duration']:.0f} с, ⭳{found['downloads']}, ★{found['rating']})", flush=True)
        out_file.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    taken = {m["oga"] for m in out["music"]}
    for wish in wishlist["music"]:
        have = sum(1 for m in out["music"] if m["query"] == wish["q"])
        if have >= wish["n"]:
            continue
        print(f"музыка «{wish['q']}»", flush=True)
        time.sleep(3)
        for href in oga_search(wish["q"]):
            if have >= wish["n"]:
                break
            if href in taken:
                continue
            time.sleep(3)
            info = oga_page(href)
            taken.add(href)
            if info is None:
                continue
            info["query"] = wish["q"]
            out["music"].append(info)
            have += 1
            print(f"  → {info['title']} — {info['author']} ({info['size'] / 1048576:.1f} МБ)", flush=True)
            out_file.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    out_file.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nЗвуков: {len(out['sounds'])} из {len(wishlist['sounds'])}, музыки: {len(out['music'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
