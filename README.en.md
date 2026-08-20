# wireless-mic-battery-alert

[日本語 README](./README.md)

A Windows application that detects wireless microphone battery drain and connection loss by watching for signal dropout at the receiver, and alerts the user.

## Overview

- Watches the wireless receiver and alerts when the transmitter's signal stops
- Lets users configure alert, pause, stop, and resume sounds
- Stays resident without preventing Windows from sleeping
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

## How Sleep Is Kept Working

Holding a capture stream open makes the USB audio driver raise a SYSTEM power request, which keeps Windows from sleeping. An application cannot withdraw that request, so the only fix is to **close the stream**.

This app stops monitoring and closes the stream once the PC has been idle, then reopens it as soon as input resumes. Since an idle PC means an unused wireless microphone, nothing practical is lost.

- Automatic stop and resume are silent, to keep them distinct from manual stop and resume
- If monitoring was stopped manually, it does not come back on its own when input resumes
- Monitoring continues while another app (Discord, OBS, and the like) is using the microphone, because that app raises the power request anyway

Set the idle threshold shorter than the machine's Windows sleep timeout (the default is 180 seconds).

This app is not the only thing that can keep a machine awake: a browser playing video, or any app producing audio, raises its own power request. When the machine will not sleep, run `powercfg /requests` from an elevated prompt to see which device or process is holding it.

## Main Features

- Input device selection (WASAPI)
- Battery-drain detection by signal dropout
- Configurable alert interval
- Configurable alert sound (5 built-in sounds or any WAV file)
- Configurable pause, stop, and resume sounds
- Automatic monitoring pause after an alert, with automatic resume when the signal returns
- Idle-linked automatic stop and resume, so the machine can still sleep
- Live input level readout (dB and zero-sample ratio)
- Task tray integration (state-colored icon, shortcuts to the config file and log)
- Windows EXE build support

## Task Tray

While resident, the tray icon shows the current state by color.

![Task tray icons](./docs/images/tray-icons.png)

| Icon | State | Meaning |
|---|---|---|
| Gray | Stopped | Monitoring was stopped manually; it does not resume on its own |
| Green | Monitoring | Normal monitoring |
| Red | Alert | Signal loss was detected and alerted (shown for 5 seconds) |
| Orange | Paused | Auto-paused after an alert. The microphone stays open and monitoring resumes when the signal returns |
| Light blue | Idle-stopped | The microphone was closed because the PC went idle. It reopens as soon as input resumes |

The distinction between **orange and light blue** matters: orange only stops the alerts and keeps the microphone open, while light blue closes it. Only the light blue state lets the machine sleep.

The right-click menu offers the settings window, monitoring start/stop, opening the config file location, opening the log, and quit.

## Settings

| Setting | Description |
|---|---|
| Input device | The wireless receiver to monitor. Stored by name, since PortAudio indices shift when devices are re-enumerated |
| Alert interval (sec) | How often to repeat the alert while the signal is gone |
| Volume | Notification volume (0–100) |
| Alert sound | Played when signal loss is detected |
| Pause sound | Played when monitoring auto-pauses |
| Stop / resume sound | Played when monitoring is toggled manually |
| Auto-pause | Pause monitoring after the configured number of alerts |
| Alerts before pausing | Defaults to 1 |
| Stop when idle | Stop monitoring once the PC has been idle (on by default) |
| Idle threshold (sec) | Defaults to 180 (range 30–1800) |
| Keep going for other apps | Keep monitoring while another app uses the microphone (on by default) |
| Theme | system / light / dark |

Settings save automatically on change; the save time and the version are shown at the bottom of the window.

`config.json` sits next to the executable. The tray right-click menu has an "open config file location" entry.

If the configured receiver cannot be found, the app falls back to the WASAPI default device, so monitoring survives a sleep cycle or a replugged USB device even when the index changes.

Signal loss and signal return each require one second of confirmation, so brief radio dropouts and the link-establishment period after power-on do not trigger false alerts. These are internal constants rather than settings.

## Logs

The app writes to `logs/app.log` next to the executable. The tray right-click menu has an "open log" entry.

Only state changes are recorded: startup and shutdown, monitoring start and stop (distinguishing manual from idle-linked), the resolved input device, alerts, auto-pause and its release, and failures.

Since the app stays resident, three measures keep the log from growing without bound.

| Measure | Detail |
|---|---|
| Size cap | 512KB × 3 generations; never exceeds 1.5MB in total |
| Repeat collapsing | Consecutive identical records are dropped, with the count appended to the next line |
| INFO by default | Nothing is written on every poll |

Set `debug_log` to `true` in `config.json` for verbose output. It records each poll, so it is not meant for everyday use.

## Repository Layout

```text
wireless-mic-battery-alert/
├── CHANGELOG.md
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
    ├── activity.py
    ├── applog.py
    ├── tray.py
    ├── version.py
    ├── test_phase10.py
    ├── test_suspend_flow.py
    ├── test_gui_build.py
    ├── test_resume_no_alert.py
    ├── test_device_resolve.py
    ├── test_logging.py
    ├── build.spec
    ├── build_windows.bat
    └── BUILD_WINDOWS.md
```

| File | Role |
|---|---|
| `main.py` | Startup, config loading, monitor control, notification and tray/GUI wiring |
| `monitor.py` | Input device monitoring and signal-dropout detection |
| `activity.py` | PC idle time and other apps' microphone usage |
| `applog.py` | Log output and size management |
| `notifier.py` | Notification sound resolution and playback |
| `settings.py` | Config file load and save |
| `gui.py` | Settings window |
| `tray.py` | Task tray integration |
| `version.py` | Version information |

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

## Tests

```bash
cd wireless-mic-battery-alert-eng
python test_phase10.py
python test_suspend_flow.py
python test_gui_build.py
python test_resume_no_alert.py
python test_device_resolve.py
python test_logging.py
```

These cover idle detection, microphone-usage lookup, automatic stop and resume, and settings-window construction. Run them on Windows.

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
- See [CHANGELOG.md](./CHANGELOG.md) for the release history
