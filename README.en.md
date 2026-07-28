# wireless-mic-battery-alert

[日本語 README](./README.md)

A Windows application that detects wireless microphone battery drain and connection loss by watching for signal dropout at the receiver, and alerts the user.

## Overview

- Watches the wireless receiver and alerts when the transmitter's signal stops
- Lets users configure alert, pause, stop, and resume sounds
- Targets Windows `.exe` distribution

## How Detection Works

When the transmitter powers off, the receiver emits **exact digital silence** — samples whose value is precisely zero. While the transmitter is alive, zero samples never appear. The app keys on that difference.

Measured on a BOYA mini over WASAPI, 10 seconds per state:

| State | Zero samples | Smallest non-zero value |
|---|---|---|
| Transmitter on | 0.0000% (0 of 480,000) | 2.9e-14 |
| Transmitter off | 100.00% | none |

Because the test does not depend on loudness, there is no threshold to tune and a quiet room does not affect it.

### Why not a volume threshold

With Windows 11 **Voice Clarity** (an AI noise-suppression APO inserted into the capture path) enabled, ambient noise is suppressed so aggressively that a **live microphone in a quiet room reads below -100 dB**. The gap between "dead battery noise" and "live microphone in a quiet room" disappears, so no threshold can separate them. Signal-dropout detection is immune to this.

## Main Features

- Input device selection (WASAPI)
- Battery-drain detection by signal dropout
- Configurable alert interval
- Configurable alert sound (5 built-in sounds or any WAV file)
- Configurable pause, stop, and resume sounds
- Automatic monitoring pause after an alert, with automatic resume when the signal returns
- Live input level readout (dB and zero-sample ratio)
- Task tray integration
- Windows EXE build support

## Settings

| Setting | Description |
|---|---|
| Input device | The wireless receiver to monitor |
| Alert interval (sec) | How often to repeat the alert while the signal is gone |
| Volume | Notification volume (0–100) |
| Alert sound | Played when signal loss is detected |
| Pause sound | Played when monitoring auto-pauses |
| Stop / resume sound | Played when monitoring is toggled manually |
| Auto-pause | Pause monitoring after the configured number of alerts |
| Alerts before pausing | Defaults to 1 |
| Theme | system / light / dark |

Settings save automatically on change; the save time is shown at the bottom of the window.

Signal loss and signal return each require one second of confirmation, so brief radio dropouts and the link-establishment period after power-on do not trigger false alerts. These are internal constants rather than settings.

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
