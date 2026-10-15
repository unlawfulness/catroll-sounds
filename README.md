# Catroll Sounds

Открытая библиотека звуков для мастеров D&D — вкладка **«Общие треки»** в [Catroll Player](https://github.com/unlawfulness/catroll-player-releases):
шум таверны, дождь и гром, пещера, лес, костёр, битва, город, существа, магия.

**Только CC0 / общественное достояние.** Каждый звук можно использовать где угодно — на играх,
стримах, в видео и коммерческих проектах — без разрешения и без указания автора.
Авторы и оригиналы перечислены в [LICENSES/ATTRIBUTION.md](LICENSES/ATTRIBUTION.md).

## Как это устроено

| Что | Где |
|---|---|
| Каталог (название ru/en, категория, теги, длительность, размер, формат, loop, автор, ссылка, лицензия) | [`catalog.json`](catalog.json) в ветке `main` |
| Сами файлы (Ogg Vorbis) | assets релиза [`library-v1`](https://github.com/unlawfulness/catroll-sounds/releases/tag/library-v1) |
| Что брать и как называть | [`sources.json`](sources.json) |
| Сборка каталога и скачивание файлов | [`tools/build_catalog.py`](tools/build_catalog.py) |

Приложение скачивает `catalog.json` по адресу
`https://raw.githubusercontent.com/unlawfulness/catroll-sounds/main/catalog.json`, хранит его копию
для работы без сети и по кнопке «Скачать» кладёт файл в папку данных пользователя (рядом с `parties.json`).

### Формат записи

```json
{
  "id": "tavern-ambience",
  "name": { "ru": "Таверна: гомон и смех", "en": "Tavern chatter and laughter" },
  "category": "tavern",
  "tags": ["inn", "crowd", "таверна"],
  "duration": 37.5,
  "size": 905123,
  "format": "ogg",
  "loop": false,
  "file": "tavern-ambience.ogg",
  "license": "CC0-1.0",
  "source": { "site": "Freesound", "author": "ivolipa", "title": "…", "url": "https://freesound.org/s/326313/" }
}
```

- `file` — имя asset'а в релизе; полная ссылка = `assetsBaseUrl` + `file` (или явное поле `url`).
- `loop: true` — звук зациклен без щелчка на стыке.
- Приложение принимает только `CC0-1.0` / `Public Domain`: записи с другой лицензией игнорируются.

## Добавить звуки

1. Найдите звук с лицензией **CC0** (например, на Freesound с фильтром «Creative Commons 0»).
   Звуки CC-BY, CC-BY-NC, «royalty free» и с неясной лицензией **не принимаются**.
2. Добавьте запись в `sources.json` (id латиницей через дефис, название на двух языках, категория, теги).
3. `python tools/build_catalog.py` — скрипт проверит лицензию на странице источника, скачает файл
   в `release/<тег>/` и пересоберёт `catalog.json` и `LICENSES/ATTRIBUTION.md`.
4. Новые файлы — в assets релиза (новый тег, например `library-v2`, и `assetsBaseUrl` в `sources.json`),
   `catalog.json` — коммитом в `main`.

---

# Catroll Sounds (English)

An open sound library for D&D game masters — the **Shared tracks** tab of Catroll Player. Every sound
is **CC0 / public domain**: use it anywhere, no attribution required (authors are credited in
[LICENSES/ATTRIBUTION.md](LICENSES/ATTRIBUTION.md)). `catalog.json` on `main` describes the sounds;
the audio files are assets of the `library-v1` release. To add sounds, edit `sources.json` and run
`python tools/build_catalog.py` — it verifies the CC0 license on the source page, downloads the files
into `release/<tag>/` and regenerates the catalog and attribution list.

The repository itself (catalog, scripts, docs) is released under [CC0 1.0](LICENSE).
