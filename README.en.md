# wireless-mic-battery-alert

[日本語 README](./README.md)

A Windows application that monitors wireless microphone input, detects extended silence that may indicate battery drain or connection issues, and alerts the user.

## Overview

- Monitors microphone input and alerts on sustained silence
- Lets users configure alert sounds, pause/resume sounds, thresholds, and timing
- Targets Windows `.exe` distribution

## Main Features

- Input device selection
- Silence threshold and duration settings
- Configurable alert sound
- Configurable pause, stop, and resume sounds
- Task tray integration
- Windows EXE build support

## Repository Layout

```text
wireless-mic-battery-alert/
├── requirements.md
├── wireless-mic-battery-alert-PL/
│   ├── design/
│   └── tasks/
└── wireless-mic-battery-alert-eng/
    ├── assets/
    ├── main.py
    ├── gui.py
    ├── monitor.py
    ├── notifier.py
    ├── settings.py
    ├── tray.py
    ├── build.spec
    ├── build_windows.bat
    └── BUILD_WINDOWS.md
```

## Development Environment

- Python
- tkinter / ttk / sv_ttk
- sounddevice
- numpy
- matplotlib
- pygame
- pystray
- Pillow
- PyInstaller

Install dependencies:

```bash
pip install -r wireless-mic-battery-alert-eng/requirements.txt
```

## Run in Development

```bash
cd wireless-mic-battery-alert-eng
python main.py
```

## Screenshot

![Application screenshot](./docs/images/app-screenshot.png)

## Windows Build

Use a native Windows environment for final builds.  
Artifacts built on Linux or WSL are not treated as final release outputs.

See:

- [wireless-mic-battery-alert-eng/BUILD_WINDOWS.md](./wireless-mic-battery-alert-eng/BUILD_WINDOWS.md)

Basic Windows command:

```bat
cd wireless-mic-battery-alert-eng
build_windows.bat
```

## Notes

- `wireless-mic-battery-alert-PL/` contains planning, design, and review documents
- `wireless-mic-battery-alert-eng/` contains the application implementation
- `requirements-lock.txt` is kept as a build-environment record
