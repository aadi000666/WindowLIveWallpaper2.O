# LiveWall

Turn a video into a looping wallpaper on Windows. LiveWall places its video surface on the Windows desktop wallpaper layer, underneath desktop icons, and pauses playback while a fullscreen application is in the foreground.

## Features

- Video wallpaper playback using Qt Multimedia (MP4, MKV, AVI, MOV, and WebM, subject to installed Qt/Windows codecs).
- Looping playback, mute and volume controls, and playback speed from 0.25x to 2x.
- Automatically pauses for fullscreen or borderless fullscreen applications and resumes afterward.
- System tray controls for playback, mute, video selection, startup behavior, and exit.
- Optional per-user Windows sign-in startup registration.
- Dark settings panel.

## Requirements

- Windows 10 or 11.
- Python 3.9 or newer.
- A video format/codec supported by the Qt Multimedia backend on the target computer.

## Run from source

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

Optionally pass a video on startup:

```powershell
python main.py "C:\Videos\wallpaper.mp4"
```

Use `--minimized` to start directly in the system tray:

```powershell
python main.py --minimized
```

Select a video from the settings panel or tray menu. Closing the settings panel minimizes LiveWall to the tray; use **Exit** in the tray menu to stop it. Selecting a file does not guarantee its codec can be decoded: if playback fails, try an MP4 encoded with H.264 video and AAC audio.

## Build a standalone executable

Install PyInstaller into the same environment:

```powershell
pip install pyinstaller
```

From the project root, build the Windows executable:

```powershell
pyinstaller --onefile --noconsole --name LiveWall main.py
```

The executable is created at `dist\LiveWall.exe`. Qt Multimedia and the required Windows media codecs must be available on the destination machine. Test the packaged build on a clean Windows machine before publishing.

## Notes

- LiveWall asks Explorer to create the `WorkerW` desktop layer and attaches its video surface behind the desktop icons. This is an Explorer implementation detail that can vary across Windows versions and desktop customization tools. Restarting Explorer may require restarting LiveWall.
- If desktop attachment fails, close and relaunch LiveWall normally (not **Run as administrator**) and restart Windows Explorer if needed. Desktop customization utilities or Windows policies can block WorkerW hosting.
- Fullscreen detection uses the foreground window's bounds, so borderless fullscreen windows are included.
- The video surface fills the desktop; videos with a different aspect ratio are cropped slightly rather than letterboxed.
- The current wallpaper surface is sized to the primary display.
- LiveWall remembers the selected video, volume, mute state, and playback speed so the wallpaper can be restored at sign-in.
- Audio starts muted by default; unmute it from the panel or tray if you want wallpaper audio.

## License

LiveWall is distributed under the MIT License; see [LICENSE](LICENSE).

# 🎥 LiveWall v1.0.0

A lightweight, open-source Windows utility to set video files (.mp4) as dynamic desktop wallpapers.

## ✨ Features
- 🎬 **Custom Video Wallpapers:** Set any MP4 video as your background.
- ⚡ **Auto-Pause Mode:** Automatically pauses video when full-screen apps/games run to save CPU/RAM.
- 🪟 **System Tray:** Runs quietly in the background near the system clock.

## 🚀 Quick Download
1. Go to **[Releases](../../releases)**.
2. Download `LiveWall.exe`.
3. Double-click to run!
