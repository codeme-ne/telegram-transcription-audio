# Telegram Voice Transcriber

Exportiert Sprachnachrichten (und optional Text) aus einem Telegram-Chat, transkribiert sie lokal mit Whisper und schreibt die Ergebnisse als Markdown-Datei – vollständig offline, ohne Telegram Premium.

## Funktionsüberblick

- **Ziel-Chat**: ein bestimmter Chat (z. B. „Alice Example“) für ein festgelegtes Jahr (Standard: 2025).
- **Inhalte**: Sprachnachrichten (`voice`, `audio`, `video_note`) und Textnachrichten.
- **Filter**: Nur Nachrichten des Gegenübers; eigene Beiträge optional (`--include-self`).
- **Dry-Run**: `--dry-run` zeigt eine Übersicht (Zählung + Beispiele), ohne Downloads.
- **Resume**: Wiederaufnahme über `state.json`, um bereits verarbeitete Nachrichten zu überspringen.
- **Ausgabe**: `alice-example-2025.md` im Datenverzeichnis, gruppiert nach Datum, mit Uhrzeit, Absender, Text/Transkript und Message-ID.

## Voraussetzungen

- Kubuntu 25.04 (oder vergleichbar).
- Python ≥ 3.10 (venv empfohlen).
- `ffmpeg` installiert (`sudo apt install ffmpeg`).
- Telegram API Credentials (my.telegram.org → „API development tools“ → `api_id`, `api_hash`).
- Optionale GPU (verbessert Geschwindigkeit); CPU funktioniert mit `model small`.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e '.[dev]'
```

## Telegram-Login (erstmalig)

Beim ersten Tool-Start wird eine Session-Datei angelegt (Standard: `.data/telegram.session`). Der Ablauf:

1. Telefon­nummer (inkl. +Ländercode) eingeben.
2. Telegram-Code bestätigen.
3. Falls 2FA aktiv, Passwort eingeben.

Die Session bleibt lokal gespeichert.

## Beispiel-Workflow

### 1. Dry-Run (Überblick, keine Downloads)

```bash
TG_API_ID=123456 TG_API_HASH=abcdef123456 \
tg-transcribe "Alice Example" \
  --year 2025 \
  --dry-run \
  --data-dir ~/.cache/telegram-transcriber
```

Ausgabe: Zählung nach Typ sowie Beispielnachrichten.

### 2. Vollständiger Lauf

```bash
TG_API_ID=123456 TG_API_HASH=abcdef123456 \
tg-transcribe "Alice Example" \
  --year 2025 \
  --data-dir ~/.cache/telegram-transcriber \
  --timezone Europe/Vienna \
  --model small
```

- Sprachnachrichten werden in `cache/` gespeichert.
- Transkripte werden erzeugt (`models/` enthält das Whisper-Modell).
- Markdown: `output/alice-example-2025.md`.

### Wichtige Optionen

| Option | Beschreibung |
| --- | --- |
| `--include-self` | Eigene Nachrichten/Sprachnachrichten aufnehmen. |
| `--type voice --type text` | Steuert zulässige Typen (voice, audio, video_note, text). |
| `--timezone Europe/Vienna` | Zeitzone für Datum/Uhrzeit in Markdown. |
| `--session <pfad>` | Alternativer Pfad zur `.session` Datei. |
| `--language de` | Whisper-Sprache festlegen (z. B. `en`, `de`). |
| `--model small` | Whisper-Modellgröße (`tiny`, `base`, `small`, `medium`, …). |

## Web UI

```bash
# Start the web interface
streamlit run app.py

# Or using the installed command
tg-web
```

Open http://localhost:8501 in your browser.

## Tests & Entwicklung

- **Alle Tests**: `pytest`
- Ideologie: TDD – Tests zuerst, keine Anpassung erfolgreicher Tests.
- Wichtige Module: `filters`, `download`, `transcribe`, `pipeline`, `tg_client`, `cli`.

## Verzeichnisstruktur (Standard)

```
.data/
  alice-example/
    2025/
      cache/          # heruntergeladene Mediendateien (Jahres- & Monats-Unterordner)
      models/         # Cache für Whisper-Modelle
      output/         # Markdown-Ergebnis
      state/state.json# Resume-Information
```

## Nächste Schritte (TODO)

- **Telegram API Zugang**: `api_id` und `api_hash` von my.telegram.org besorgen.
- **Verifikation**: Mit echten Daten `--dry-run` ausführen, anschließend vollständigen Lauf.
- **TDD beibehalten**: Bei künftigen Erweiterungen neue Tests vor Implementierung hinzufügen (z. B. zusätzliche Filter).

## Hinweise & Grenzen

- Secret Chats sind nicht exportierbar (Telegram-Beschränkung).
- Gelöschte oder abgelaufene Medien lassen sich nicht mehr abrufen.
- Daten bleiben lokal – kein Upload zu Drittanbietern.
- Whisper-Ladezeit: erstes Modell-Laden (CPU) kann >1 Minute dauern, danach Caching.
