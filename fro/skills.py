"""Everything Fro can do. Router.handle(text) -> Reply.

Order of the @rule functions matters: the first matching rule wins, anything left over goes to the AI brain.
"""
from __future__ import annotations

import base64
import datetime as dt
import io
import json
import logging
import os
import random
import re
import shutil
import subprocess
import sys
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, quote_plus

from . import calc, convert, timeparse
from .settings import settings

log = logging.getLogger("fro.skills")
IS_WIN = sys.platform == "win32"
HOME = Path.home()
_NOWIN = 0x08000000 if IS_WIN else 0  # CREATE_NO_WINDOW


@dataclass
class Reply:
    text: str
    expect: bool = False  # keep the microphone open for an answer (confirmations, questions)
    speak: bool = True


class Hooks:
    """Things skills need from the app. The engine overrides these."""

    def quit_app(self): ...
    def show_main(self): ...
    def show_page(self, name): ...
    def stop_speaking(self): ...
    def copy_text(self, text): ...


# ------------------------------------------------------------------ small helpers
def _run(args, timeout=15, shell=False):
    return subprocess.run(
        args, shell=shell, capture_output=True, text=True, timeout=timeout,
        stdin=subprocess.DEVNULL, creationflags=_NOWIN, encoding="utf-8", errors="replace",
    )


def _popen(args):
    subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, creationflags=_NOWIN)


def _launch(target):
    _popen(["cmd", "/c", "start", "", target])


def _ps(script, timeout=15):
    return _run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], timeout=timeout)


def _keys(combo):
    import keyboard

    keyboard.send(combo)


def _http_json(url, timeout=8):
    import requests

    r = requests.get(url, timeout=timeout, headers={"User-Agent": "Fro/1.0"})
    r.raise_for_status()
    return r.json()


def _http_text(url, timeout=8):
    import requests

    r = requests.get(url, timeout=timeout, headers={"User-Agent": "Fro/1.0"})
    r.raise_for_status()
    return r.text


def _open_url(url):
    webbrowser.open(url)


def _ordinal_time(d: dt.datetime) -> str:
    return d.strftime("%I:%M %p").lstrip("0")


def _greeting():
    h = dt.datetime.now().hour
    return "Good morning" if h < 12 else "Good afternoon" if h < 18 else "Good evening"


def grab_screen():
    """Screenshot as (media_type, base64) scaled down for the AI."""
    from PIL import ImageGrab

    img = ImageGrab.grab().convert("RGB")
    img.thumbnail((1600, 1600))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return "image/jpeg", base64.b64encode(buf.getvalue()).decode()


# ------------------------------------------------------------------ data tables
APPS = {
    "chrome": "chrome", "google chrome": "chrome", "edge": "msedge", "microsoft edge": "msedge",
    "firefox": "firefox", "brave": "brave", "notepad": "notepad", "calculator": "calc", "calc": "calc",
    "paint": "mspaint", "word": "winword", "excel": "excel", "powerpoint": "powerpnt",
    "outlook": "outlook", "onenote": "onenote", "cmd": "cmd", "command prompt": "cmd",
    "terminal": "wt", "powershell": "powershell", "file explorer": "explorer", "explorer": "explorer",
    "files": "explorer", "task manager": "taskmgr", "settings": "ms-settings:",
    "windows settings": "ms-settings:", "camera": "microsoft.windows.camera:", "spotify": "spotify",
    "vs code": "code", "vscode": "code", "visual studio code": "code", "whatsapp": "whatsapp:",
    "telegram": "telegram", "discord": "discord", "snipping tool": "snippingtool",
    "control panel": "control", "clock": "ms-clock:", "store": "ms-windows-store:",
    "microsoft store": "ms-windows-store:", "photos": "ms-photos:", "mail": "outlookmail:",
    "calendar": "outlookcal:", "maps": "bingmaps:", "voice recorder": "ms-callrecording:",
}
PROCESSES = {
    "chrome": "chrome.exe", "google chrome": "chrome.exe", "edge": "msedge.exe", "firefox": "firefox.exe",
    "brave": "brave.exe", "notepad": "notepad.exe", "calculator": "CalculatorApp.exe",
    "paint": "mspaint.exe", "word": "WINWORD.EXE", "excel": "EXCEL.EXE", "powerpoint": "POWERPNT.EXE",
    "outlook": "OUTLOOK.EXE", "spotify": "Spotify.exe", "vs code": "Code.exe", "vscode": "Code.exe",
    "task manager": "Taskmgr.exe", "telegram": "Telegram.exe", "whatsapp": "WhatsApp.exe",
    "discord": "Discord.exe", "camera": "WindowsCamera.exe", "photos": "Microsoft.Photos.exe",
}
SITES = {
    "youtube": "https://www.youtube.com", "google": "https://www.google.com",
    "gmail": "https://mail.google.com", "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com", "twitter": "https://x.com", "x": "https://x.com",
    "github": "https://github.com", "chatgpt": "https://chatgpt.com", "claude": "https://claude.ai",
    "netflix": "https://www.netflix.com", "linkedin": "https://www.linkedin.com",
    "amazon": "https://www.amazon.com", "wikipedia": "https://www.wikipedia.org",
    "reddit": "https://www.reddit.com", "google maps": "https://maps.google.com",
    "google drive": "https://drive.google.com", "google docs": "https://docs.google.com",
}
FOLDERS = {
    "downloads": HOME / "Downloads", "documents": HOME / "Documents", "desktop": HOME / "Desktop",
    "pictures": HOME / "Pictures", "music": HOME / "Music", "videos": HOME / "Videos",
}
SETTINGS_PAGES = {
    "bluetooth": "ms-settings:bluetooth", "wifi": "ms-settings:network-wifi",
    "wi-fi": "ms-settings:network-wifi", "network": "ms-settings:network",
    "display": "ms-settings:display", "sound": "ms-settings:sound",
    "airplane mode": "ms-settings:network-airplanemode", "airplane": "ms-settings:network-airplanemode",
    "battery": "ms-settings:batterysaver", "windows update": "ms-settings:windowsupdate",
    "update": "ms-settings:windowsupdate", "privacy": "ms-settings:privacy",
    "apps": "ms-settings:appsfeatures", "night light": "ms-settings:nightlight",
    "do not disturb": "ms-settings:notifications", "focus": "ms-settings:notifications",
    "personalization": "ms-settings:personalization", "wallpaper": "ms-settings:personalization-background",
    "storage": "ms-settings:storagesense", "accessibility": "ms-settings:easeofaccess",
    "default apps": "ms-settings:defaultapps", "printers": "ms-settings:printers",
    "mouse": "ms-settings:mousetouchpad", "keyboard": "ms-settings:keyboard",
    "date and time": "ms-settings:dateandtime", "language": "ms-settings:regionlanguage",
    "about": "ms-settings:about", "microphone": "ms-settings:privacy-microphone",
}
CITY_ZONES = {
    "london": "Europe/London", "paris": "Europe/Paris", "berlin": "Europe/Berlin", "rome": "Europe/Rome",
    "madrid": "Europe/Madrid", "moscow": "Europe/Moscow", "istanbul": "Europe/Istanbul",
    "dubai": "Asia/Dubai", "dhaka": "Asia/Dhaka", "kolkata": "Asia/Kolkata", "delhi": "Asia/Kolkata",
    "mumbai": "Asia/Kolkata", "karachi": "Asia/Karachi", "bangkok": "Asia/Bangkok",
    "singapore": "Asia/Singapore", "hong kong": "Asia/Hong_Kong", "beijing": "Asia/Shanghai",
    "shanghai": "Asia/Shanghai", "tokyo": "Asia/Tokyo", "seoul": "Asia/Seoul", "sydney": "Australia/Sydney",
    "new york": "America/New_York", "chicago": "America/Chicago", "denver": "America/Denver",
    "los angeles": "America/Los_Angeles", "san francisco": "America/Los_Angeles",
    "toronto": "America/Toronto", "mexico city": "America/Mexico_City", "sao paulo": "America/Sao_Paulo",
    "cairo": "Africa/Cairo", "lagos": "Africa/Lagos", "nairobi": "Africa/Nairobi",
    "johannesburg": "Africa/Johannesburg", "riyadh": "Asia/Riyadh", "tehran": "Asia/Tehran",
    "kathmandu": "Asia/Kathmandu", "colombo": "Asia/Colombo", "jakarta": "Asia/Jakarta",
    "manila": "Asia/Manila", "kuala lumpur": "Asia/Kuala_Lumpur",
}
CURRENCIES = {
    "dollar": "USD", "dollars": "USD", "usd": "USD", "euro": "EUR", "euros": "EUR", "eur": "EUR",
    "pound": "GBP", "pounds": "GBP", "gbp": "GBP", "yen": "JPY", "jpy": "JPY", "rupee": "INR",
    "rupees": "INR", "inr": "INR", "taka": "BDT", "bdt": "BDT", "yuan": "CNY", "cny": "CNY",
    "riyal": "SAR", "riyals": "SAR", "sar": "SAR", "dirham": "AED", "dirhams": "AED", "aed": "AED",
    "cad": "CAD", "aud": "AUD", "chf": "CHF", "franc": "CHF", "won": "KRW", "krw": "KRW",
    "ruble": "RUB", "rubles": "RUB", "rub": "RUB", "lira": "TRY", "try": "TRY", "peso": "MXN",
    "pesos": "MXN", "mxn": "MXN", "ringgit": "MYR", "myr": "MYR", "baht": "THB", "thb": "THB",
    "rand": "ZAR", "zar": "ZAR", "real": "BRL", "brl": "BRL", "sgd": "SGD", "pkr": "PKR",
}
JOKES = [
    "Why don't scientists trust atoms? Because they make up everything.",
    "I told my computer I needed a break. It said: no problem, I'll go to sleep.",
    "Why did the laptop get cold? It left its Windows open.",
    "I would tell you a UDP joke, but you might not get it.",
    "Why do programmers prefer dark mode? Because light attracts bugs.",
    "There are 10 kinds of people: those who understand binary and those who don't.",
    "What do you call a fake noodle? An impasta.",
    "Why was the math book sad? It had too many problems.",
]
FACTS = [
    "Honey never spoils. Archaeologists have eaten edible honey from ancient Egyptian tombs.",
    "A day on Venus is longer than its year.",
    "Octopuses have three hearts and blue blood.",
    "Bananas are berries, but strawberries are not.",
    "The first computer bug was a real moth, found in a Harvard computer in 1947.",
    "There are more possible chess games than atoms in the observable universe.",
]
YES = {"yes", "yeah", "yep", "yup", "sure", "confirm", "do it", "go ahead", "ok", "okay", "yes please",
       "haan", "ha", "হ্যাঁ", "হ্যা", "ji", "জি"}


# ------------------------------------------------------------------ Windows helpers
def _find_start_app(name):
    """Find any installed app by name using the Start menu (like typing in Windows search)."""
    q = re.sub(r"[^a-z0-9 ._+-]", "", name.lower()).strip()
    if not q or not IS_WIN:
        return None
    script = (
        "Get-StartApps | Where-Object { $_.Name -like '*%s*' } | Select-Object -First 1 | "
        "ConvertTo-Json -Compress" % q
    )
    try:
        out = _ps(script, timeout=15).stdout.strip()
        if not out:
            return None
        data = json.loads(out)
        return data["Name"], data["AppID"]
    except Exception:
        return None


def _open_app(name):
    name = name.strip(" .")
    extra = {k.lower(): v for k, v in (settings.get("extra_apps") or {}).items()}
    apps = {**APPS, **extra}
    if name in apps:
        _launch(apps[name])
        return f"Opening {name}."
    if name in SITES:
        _open_url(SITES[name])
        return f"Opening {name}."
    if name in FOLDERS:
        _open_path(FOLDERS[name])
        return f"Opening your {name} folder."
    if re.fullmatch(r"[a-z0-9-]+\.[a-z]{2,}(?:/\S*)?", name):
        _open_url(name if name.startswith("http") else "https://" + name)
        return f"Opening {name}."
    found = _find_start_app(name)
    if found:
        _popen(["explorer.exe", "shell:AppsFolder\\" + found[1]])
        return f"Opening {found[0]}."
    if shutil.which(name):
        _launch(name)
        return f"Opening {name}."
    return f"I couldn't find an app called {name}. You can add it in Settings under Extra apps."


def _open_path(path):
    if IS_WIN:
        os.startfile(str(path))  # noqa: S606
    else:
        _popen(["xdg-open", str(path)])


def _close_app(name):
    name = name.strip(" .")
    proc = PROCESSES.get(name) or re.sub(r"[^a-z0-9]", "", name) + ".exe"
    res = _run(["taskkill", "/f", "/im", proc])
    if res.returncode == 0:
        return f"Closed {name}."
    return f"{name.title()} doesn't seem to be running."


def _volume_iface():
    from comtypes import CLSCTX_ALL, CoInitialize
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from ctypes import POINTER, cast

    CoInitialize()
    dev = AudioUtilities.GetSpeakers()
    if hasattr(dev, "EndpointVolume"):
        return dev.EndpointVolume
    iface = dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(iface, POINTER(IAudioEndpointVolume))


def _set_volume(percent):
    percent = max(0, min(100, percent))
    try:
        _volume_iface().SetMasterVolumeLevelScalar(percent / 100.0, None)
    except Exception:
        _keys_repeat("volume down", 50)
        _keys_repeat("volume up", percent // 2)
    return f"Volume set to {percent} percent."


def _get_volume():
    try:
        return round(_volume_iface().GetMasterVolumeLevelScalar() * 100)
    except Exception:
        return None


def _keys_repeat(combo, n):
    for _ in range(n):
        _keys(combo)


def _nudge_volume(delta):
    current = _get_volume()
    if current is not None:
        return _set_volume(current + delta)
    _keys_repeat("volume up" if delta > 0 else "volume down", abs(delta) // 2)
    return "Volume up." if delta > 0 else "Volume down."


def _set_theme(light: bool):
    import winreg

    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                         r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                         0, winreg.KEY_SET_VALUE)
    for name in ("AppsUseLightTheme", "SystemUsesLightTheme"):
        winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, 1 if light else 0)
    winreg.CloseKey(key)


def _brightness(t):
    try:
        import screen_brightness_control as sbc

        current = sbc.get_brightness()[0]
        m = re.search(r"\d+", t)
        if m:
            target = int(m.group())
        elif re.search(r"\b(up|increase|raise|more|higher|brighter|brighten)\b", t):
            target = current + 20
        else:
            target = current - 20
        target = max(0, min(100, target))
        sbc.set_brightness(target)
        return f"Brightness set to {target} percent."
    except Exception:
        return "I couldn't change the brightness. That only works on a laptop screen."


# ------------------------------------------------------------------ the router
RULES = []


def rule(pattern, flags=re.I):
    rx = re.compile(pattern, flags)

    def deco(fn):
        RULES.append((rx, fn))
        return fn

    return deco


_FILLER = re.compile(
    r"^(?:(?:hey|ok|okay)\s+)?(?:fro[, ]+)?(?:please[, ]+)?"
    r"(?:(?:can|could|would|will) you (?:please )?|i (?:want|need|would like) you to |i'd like you to |go ahead and )?"
    r"(?:please )?", re.I)


def clean(raw: str) -> str:
    t = raw.strip().lower()
    t = re.sub(r"[?!.,;:]+$", "", t)
    t = _FILLER.sub("", t, count=1)
    t = re.sub(r"\s+", " ", t).strip()
    return t


class Router:
    def __init__(self, store, scheduler, brain, hooks=None):
        self.store = store
        self.scheduler = scheduler
        self.brain = brain
        self.hooks = hooks or Hooks()
        self.pending = None
        self.last_reply = ""

    def confirm(self, prompt, action):
        self.pending = action
        return Reply(f"{prompt} Say yes to confirm.", expect=True)

    def handle(self, raw: str) -> Reply:
        raw = raw.strip()
        t = clean(raw)
        if self.pending:
            action, self.pending = self.pending, None
            if t in YES:
                try:
                    out = action()
                except Exception as e:
                    log.exception("confirmed action failed")
                    out = "Sorry, that didn't work."
                reply = out if isinstance(out, Reply) else Reply(out or "Done.")
                self.last_reply = reply.text
                return reply
            return Reply("Okay, cancelled.")
        for rx, fn in RULES:
            m = rx.search(t)
            if not m:
                continue
            try:
                out = fn(self, m, t, raw)
            except Exception as e:
                log.exception("skill %s failed", fn.__name__)
                kind = type(e).__name__
                if any(w in kind for w in ("Connection", "Timeout", "HTTPError", "SSL", "ParseError", "JSONDecode")):
                    out = Reply("I couldn't reach the internet for that. Please check your connection.")
                else:
                    out = Reply("Sorry, something went wrong while doing that.")
            if out is None:
                continue
            reply = out if isinstance(out, Reply) else Reply(str(out))
            self.last_reply = reply.text
            return reply
        text = self.brain.ask(raw)
        self.last_reply = text
        # after an AI answer keep listening a few seconds, so follow-up questions need no wake word
        return Reply(text, expect=self.brain.available)

    def handle_file(self, path, question="") -> Reply:
        p = Path(path)
        ext = p.suffix.lower()
        try:
            if ext in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
                media = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                         ".webp": "image/webp", ".gif": "image/gif"}[ext]
                data = base64.b64encode(p.read_bytes()).decode()
                text = self.brain.ask(question or "Describe this image briefly and point out anything important.",
                                      image=(media, data), remember=False)
            else:
                if ext == ".pdf":
                    from pypdf import PdfReader

                    content = "\n".join((pg.extract_text() or "") for pg in PdfReader(str(p)).pages[:20])
                else:
                    content = p.read_text(encoding="utf-8", errors="replace")
                content = content[:20000]
                if not content.strip():
                    return Reply("That file looks empty, or I can't read its text.")
                prompt = f"{question or 'Summarize this file in a few sentences.'}\n\nFile: {p.name}\n\n{content}"
                text = self.brain.ask(prompt, remember=False)
        except Exception as e:
            log.exception("file failed")
            return Reply("Sorry, I couldn't read that file.")
        self.last_reply = text
        return Reply(text)


# ------------------------------------------------------------------ talking to Fro
@rule(r"^(?:hello|hi|hey|yo|hola|good (?:morning|afternoon|evening)|salam|assalamu alaikum|namaste)\b")
def _greet(r, m, t, raw):
    if len(t.split()) > 4:
        return None
    said = re.match(r"good (morning|afternoon|evening)", t)
    hello = f"Good {said.group(1)}" if said else _greeting()
    return f"{hello}, {settings.get('user_name')}! How can I help?"


@rule(r"\b(who are you|what('s| is) your name|what are you|tell me about yourself|introduce yourself)\b")
def _who(r, m, t, raw):
    return "I'm Fro, your personal assistant for this PC. I can open apps, set timers, answer questions and much more."


@rule(r"^how are you|how('s| is) it going|how do you do")
def _howareyou(r, m, t, raw):
    return random.choice(["I'm doing great, thanks for asking!", "All systems glowing. How about you?"])


@rule(r"^(thanks|thank you|thx|cheers)\b")
def _thanks(r, m, t, raw):
    return random.choice(["You're welcome!", "Anytime!", "Happy to help."])


@rule(r"^i love you\b")
def _love(r, m, t, raw):
    return "That's kind of you. I'm just a glowing circle, but I'm happy to help."


@rule(r"^(?:my name is|call me|i am called|change my name to)\s+(.+)$")
def _set_name(r, m, t, raw):
    name = m.group(1).strip().title()
    settings.set("user_name", name)
    return f"Nice to meet you, {name}. I'll call you that from now on."


@rule(r"\b(what('s| is) my name|who am i|do you know my name)\b")
def _my_name(r, m, t, raw):
    return f"Your name is {settings.get('user_name')}."


@rule(r"^remember (?:that )?(?!to\b)(.+)$")
def _remember(r, m, t, raw):
    fact = re.sub(r"^remember (?:that )?", "", raw.strip(), flags=re.I).strip(" .")
    r.store.add_fact(fact)
    return "Got it. I'll remember that."


@rule(r"\b(what do you (?:remember|know) about me|what did i tell you)\b")
def _facts(r, m, t, raw):
    facts = r.store.facts()
    return ("Here's what I remember: " + "; ".join(facts) + ".") if facts else "You haven't told me anything to remember yet."


@rule(r"^(forget everything|forget what i told you|clear my memory)\b")
def _forget(r, m, t, raw):
    return r.confirm("Forget everything you told me?", lambda: (r.store.clear_facts(), "Okay, I've forgotten it all.")[1])


@rule(r"^(what can you do|help|what do you do|show (?:me )?(?:your )?(?:commands|features|skills)|what are your (?:commands|features|skills))$")
def _help(r, m, t, raw):
    r.hooks.show_main()
    r.hooks.show_page("skills")
    return ("I can open apps, set timers, alarms and reminders, take notes, check the weather and news, "
            "do maths and conversions, play music, control volume and brightness, find files, "
            "read your screen, send emails and messages, and answer any question. Here's a full list.")


# ------------------------------------------------------------------ controlling Fro
@rule(r"^(stop|be quiet|quiet|shut up|enough|stop talking|silence)$")
def _stop(r, m, t, raw):
    r.hooks.stop_speaking()
    return Reply("", speak=False)


@rule(r"^(mute|silence) (?:yourself|fro|your voice)$|^stop (?:speaking|talking) (?:out loud|to me)$")
def _mute_self(r, m, t, raw):
    settings.set("tts_enabled", False)
    return Reply("Okay, I'll stay quiet and just show text.", speak=False)


@rule(r"^(unmute|speak) (?:yourself|fro|your voice)$|^start (?:speaking|talking)$")
def _unmute_self(r, m, t, raw):
    settings.set("tts_enabled", True)
    return "I can speak again."


@rule(r"^(go to sleep|stop listening|pause listening|sleep fro|turn off (?:wake word|listening))$")
def _wake_off(r, m, t, raw):
    settings.set("wake_enabled", False)
    r.hooks.show_page("refresh")
    return "Okay, I've stopped listening for my name. Press the hotkey when you need me."


@rule(r"^(start listening|wake up|turn on (?:wake word|listening))$")
def _wake_on(r, m, t, raw):
    settings.set("wake_enabled", True)
    r.hooks.show_page("refresh")
    return "I'm listening again."


@rule(r"^(?:quit|exit|close|shut down|turn off) fro$|^goodbye fro$")
def _quit(r, m, t, raw):
    r.hooks.quit_app()
    return "Goodbye!"


@rule(r"^(?:open|show)\s+(?:the\s+)?(?:fro|main)(?:\s+(?:window|app))?$")
def _show_main(r, m, t, raw):
    r.hooks.show_main()
    return Reply("Here I am.", speak=False)


@rule(r"^(?:open|show)\s+fro\s+settings$")
def _fro_settings(r, m, t, raw):
    r.hooks.show_main()
    r.hooks.show_page("settings")
    return "Opening my settings."


# ------------------------------------------------------------------ time, date, timers, alarms
@rule(r"\b(?:what(?:'s| is)? the time|what time is it|current time|time now|tell me the time|^time)\b(?:\s+(?:in|at)\s+(.+))?$")
def _time(r, m, t, raw):
    city = (m.group(1) or "").strip()
    if city:
        zone = CITY_ZONES.get(city)
        if not zone:
            return None
        from zoneinfo import ZoneInfo

        now = dt.datetime.now(ZoneInfo(zone))
        return f"It's {_ordinal_time(now)} in {city.title()}."
    return f"It's {_ordinal_time(dt.datetime.now())}."


@rule(r"\b(what(?:'s| is)? (?:the )?(?:date|day)(?: today)?|today's date|what day is (?:it|today)|^date$|^today$)\b")
def _date(r, m, t, raw):
    return dt.datetime.now().strftime("Today is %A, %d %B %Y.")


@rule(r"\b(cancel|stop|delete|clear|remove)\b.*\btimers?\b")
def _timer_cancel(r, m, t, raw):
    n = r.scheduler.cancel("timer")
    return f"Cancelled {n} timer{'s' if n != 1 else ''}." if n else "You don't have any timers running."


@rule(r"\b(?:how (?:much|long)|what).*\b(?:left|remaining)\b|\bcheck (?:my |the )?timers?\b")
def _timer_left(r, m, t, raw):
    if re.search(r"battery|charge|storage|space|disk|memory|ram|data|money|days|weeks|months|years|until|till", t):
        return None
    timers = r.scheduler.list("timer")
    if not timers:
        return "You don't have any timers running."
    parts = [timeparse.human_duration(max(0, r.scheduler.remaining(i))) + " left"
             + (f" on {i['label']}" if i["label"] else "") for i in timers]
    return "You have " + "; ".join(parts) + "."


@rule(r"\btimers?\b")
def _timer_set(r, m, t, raw):
    seconds = timeparse.parse_duration(t)
    if not seconds:
        return Reply("For how long should I set the timer?", expect=True)
    label = timeparse.human_duration(seconds)
    due = dt.datetime.now() + dt.timedelta(seconds=seconds)
    r.scheduler.add("timer", due, label)
    return f"Timer set for {label}."


@rule(r"\b(cancel|stop|delete|clear|remove|turn off)\b.*\balarms?\b")
def _alarm_cancel(r, m, t, raw):
    n = r.scheduler.cancel("alarm")
    return f"Cancelled {n} alarm{'s' if n != 1 else ''}." if n else "You don't have any alarms."


@rule(r"\balarms?\b|\bwake me up\b")
def _alarm_set(r, m, t, raw):
    if re.search(r"\b(list|show|what|check|any)\b", t) and "set" not in t:
        alarms = r.scheduler.list("alarm")
        if not alarms:
            return "You don't have any alarms."
        return "Your alarms: " + ", ".join(_ordinal_time(dt.datetime.fromisoformat(a["due"])) for a in alarms) + "."
    due, rest = timeparse.extract_time(t)
    if not due:
        return Reply("What time should I set the alarm for?", expect=True)
    label = re.sub(r"\b(set|an?|the|alarm|for|wake me up|called|named|to|please)\b", " ", rest)
    label = re.sub(r"\s+", " ", label).strip()
    r.scheduler.add("alarm", due, label)
    when = _ordinal_time(due)
    day = "" if due.date() == dt.date.today() else (" tomorrow" if due.date() == dt.date.today() + dt.timedelta(days=1) else due.strftime(" on %A"))
    return f"Alarm set for {when}{day}."


@rule(r"^remind me\b|\bset (?:a )?reminder\b")
def _reminder(r, m, t, raw):
    due, rest = timeparse.extract_time(t)
    label = re.sub(r"^(?:set (?:a )?reminder|remind me)\s*", "", rest).strip()
    label = re.sub(r"^(?:to|that|about)\s+", "", label).strip(" ,.")
    label = re.sub(r"\b(?:at|on|in)\s*$", "", label).strip()
    if not due:
        return Reply("When should I remind you?", expect=True) if label else Reply("What should I remind you about?", expect=True)
    if not label:
        return Reply("What should I remind you about?", expect=True)
    r.scheduler.add("reminder", due, label)
    secs = (due - dt.datetime.now()).total_seconds()
    if secs < 3600 * 5:
        return f"Okay, I'll remind you to {label} in {timeparse.human_duration(secs)}."
    return f"Okay, I'll remind you to {label} at {_ordinal_time(due)}{'' if due.date() == dt.date.today() else due.strftime(' on %A')}."


@rule(r"\b(what|show|list|check|any)\b.*\b(reminders|timers|alarms|schedule)\b")
def _list_items(r, m, t, raw):
    items = r.scheduler.list()
    r.hooks.show_main()
    r.hooks.show_page("tasks")
    if not items:
        return "You have no timers, alarms or reminders."
    return f"You have {len(items)} scheduled item{'s' if len(items) != 1 else ''}. I've opened them for you."


@rule(r"\b(add|create|schedule|put|set up)\b.*\b(event|meeting|appointment)\b")
def _calendar_add(r, m, t, raw):
    due, rest = timeparse.extract_time(t)
    title = re.sub(r"\b(add|create|schedule|put|set up|an?|the|event|meeting|appointment|called|named|for|to my calendar|on my calendar|in my calendar|called|titled)\b", " ", rest)
    title = re.sub(r"\s+", " ", title).strip() or "Event"
    url = "https://calendar.google.com/calendar/render?action=TEMPLATE&text=" + quote_plus(title.title())
    if due:
        end = due + dt.timedelta(hours=1)
        url += "&dates=" + due.strftime("%Y%m%dT%H%M%S") + "/" + end.strftime("%Y%m%dT%H%M%S")
    _open_url(url)
    when = f" for {due.strftime('%A at ')}{_ordinal_time(due)}" if due else ""
    return f"I've opened your calendar with '{title.title()}'{when}. Press Save to add it."


@rule(r"\b(what('s| is) on my calendar|my (?:schedule|agenda)|(?:open|show) (?:my |the )?calendar)\b")
def _calendar_open(r, m, t, raw):
    _open_url("https://calendar.google.com/calendar/r")
    return "Opening your calendar."


# ------------------------------------------------------------------ maths, units, money
def _currency_convert(value, a, b):
    ca, cb = CURRENCIES.get(a.strip().lower()), CURRENCIES.get(b.strip().lower())
    if not ca or not cb:
        return None
    data = _http_json(f"https://open.er-api.com/v6/latest/{ca}")
    rate = data["rates"][cb]
    return f"{calc.fmt(value)} {ca} is about {calc.fmt(round(value * rate, 2))} {cb}."


@rule(r"\b(convert|how many|how much is)\b|\d\s*[a-z°/²]+\s+(?:to|in|into)\s+[a-z]")
def _convert(r, m, t, raw):
    parsed = convert.parse(t)
    if not parsed:
        return None
    value, a, b = parsed
    result = convert.convert(value, a, b)
    if result is not None:
        return f"{calc.fmt(value)} {a} is {calc.fmt(round(result, 4))} {b}."
    try:
        return _currency_convert(value, a, b)
    except Exception:
        return "I couldn't get the exchange rate right now."


@rule(r".")
def _math(r, m, t, raw):
    res = calc.try_eval(t)
    if not res:
        return None
    expr, answer = res
    return f"The answer is {answer}."


@rule(r"^(?:flip|toss) a coin$|^heads or tails$")
def _coin(r, m, t, raw):
    return random.choice(["Heads.", "Tails."])


@rule(r"^roll (?:a |the )?(?:die|dice)(?: with (\d+) sides)?$")
def _dice(r, m, t, raw):
    return f"You rolled a {random.randint(1, int(m.group(1) or 6))}."


@rule(r"^(?:pick |give me )?(?:a )?random number(?: between (\d+) and (\d+))?$")
def _random(r, m, t, raw):
    lo, hi = int(m.group(1) or 1), int(m.group(2) or 100)
    return f"How about {random.randint(min(lo, hi), max(lo, hi))}?"


@rule(r"^(?:tell me )?(?:a )?joke$|^make me laugh$|^tell me something funny$")
def _joke(r, m, t, raw):
    if r.brain.available:
        out = r.brain.ask("Tell me one short, clean, original joke.", remember=False)
        if out:
            return out
    return random.choice(JOKES)


@rule(r"^tell me (?:a )?(?:fun |random |interesting )?fact$|^fun fact$")
def _fact(r, m, t, raw):
    if r.brain.available:
        out = r.brain.ask("Tell me one surprising true fact in one sentence.", remember=False)
        if out:
            return out
    return random.choice(FACTS)


@rule(r"^(?:what is )?the meaning of life$")
def _meaning(r, m, t, raw):
    return "Forty-two. Though I hear a nice cup of tea helps too."


# ------------------------------------------------------------------ the world
@rule(r"\b(weather|forecast|will it rain|is it (?:raining|cold|hot|sunny|snowing)|how('s| is) it outside)\b")
def _weather(r, m, t, raw):
    city = ""
    mm = re.search(r"\b(?:in|for|at)\s+([a-z .'-]+)$", t)
    if mm:
        city = mm.group(1).strip()
    city = city or settings.get("weather_city")
    url = f"https://wttr.in/{quote(city)}?format=" + quote("%l: %C, %t (feels like %f), humidity %h, wind %w")
    text = _http_text(url, timeout=10).strip()
    if not text or "Unknown location" in text:
        return "I couldn't find the weather for that place."
    text = re.sub(r"[←-⇿]", "", text).replace("+", "")
    return text


@rule(r"\b(news|headlines)\b")
def _news(r, m, t, raw):
    import xml.etree.ElementTree as ET

    xml = _http_text("https://feeds.bbci.co.uk/news/rss.xml", timeout=10)
    titles = [i.findtext("title") for i in ET.fromstring(xml).iter("item")][:4]
    return "Here are the top headlines. " + " ".join(f"{n}. {x}." for n, x in enumerate(titles, 1))


@rule(r"^(?:define|definition of|dictionary)\s+(.+)$|^what does (.+) mean$|^meaning of (.+)$")
def _define(r, m, t, raw):
    word = (m.group(1) or m.group(2) or m.group(3)).strip()
    if " " in word:
        return None
    try:
        data = _http_json("https://api.dictionaryapi.dev/api/v2/entries/en/" + quote(word))
        meaning = data[0]["meanings"][0]
        return f"{word}, {meaning['partOfSpeech']}: {meaning['definitions'][0]['definition']}"
    except Exception:
        return None


@rule(r"\b(?:my ip|ip address)\b")
def _ip(r, m, t, raw):
    return "Your public IP address is " + _http_text("https://api.ipify.org", timeout=6).strip() + "."


@rule(r"\bspeed ?test\b|\binternet speed\b")
def _speedtest(r, m, t, raw):
    _open_url("https://fast.com")
    return "Opening a speed test."


@rule(r"^(?:directions to|navigate to|take me to|how do i get to)\s+(.+)$|^where is\s+(.+)$|^show me (.+) on (?:the )?map$")
def _maps(r, m, t, raw):
    place = next(g for g in m.groups() if g)
    _open_url("https://www.google.com/maps/search/?api=1&query=" + quote_plus(place))
    return f"Showing {place} on the map."


# ------------------------------------------------------------------ media and sound
@rule(r"^(?:mute|unmute)$|^(?:mute|unmute) (?:the )?(?:sound|volume|audio|pc|laptop|computer)$")
def _mute(r, m, t, raw):
    _keys("volume mute")
    return Reply("Done.", speak=False)


@rule(r"\b(?:volume|sound)\b.*?\b(\d{1,3})\b|\b(\d{1,3})\s*(?:%|percent)\s*volume\b")
def _volume_set(r, m, t, raw):
    return _set_volume(int(m.group(1) or m.group(2)))


@rule(r"\b(?:volume|sound)\b.*\b(?:max|full)\b|\bmax(?:imum)? volume\b")
def _volume_max(r, m, t, raw):
    return _set_volume(100)


@rule(r"\b(?:volume|sound|louder|turn it up|turn up)\b.*\b(?:up|increase|raise|louder|higher)\b|\b(?:louder|turn it up)\b|\b(?:increase|raise|turn up) (?:the )?(?:volume|sound)\b")
def _volume_up(r, m, t, raw):
    return _nudge_volume(+10)


@rule(r"\b(?:volume|sound)\b.*\b(?:down|decrease|lower|reduce|quieter)\b|\b(?:quieter|turn it down|softer)\b|\b(?:decrease|lower|reduce|turn down) (?:the )?(?:volume|sound)\b")
def _volume_down(r, m, t, raw):
    return _nudge_volume(-10)


@rule(r"\bwhat(?:'s| is) the volume\b|\bhow loud\b")
def _volume_get(r, m, t, raw):
    v = _get_volume()
    return f"The volume is at {v} percent." if v is not None else "I can't read the volume right now."


@rule(r"\b(brightness|brighten|dim (?:the )?(?:screen|display))\b")
def _brightness_rule(r, m, t, raw):
    return _brightness(t)


@rule(r"^(?:pause|resume|play|stop)(?: the)?(?: music| song| video| playback| media)?$|^(?:play|pause) music$")
def _playpause(r, m, t, raw):
    _keys("play/pause media")
    return Reply("Done.", speak=False)


@rule(r"^(?:next|skip)(?: the)?(?: song| track)?$|^skip this(?: song| track)?$")
def _next(r, m, t, raw):
    _keys("next track")
    return Reply("Next track.", speak=False)


@rule(r"^(?:previous|last|go back)(?: song| track)$|^previous$")
def _prev(r, m, t, raw):
    _keys("previous track")
    return Reply("Previous track.", speak=False)


@rule(r"^play\s+(.+?)(?:\s+on\s+(spotify|youtube music|youtube))?$")
def _play(r, m, t, raw):
    query, service = m.group(1).strip(), (m.group(2) or settings.get("music_service") or "youtube").lower()
    if query in {"music", "some music", "something", "a song", "songs"}:
        _keys("play/pause media")
        return Reply("Playing.", speak=False)
    if service == "spotify":
        _open_url("spotify:search:" + quote(query))
        return f"Searching Spotify for {query}."
    _open_url("https://www.youtube.com/results?search_query=" + quote_plus(query))
    return f"Looking for {query} on YouTube."


# ------------------------------------------------------------------ system
@rule(r"\b(?:turn on |switch to |enable |use )?(dark|light) (?:mode|theme)\b")
def _theme(r, m, t, raw):
    if "turn off dark" in t or "disable dark" in t:
        light = True
    elif "turn off light" in t or "disable light" in t:
        light = False
    else:
        light = m.group(1) == "light"
    _set_theme(light)
    return f"Switched to {'light' if light else 'dark'} mode."


@rule(r"\b(?:turn (?:on|off)|switch (?:on|off)|enable|disable|toggle)\s+(?:the\s+)?(bluetooth|wi-?fi|airplane mode|night light|do not disturb|focus)\b")
def _toggle_setting(r, m, t, raw):
    name = m.group(1).replace("wifi", "wi-fi")
    _launch(SETTINGS_PAGES.get(name, SETTINGS_PAGES["network"]))
    return f"Windows doesn't let me flip {name} directly, so I've opened its settings page."


@rule(r"^(?:open|show) (?:the )?(.+?) settings$")
def _open_settings_page(r, m, t, raw):
    name = m.group(1).strip()
    if name in SETTINGS_PAGES:
        _launch(SETTINGS_PAGES[name])
        return f"Opening {name} settings."
    return None


@rule(r"\b(?:take|capture|grab|make) (?:a )?screen ?shot\b|^screenshot$")
def _screenshot(r, m, t, raw):
    from PIL import ImageGrab

    folder = HOME / "Pictures"
    folder.mkdir(exist_ok=True)
    path = folder / f"Fro_screenshot_{dt.datetime.now():%Y%m%d_%H%M%S}.png"
    ImageGrab.grab().save(path)
    return "Screenshot saved in your Pictures folder."


@rule(r"\b(?:what(?:'s| is) on (?:my )?screen|what am i looking at|(?:read|describe|explain|summari[sz]e|look at) (?:my |the |this )?(?:screen|page|window))\b")
def _screen(r, m, t, raw):
    if not r.brain.available:
        return "I need my AI brain to read the screen. Please add an Anthropic API key in Settings."
    image = grab_screen()
    question = raw if len(raw.split()) > 5 else "Describe what's on this screen and summarize anything important."
    return r.brain.ask(question, image=image, remember=False)


@rule(r"\b(?:read|what(?:'s| is) in|summari[sz]e) (?:my |the )?clipboard\b")
def _clipboard(r, m, t, raw):
    out = _ps("[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-Clipboard -Raw").stdout.strip()
    if not out:
        return "Your clipboard is empty."
    if "summar" in t and r.brain.available:
        return r.brain.ask("Summarize this briefly:\n\n" + out[:15000], remember=False)
    return out[:600]


@rule(r"^copy (?:that|this|your (?:last )?(?:reply|answer|response))$")
def _copy_last(r, m, t, raw):
    if not r.last_reply:
        return "I have nothing to copy yet."
    r.hooks.copy_text(r.last_reply)
    return Reply("Copied.", speak=False)


@rule(r"\bbattery\b")
def _battery(r, m, t, raw):
    import psutil

    b = psutil.sensors_battery()
    if b is None:
        return "I can't find a battery. This looks like a desktop PC."
    state = "charging" if b.power_plugged else "not charging"
    return f"Battery is at {int(b.percent)} percent and {state}."


@rule(r"\b(?:cpu|ram|memory usage|disk space|storage left|system (?:status|info)|how is my (?:pc|computer|laptop))\b")
def _status(r, m, t, raw):
    import psutil

    cpu = psutil.cpu_percent(interval=0.6)
    mem = psutil.virtual_memory().percent
    disk = psutil.disk_usage(os.environ.get("SystemDrive", "C:") + "\\" if IS_WIN else "/")
    return (f"CPU is at {cpu:.0f} percent, memory is {mem:.0f} percent used, "
            f"and you have {disk.free / 1e9:.0f} gigabytes free on your main drive.")


@rule(r"^lock (?:the |my )?(?:laptop|computer|pc|screen|windows)$|^lock$")
def _lock(r, m, t, raw):
    _popen(["rundll32.exe", "user32.dll,LockWorkStation"])
    return Reply("Locking your PC.", speak=False)


@rule(r"\b(?:go to sleep mode|sleep mode|put (?:the |my )?(?:laptop|computer|pc) to sleep|sleep (?:the |my )?(?:laptop|computer|pc))\b")
def _sleep(r, m, t, raw):
    return r.confirm("Put the PC to sleep?", lambda: (_popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"]), "Sleeping.")[1])


@rule(r"\bhibernate\b")
def _hibernate(r, m, t, raw):
    return r.confirm("Hibernate the PC?", lambda: (_popen(["shutdown", "/h"]), "Hibernating.")[1])


@rule(r"\b(?:shut ?down|turn off|power off)\s+(?:the |my )?(?:laptop|computer|pc)\b|^shut ?down$")
def _shutdown(r, m, t, raw):
    return r.confirm("Shut down the PC?", lambda: (_popen(["shutdown", "/s", "/t", "5"]), "Shutting down in 5 seconds.")[1])


@rule(r"\b(?:restart|reboot)\b(?:\s+(?:the |my )?(?:laptop|computer|pc))?$")
def _restart(r, m, t, raw):
    return r.confirm("Restart the PC?", lambda: (_popen(["shutdown", "/r", "/t", "5"]), "Restarting in 5 seconds.")[1])


@rule(r"\b(?:sign out|log out|log off)\b")
def _signout(r, m, t, raw):
    return r.confirm("Sign out of Windows?", lambda: (_popen(["shutdown", "/l"]), "Signing out.")[1])


@rule(r"\bcancel (?:the )?(?:shutdown|restart)\b")
def _cancel_shutdown(r, m, t, raw):
    _run(["shutdown", "/a"])
    return "Cancelled."


@rule(r"\bempty (?:the |my )?(?:recycle bin|trash|bin)\b")
def _recycle(r, m, t, raw):
    return r.confirm("Empty the Recycle Bin?", lambda: (_ps("Clear-RecycleBin -Force -ErrorAction SilentlyContinue"), "Recycle Bin emptied.")[1])


# ------------------------------------------------------------------ windows and typing
_WINDOW_KEYS = [
    (r"^(?:show|go to) (?:the )?desktop$|^minimi[sz]e (?:all|everything|all windows)$", "windows+d", "Showing the desktop."),
    (r"^(?:close|exit) (?:this|the current|that) (?:window|app|program)$", "alt+f4", "Closing it."),
    (r"^(?:close|exit) (?:this|the current|that) tab$|^close tab$", "ctrl+w", "Closing the tab."),
    (r"^(?:new tab|open a new tab)$", "ctrl+t", "New tab."),
    (r"^(?:switch|change) (?:window|app)s?$|^next window$", "alt+tab", "Switching."),
    (r"^maxi[mn]i[sz]e(?: this| the)?(?: window)?$", "windows+up", "Maximized."),
    (r"^minimi[sz]e(?: this| the)?(?: window)?$", "windows+down", "Minimized."),
    (r"^snap (?:this |the )?(?:window )?left$", "windows+left", "Snapped left."),
    (r"^snap (?:this |the )?(?:window )?right$", "windows+right", "Snapped right."),
    (r"^(?:full ?screen|exit full ?screen)$", "f11", "Done."),
    (r"^(?:copy|copy this|copy that selection)$", "ctrl+c", "Copied."),
    (r"^(?:paste|paste it|paste here)$", "ctrl+v", "Pasted."),
    (r"^cut(?: this)?$", "ctrl+x", "Cut."),
    (r"^undo(?: that)?$", "ctrl+z", "Undone."),
    (r"^redo(?: that)?$", "ctrl+y", "Redone."),
    (r"^select all$", "ctrl+a", "Selected everything."),
    (r"^save(?: this| the file)?$", "ctrl+s", "Saved."),
    (r"^(?:press )?enter$", "enter", ""),
]


def _make_key_rule(combo, msg):
    def fn(r, m, t, raw):
        _keys(combo)
        return Reply(msg, speak=False)

    return fn


for _pat, _combo, _msg in _WINDOW_KEYS:
    rule(_pat)(_make_key_rule(_combo, _msg))


@rule(r"^(?:type|dictate)\s+(.+)$")
def _type(r, m, t, raw):
    import keyboard

    text = re.sub(r"^(?:please\s+)?(?:type|dictate)\s+", "", raw.strip(), flags=re.I)
    time.sleep(0.4)
    keyboard.write(text, delay=0.01)
    return Reply("Typed.", speak=False)


@rule(r"^(?:repeat after me|say)\s+(.+)$")
def _say(r, m, t, raw):
    return re.sub(r"^(?:please\s+)?(?:repeat after me|say)\s+", "", raw.strip(), flags=re.I)


@rule(r"^spell\s+(.+)$")
def _spell(r, m, t, raw):
    word = m.group(1).strip().replace(" ", "")
    return f"{word} is spelled " + ", ".join(word.upper()) + "."


# ------------------------------------------------------------------ files and folders
@rule(r"^(?:open|show) (?:my |the )?(downloads|documents|desktop|pictures|music|videos)(?: folder)?$")
def _open_folder(r, m, t, raw):
    _open_path(FOLDERS[m.group(1)])
    return f"Opening your {m.group(1)} folder."


def _search_files(words, limit=6):
    roots = [FOLDERS["desktop"], FOLDERS["documents"], FOLDERS["downloads"], FOLDERS["pictures"], FOLDERS["videos"], FOLDERS["music"]]
    found, scanned = [], 0
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".") and d.lower() not in {"node_modules", "__pycache__", "appdata"}]
            for name in filenames + dirnames:
                scanned += 1
                low = name.lower()
                if all(w in low for w in words):
                    found.append(Path(dirpath) / name)
                    if len(found) >= limit:
                        return found
            if scanned > 60000:
                return found
    return found


@rule(r"^(?:find|search for|locate|where is)\s+(?:my |the |a )?(?:file|document|folder|pdf|picture|photo|video)s?(?: named| called)?\s+(.+)$|^open (?:the )?file(?: named| called)?\s+(.+)$")
def _find_file(r, m, t, raw):
    query = (m.group(1) or m.group(2)).strip()
    words = [w for w in re.split(r"\s+", query.lower()) if w not in {"the", "a", "my"}]
    results = _search_files(words)
    if not results:
        return f"I couldn't find anything called {query} in your Desktop, Documents or Downloads."
    _open_path(results[0])
    more = f" I found {len(results)} matches; opened the first." if len(results) > 1 else ""
    return f"Opening {results[0].name}.{more}"


@rule(r"^(?:create|make|new) (?:a )?folder (?:named |called )?(.+?)(?: on (?:my )?(desktop|documents|downloads))?$")
def _new_folder(r, m, t, raw):
    name = re.sub(r'[<>:"/\\|?*]', "", m.group(1)).strip().title()
    where = FOLDERS[m.group(2) or "desktop"]
    (where / name).mkdir(parents=True, exist_ok=True)
    return f"Created a folder called {name} on your {m.group(2) or 'desktop'}."


# ------------------------------------------------------------------ notes and lists
@rule(r"^(?:take|make|write|create|add) (?:a )?note(?: that| saying| to| down)?\s*(.*)$|^note(?: down| that)?\s+(.+)$|^write down\s+(.+)$")
def _note(r, m, t, raw):
    body = next((g for g in m.groups() if g), "").strip()
    if not body:
        return Reply("What should the note say?", expect=True)
    original = re.sub(r"^(?:please\s+)?(?:(?:take|make|write|create|add) (?:a )?note(?: that| saying| to| down)?|note(?: down| that)?|write down)\s*", "", raw.strip(), flags=re.I)
    r.store.add_note(original or body)
    return "Noted."


@rule(r"\b(?:read|show|what are|what's in|open) (?:me )?(?:all )?(?:my )?notes\b")
def _read_notes(r, m, t, raw):
    notes = r.store.notes()
    if not notes:
        return "You don't have any notes yet."
    r.hooks.show_main()
    r.hooks.show_page("notes")
    last = notes[-3:]
    return "Your latest notes: " + " ... ".join(n["text"] for n in last)


@rule(r"^(?:delete|clear|erase) (?:all )?(?:my )?notes$")
def _clear_notes(r, m, t, raw):
    return r.confirm("Delete all your notes?", lambda: (r.store.clear_notes(), "All notes deleted.")[1])


@rule(r"^add (.+?) to (?:my |the )?(.+?) list$")
def _list_add(r, m, t, raw):
    items = [i.strip() for i in re.split(r",| and ", m.group(1)) if i.strip()]
    name = m.group(2).strip()
    for item in items:
        r.store.list_add(name, item)
    return f"Added {', '.join(items)} to your {name} list."


@rule(r"^(?:what(?:'s| is)|read|show) (?:on |in )?(?:my |the )?(.+?) list$|^what do i need to (?:buy|do)$")
def _list_read(r, m, t, raw):
    name = (m.group(1) if m.lastindex else None) or ("shopping" if "buy" in t else "to-do")
    items = r.store.list_get(name)
    if not items and name in {"todo", "to do"}:
        items = r.store.list_get("to-do")
    if not items:
        return f"Your {name} list is empty."
    return f"On your {name} list: " + ", ".join(items) + "."


@rule(r"^(?:clear|empty) (?:my |the )?(.+?) list$")
def _list_clear(r, m, t, raw):
    name = m.group(1).strip()
    return r.confirm(f"Clear your {name} list?", lambda: (r.store.list_clear(name), f"Your {name} list is cleared.")[1])


@rule(r"^(?:remove|delete|cross off) (.+?) from (?:my |the )?(.+?) list$")
def _list_remove(r, m, t, raw):
    ok = r.store.list_remove(m.group(2).strip(), m.group(1).strip())
    return f"Removed {m.group(1)}." if ok else f"I couldn't find {m.group(1)} on that list."


# ------------------------------------------------------------------ messages and email
def _spoken_email(text):
    text = re.sub(r"\s+at\s+", "@", text.strip())
    text = re.sub(r"\s+dot\s+", ".", text)
    return text.replace(" ", "")


@rule(r"^(?:send|write|compose|draft) (?:an? )?e-?mail(?: to (.+?))?(?: (?:saying|about|with the subject|subject|that says|telling them) (.+))?$")
def _email(r, m, t, raw):
    to = m.group(1) or ""
    body = m.group(2) or ""
    address = _spoken_email(to) if re.search(r"@| at | dot ", to) else ""
    url = "mailto:" + quote(address) + "?subject=" + quote(body.title() if body else "") + "&body=" + quote(body)
    _open_url(url)
    return "I've opened a new email for you." if not to or address else f"I've opened a new email. I don't have {to}'s address, so add it before sending."


@rule(r"^(?:send )?(?:a )?(?:whatsapp|whatsapp message|message|text)(?: to)?\s+(\+?[\d ]{7,})\s*(?:saying|that|:)?\s*(.*)$")
def _whatsapp(r, m, t, raw):
    number = re.sub(r"\D", "", timeparse.words_to_numbers(m.group(1)))
    body = m.group(2).strip()
    _open_url(f"https://wa.me/{number}" + (f"?text={quote(body)}" if body else ""))
    return "Opening WhatsApp with your message. Press send."


@rule(r"^(?:send )?(?:a )?(?:whatsapp|message|text)\b")
def _whatsapp_nonumber(r, m, t, raw):
    return Reply("Tell me the phone number with the country code, like: message 8801700000000 saying hello.", expect=True)


# ------------------------------------------------------------------ searching and opening
@rule(r"^(?:search|look up|find|google)(?: for| about| on)? (.+?) on (youtube|wikipedia|amazon|maps|github|reddit)$")
def _search_site(r, m, t, raw):
    q, site = quote_plus(m.group(1)), m.group(2)
    url = {
        "youtube": "https://www.youtube.com/results?search_query=",
        "wikipedia": "https://en.wikipedia.org/w/index.php?search=",
        "amazon": "https://www.amazon.com/s?k=",
        "maps": "https://www.google.com/maps/search/?api=1&query=",
        "github": "https://github.com/search?q=",
        "reddit": "https://www.reddit.com/search/?q=",
    }[site] + q
    _open_url(url)
    return f"Searching {site} for {m.group(1)}."


@rule(r"^(?:search|look up|google)(?: for| about)? (.+)$")
def _search(r, m, t, raw):
    _open_url("https://www.google.com/search?q=" + quote_plus(m.group(1)))
    return f"Searching Google for {m.group(1)}."


@rule(r"^(?:go to|visit|open)\s+((?:https?://)?[a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,}(?:/\S*)?)$")
def _url(r, m, t, raw):
    u = m.group(1)
    _open_url(u if u.startswith("http") else "https://" + u)
    return f"Opening {u}."


@rule(r"^(?:close|quit|exit|kill|terminate)\s+(?:the\s+)?(.+)$")
def _close(r, m, t, raw):
    return _close_app(m.group(1))


@rule(r"^(?:open|launch|start|run)\s+(?:the\s+|my\s+)?(.+)$")
def _open(r, m, t, raw):
    return _open_app(m.group(1))
