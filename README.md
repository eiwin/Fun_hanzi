# Fun Hanzi

## Run

1. Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

2. Start the local app:

```bash
python3 -m backend
```

3. Open:

```text
http://127.0.0.1:8000/learn
```

## Main Files

- `backend/` Python API, weekly workflow, scheduler, asset import
- `frontend/` Local web UI
- `data/` Characters, progress, weekly pack, asset manifest, logs

## Pages

- Learner page: `http://127.0.0.1:8000/learn`
- Parent/admin page: `http://127.0.0.1:8000/admin`

## Current Status

- The learner page and the parent/admin page are separated.
- Weekly pack generation, progress recording, prompt regeneration, and manual image import are implemented.
- Teaching-style pinyin display is implemented, for example `你，第三声，nǐ`.
- Browser-based audio preview is available for chars, words, sentences, and story scenes.
- Before running `python3` on this machine, you may need to accept the macOS Xcode license with `sudo xcodebuild -license`.
