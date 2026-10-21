"""
Скачать файлы выпуска по tools/downloads.json и сверить SHA-256 (для GitHub Actions).

Файлы берутся по тем же ссылкам, по которым их скачал и проверил build_catalog.py; если хоть один
не совпал по контрольной сумме — выпуск не создаётся.
Запуск: python tools/fetch_release.py <папка>
"""
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "CatrollPlayer catalog builder (+https://github.com/unlawfulness/catroll-sounds)"}


def fetch(url: str) -> bytes:
    for attempt in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return r.read()
        except Exception as e:
            print(f"  повтор через 30 с ({e})", flush=True)
            time.sleep(30)
    raise RuntimeError(f"не удалось загрузить {url}")


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "dist")
    out.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ROOT / "tools" / "downloads.json").read_text(encoding="utf-8"))
    bad = []
    for f in manifest["files"]:
        data = fetch(f["url"])
        digest = hashlib.sha256(data).hexdigest()
        if digest != f["sha256"]:
            bad.append(f"{f['file']}: SHA-256 {digest} вместо {f['sha256']}")
            continue
        (out / f["file"]).write_bytes(data)
        print(f"{f['file']}  {len(data) / 1048576:.1f} МБ", flush=True)
        time.sleep(1)
    for b in bad:
        print("ОШИБКА:", b)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
