# Codex Pet Companion

A tiny desktop pet for Codex — made to sit beside your workflow, react to what Codex is doing, and slowly turn into a small companion with its own routine.

It notices tasks, tool calls, reviews, errors, quiet stretches, and care actions. It can live in a full desktop window or shrink into a compact mini pet when you want your workspace back.

## Screenshots

**Full mode**

![Codex Pet Companion full mode](screenshot.png)

**Mini mode**

![Codex Pet Companion mini mode](screenshot2.png)

## Download

Get the latest Windows build from the [Releases](https://github.com/PersephoneUsher/codex-pet-companion/releases) page.

Download the release zip, extract the `Codex Pet Companion` folder, and run:

```text
CodexPetCompanion.exe
```

The app includes an updater, so future versions can be installed from inside the app.

## Features

- Full desktop window and compact mini mode.
- Mini mode with short workflow notifications, similar to the official Codex pets.
- Reactions to Codex tasks, tool calls, reviews, errors, and quiet periods.
- Virtual-pet care: feed, play, rest, and click the pet in full mode.
- Fullness, mood, energy, focus, friendship, and days-together progression.
- Daily activities, idle discoveries, micro reactions, and high-bond moments.
- Two built-in pets:
  - Lumisprout — a tiny glowing sprout-cat forest spirit.
  - Vikamon — a mischievous chibi mascot in a green monster hoodie.
- Custom pet packs, so you can import pets made by other people or share your own.
- Built-in updater through GitHub Releases.
- Automatic Codex source detection for Windows, WSL, and custom `.codex` folders.

## How Codex affects the pet

Codex activity gives the pet something to react to.

When Codex starts working, runs tools, reaches review, finishes a response, goes quiet, or hits an error, the pet changes state, comments on the moment, and may gain or lose mood, focus, energy, or friendship.

The idea is simple: your coding workflow becomes part of the pet's day.

## How to use

1. Download the latest release zip.
2. Extract the `Codex Pet Companion` folder.
3. Run `CodexPetCompanion.exe`.
4. Open Settings if you want to check or change the detected Codex folder.
5. Choose a pet.
6. Use mini mode when you want the pet to stay out of the way.
7. Double-click the mini pet to return to the full window.

If you are running from source, use:

```text
start_companion_qt.bat
```

## Custom pets

Custom pets can be imported and exported from Settings.

A pet pack contains:

```text
pet.json
spritesheet.webp
```

Spritesheet format:

```text
v1: 1536x1872 (8 columns x 9 rows)
v2: 1536x2288 (8 columns x 11 rows)
192x208 per frame
transparent background
```

Custom pets use neutral fallback text, so they do not receive Lumisprout or Vikamon-specific lines.

## Data and updates

Windows releases are distributed as a folder:

```text
Codex Pet Companion/
  CodexPetCompanion.exe
  updater.exe
```

Your config, state, progress, and custom pets are stored in:

```text
Codex Pet Companion/data/
```

The updater replaces application files but skips `data/`, so your pet progress and custom pets survive updates.

## Build from source

On Windows, install dependencies and run:

```text
build_windows_exe.bat
```

The build script creates:

```text
dist/Codex Pet Companion/
dist/Codex-Pet-Companion-windows-x64.zip
```

For a console/debug build, run:

```text
build_windows_exe_debug.bat
```

The release includes `app_icon.ico`, and the build scripts use it automatically.

## Codex pet v2 support

Both PNG and WebP atlases are supported. If `spriteVersionNumber` is present,
it must be the integer 1 or 2 and match the image dimensions. For older manifests
without the field, the version is inferred from the exact atlas size. Invalid
imports are rejected before replacing an installed pet.

The nine existing animation sequences and timings are unchanged. V2 adds sixteen
single-frame poses from rows 9 and 10, read left to right. Frame 0 looks up,
4 right, 8 down, and 12 left; intermediate frames advance clockwise by 22.5 degrees.
In full and mini mode, an idle pet looks toward the global mouse position inside
an interaction radius (360 logical pixels at scale 1; at least 240). The center
deadzone returns to idle. A 3-degree boundary margin reduces direction flicker.
The pointer is sampled every 40 ms without changing the existing 120 ms care and
Codex activity timer. Qt logical coordinates keep pointer and pet aligned at
Windows display scaling. Dragging, care animations, active Codex states, menus,
and dialogs take priority. Moving outside the radius resumes normal animation.

Reference: [Codex Pet Web SDK atlas layout](https://github.com/wildcard/codex-pet-companion/blob/main/src/atlas.ts).
The inspected SDK provides an ordered `look-around` sequence, but does not expose
a pointer-to-angle implementation; pointer selection here is an independent Qt
implementation. This is not a claim of identical official Codex timing or behavior.

This fork checks releases from `PersephoneUsher/codex-pet-companion`, preventing
an upstream v1-only release from replacing the v2 build.

### Tests

```powershell
python -m unittest discover -s tests -v
# Optional private pet integration test (assets are not committed):
$env:PET_TEST_FOLDER = 'C:\path\to\your\pet'
python -m unittest discover -s tests -v
```

Tests cover strict version/geometry validation, legacy inference, import and
discovery, preservation of existing pets on invalid imports, all sixteen angles,
sector boundaries, all original animation rows, and activity/drag precedence.

### Reproducible Windows build

Use `python tools/build_windows_v2.py` after installing `requirements.txt`.
This builds `dist/CodexPetCompanion.exe` and `dist/updater.exe` with a restricted
build-process PATH, preventing unrelated media-tool DLLs from being collected.
It does not change the user's system PATH. The original batch scripts remain
available for environments that already have a clean build PATH.

A startup regression fix also marks `codex_source_name` as a static method;
previously detecting a Codex source could raise a TypeError during window setup.
