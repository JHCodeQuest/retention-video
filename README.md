# retention-video

Turns an auto-generated client retention PDF into a narrated walkthrough
video: an ElevenLabs voice reads a scripted summary while the camera zooms to
and highlights each row of the report it's talking about, with burned-in
captions.

The PDF comes from [slack-file-bot](https://github.com/JHCodeQuest/slack-file-bot)'s
`/client-report` pipeline, imported directly, so the video always matches the
report the bot posts.

```
clients (mock JSON) ─► retention_analysis + pdf_report (slack-file-bot) ─► PDF
                                         │
                                         ▼
                         script.py + script_template.json ─► segments (text + focus)
                                         │
                   ┌─────────────────────┴─────────────────────┐
                   ▼                                           ▼
     frames.py: render page, find focus text,        tts.py: ElevenLabs TTS
     zoom + highlight row, burn caption              (cached; silent offline)
                   └─────────────────────┬─────────────────────┘
                                         ▼
                        video.py: ffmpeg per-segment clips ─► concat ─► MP4
```

## Usage

```bash
pip install -r requirements.txt   # also needs ffmpeg + ffprobe on PATH
cp .env.example .env               # add ELEVENLABS_API_KEY for a real voice
python main.py                     # -> output/<timestamp>/report.mp4
```

- `python main.py --script-only` prints the narration and what each line focuses on
- `python main.py --clients my_clients.json` uses your own (fictional) client list
- `python main.py --template my_script.json` swaps the narration wording

Without an API key the video still renders, with silent audio timed to reading
speed, so you can iterate on visuals and wording for free. Generated clips are
cached in `.tts-cache/` by voice + model + text, so re-renders only pay for
lines that changed.

## Data

All data is fictional: slack-file-bot's `MOCK_CLIENTS` by default. The bot's
live outreach-tracker feed is never called from this project.

## How it works

- **Script:** `script.py` walks the analysis results (top retained client,
  the rest of the Retain group, each Review, each Drop) and fills the
  wording from `script_template.json`. Each segment records the text on the
  page it refers to.
- **Frames:** `frames.py` renders the PDF with pdfium, uses the PDF's text
  layer to locate that text (no hard-coded coordinates, so layout changes in
  the report don't break it), stretches a highlight across the table row, and
  frames a 16:9 shot around it.
- **Voice:** `tts.py` calls `POST /v1/text-to-speech/{voice_id}`.
- **Video:** `video.py` holds each frame for its narration plus a short
  pause, then concatenates the clips losslessly.

## Tests

```bash
python -m pytest tests -v
```

Covers script generation, that every focus target is locatable in the PDF, an
end-to-end offline render (checking the video's duration against the audio),
and the ElevenLabs request shape + cache (mocked, no network).
