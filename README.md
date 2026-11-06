# Fro

A Siri-style voice assistant for Windows. Say **"Hey Fro"** and a glowing ring rises from the bottom of your screen. Ask for anything: Fro runs it on your PC or answers with AI (Claude).

- **Ring overlay** (the Siri-style glow) pops up above every window, even when Fro is hidden in the tray. Say "Hey Fro" and it appears with a soft chime and a ripple, moves with your voice while you talk, and moves with Fro's own voice while it answers. Choose top, middle or bottom of the screen in Settings (default: top).
- **Main app** (2D dark teal window with the glass orb, chat, sidebar) for typing, files, timers, notes and settings.
- Lives in the system tray, starts with Windows if you want, global hotkey **Ctrl + Alt + Space**.

## Get the .exe with GitHub Actions

1. Create a new GitHub repository and upload everything in this folder (keep the `.github` folder).
2. Open the **Actions** tab. The *Build Fro (Windows exe)* workflow runs on every push. First it runs the tests, then builds `Fro.exe`, then starts the exe once (`--selftest`) to prove every library is bundled.
3. Open the finished run and download **Fro-Windows** under *Artifacts*. Unzip it, double-click `Fro.exe`.
4. For a download link anyone can use: push a tag, for example `git tag v1.0.0 && git push origin v1.0.0`. The exe is attached to a GitHub Release automatically.

Windows may show "Windows protected your PC" because the exe is not code-signed. Click *More info → Run anyway*. Some antivirus programs also flag every PyInstaller exe; that is a false alarm for unsigned apps.

## Run from source

```
setup.bat      (once: creates a venv and installs everything, needs Python 3.12 64-bit)
run.bat        (starts Fro)
```

## First start

1. Open **Settings** (gear icon). Enter your name, choose the language you speak (`bn-BD` for Bangla), and paste your **Anthropic API key** from https://console.anthropic.com. Without a key every built-in command still works; only open questions need the key.
2. Allow microphone access: *Windows Settings → Privacy → Microphone → let desktop apps access*.
3. Say **"Hey Fro, what time is it?"** or press **Ctrl + Alt + Space** and speak.

After an AI answer, or when Fro asks you something (for example "For how long?"), it keeps listening for a few seconds, so you can answer or follow up without the wake word. Click the ring or press the hotkey to stop Fro talking.

## What Fro can do

| Area | Examples |
|---|---|
| Apps and web | "open chrome", "close spotify", "go to github.com", "search for cheap flights", "search cats on youtube" |
| Any installed app | "open photoshop" (found through the Start menu), or add your own in Settings |
| Timers and alarms | "set a timer for 25 minutes", "wake me up at 6:30 am", "cancel my alarm", "how much time is left" |
| Reminders | "remind me to call mom at 6 pm", "remind me in 20 minutes to stretch" (they survive a restart) |
| Calendar | "add a meeting tomorrow at 3 pm to my calendar" |
| Maths and units | "what's 15% of 240", "square root of 144", "convert 5 miles to km", "100 dollars in euros" |
| Time and world | "what time is it in Tokyo", "weather in Paris", "give me the news", "define serendipity", "directions to Eiffel Tower" |
| Music and sound | "play lofi on youtube", "play despacito on spotify", "pause", "next song", "volume 40", "mute" |
| PC control | "brightness 70", "dark mode", "take a screenshot", "battery", "how is my pc", "lock my pc", "shut down" (asks to confirm) |
| Windows | "show desktop", "close this window", "new tab", "maximize", "snap left", "copy", "paste", "undo", "type hello world" |
| Notes and lists | "take a note buy milk", "add eggs to my shopping list", "what's on my to-do list", "remember my locker code is 1234" |
| Messages | "send an email to bob at gmail dot com saying hi", "message 8801700000000 saying hello" |
| Files | "find the file resume", "open downloads", "create a folder projects" |
| Screen and files with AI | "what's on my screen", "summarize my clipboard", drop a PDF / text / image on the window |
| Chat | "tell me a joke", "explain black holes", "translate good morning to French", "my name is Rakin" |
| Control Fro | "stop", "go to sleep" (stops the wake word), "start listening", "quit fro" |

Everything not in this list is answered by Claude, in the language you spoke.

## Bangla

Set *Language you speak* to `bn-BD` in Settings. Fro understands Bangla speech, answers in Bangla and speaks with a Bangla voice. The wake word can stay **"Hey Fro"**.

## Good to know

- Speech recognition uses Google's free web recogniser, so listening needs internet. Natural voice (edge-tts) also needs internet; offline Windows voice is the automatic fallback.
- Windows does not allow apps to flip Bluetooth, Wi-Fi or Airplane mode directly. Fro opens the right Settings page for those.
- Brightness control works on laptop screens and many external monitors.
- Your settings, notes and timers live in `%APPDATA%\Fro`.

## Project layout

```
main.py                  entry point
fro/engine.py            listening loop, wake word, speaking, timers
fro/skills.py            every command ("rules"), tried in order, rest goes to AI
fro/brain.py             Claude
fro/voice.py             microphone and speech output
fro/ui/                  ring overlay, glass orb, main window, pages
tests/                   logic tests (python -m pytest tests)
.github/workflows/       build.yml builds Fro.exe
tools/make_icon.py       draws the app icon
```

Add a new command: write a function with `@rule(r"regex")` in `fro/skills.py` that returns the text Fro should say.
