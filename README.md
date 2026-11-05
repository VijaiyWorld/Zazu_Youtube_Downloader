# YouTube Video / MP3 Downloader UI

A desktop Python app using Tkinter, yt-dlp, and FFmpeg.

## Features
- User-selectable MP4 video or MP3 audio
- Video quality: Best, 1080p, 720p, 480p, 360p
- MP3 bitrate: 320, 256, 192, 128 kbps
- Folder picker, progress, cancellation, and Open Folder
- Work runs in a background thread so the UI stays responsive

## Requirements
- Python 3.10+
- FFmpeg available on PATH
- Internet connection

## Windows setup
1. Install Python from python.org and enable **Add Python to PATH**.
2. Install FFmpeg, for example with: `winget install Gyan.FFmpeg`
3. Open Command Prompt in this folder.
4. Run: `python -m venv .venv`
5. Run: `.venv\Scripts\activate`
6. Run: `python -m pip install -r requirements.txt`
7. Run: `python app.py`

## Linux setup
Install Tkinter and FFmpeg, for example on Ubuntu/Debian:
`sudo apt install python3-tk ffmpeg`

Then create a virtual environment, install requirements, and run `python app.py`.

## Optional Windows EXE
After testing the app:
1. `python -m pip install pyinstaller`
2. `pyinstaller --noconfirm --onefile --windowed --name MediaDownloader app.py`
3. The EXE will be in `dist`. FFmpeg must still be installed on the target PC and available on PATH.

## Responsible use
Download only content that you own, that is licensed for download, or for which you have permission. Follow YouTube's Terms of Service and applicable copyright law.
