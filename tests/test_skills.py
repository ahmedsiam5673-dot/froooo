"""Logic tests that run anywhere (no microphone, no Windows needed):  python -m pytest tests"""
import datetime as dt
import os
import sys
import tempfile

os.environ["APPDATA"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fro import calc, convert, timeparse  # noqa: E402
from fro.scheduler import Scheduler  # noqa: E402
from fro.skills import Router, clean  # noqa: E402
from fro.store import Store  # noqa: E402


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_data_dir(monkeypatch):
    monkeypatch.setenv("APPDATA", tempfile.mkdtemp())


class FakeBrain:
    available = False
    history = []

    def ask(self, text, image=None, remember=True):
        return "AI:" + text


def make_router():
    store = Store()
    sched = Scheduler(store, lambda *a: None)
    return Router(store, sched, FakeBrain()), store, sched


def say(r, text):
    return r.handle(text).text


def test_clean():
    assert clean("Hey Fro, can you please open Chrome?") == "open chrome"
    assert clean("Could you set a timer for ten minutes.") == "set a timer for ten minutes"


def test_durations():
    assert timeparse.parse_duration("set a timer for 10 minutes") == 600
    assert timeparse.parse_duration("timer for twenty five minutes") == 1500
    assert timeparse.parse_duration("an hour and a half") == 5400
    assert timeparse.parse_duration("half an hour") == 1800
    assert timeparse.parse_duration("1 hour 30 minutes") == 5400
    assert timeparse.parse_duration("hello") is None


def test_extract_time():
    now = dt.datetime(2026, 11, 6, 12, 0)
    due, rest = timeparse.extract_time("wake me up at 7 am", now)
    assert due == dt.datetime(2026, 11, 7, 7, 0)
    due, _ = timeparse.extract_time("alarm tomorrow at 6:30 pm", now)
    assert due == dt.datetime(2026, 11, 7, 18, 30)
    due, _ = timeparse.extract_time("remind me in 15 minutes to stretch", now)
    assert due == now + dt.timedelta(minutes=15)
    due, _ = timeparse.extract_time("meeting on friday at 3 pm", now)
    assert due == dt.datetime(2026, 11, 13, 15, 0)
    due, _ = timeparse.extract_time("at 3", now)
    assert due == dt.datetime(2026, 11, 6, 15, 0)


def test_calc():
    assert calc.try_eval("what is 15% of 240")[1] == "36"
    assert calc.try_eval("five times six")[1] == "30"
    assert calc.try_eval("square root of 144")[1] == "12"
    assert calc.try_eval("what is 10 divided by 4")[1] == "2.5"
    assert calc.try_eval("2 to the power of 10")[1] == "1,024"
    assert calc.try_eval("open chrome") is None
    assert calc.try_eval("tell me a joke") is None
    assert calc.try_eval("__import__('os').system('x')") is None


def test_convert():
    v, a, b = convert.parse("convert 5 km to miles")
    assert round(convert.convert(v, a, b), 2) == 3.11
    v, a, b = convert.parse("72 fahrenheit to celsius")
    assert round(convert.convert(v, a, b), 1) == 22.2
    v, a, b = convert.parse("how many cm in 3 inches")
    assert round(convert.convert(v, a, b), 2) == 7.62
    assert convert.convert(1, "kg", "km") is None


def test_router_basics():
    r, store, sched = make_router()
    assert "Chrome" not in say(r, "hello")  # greeting
    assert say(r, "what's 15% of 240") == "The answer is 36."
    assert "3.1069" in say(r, "convert 5 km to miles")
    assert say(r, "my name is rakin").startswith("Nice to meet you, Rakin")
    assert say(r, "what's my name") == "Your name is Rakin."
    assert say(r, "tell me about quantum computers").startswith("AI:")


def test_timers_alarms_reminders():
    r, store, sched = make_router()
    assert say(r, "set a timer for 10 minutes") == "Timer set for 10 minutes."
    assert "9 minutes" in say(r, "how much time is left") or "10 minutes" in say(r, "how much time is left")
    assert "Cancelled 1 timer" in say(r, "cancel the timer")
    assert say(r, "set a timer").startswith("For how long")
    assert "Alarm set for" in say(r, "set an alarm for 7 am")
    assert "remind you to call mom" in say(r, "remind me to call mom in 20 minutes")
    assert len(sched.list()) == 2
    assert "Cancelled 1 alarm" in say(r, "cancel my alarm")


def test_notes_and_lists():
    r, store, sched = make_router()
    assert say(r, "take a note buy milk and eggs") == "Noted."
    assert store.notes()[0]["text"] == "buy milk and eggs"
    assert "Added eggs, bread" in say(r, "add eggs and bread to my shopping list")
    assert "eggs, bread" in say(r, "what's on my shopping list")
    assert "Removed eggs" in say(r, "remove eggs from my shopping list")
    assert say(r, "remember my wifi password is on the fridge") == "Got it. I'll remember that."
    assert "fridge" in say(r, "what do you remember about me")


def test_confirmation_flow():
    r, store, sched = make_router()
    out = r.handle("clear my shopping list")
    assert out.expect and "confirm" in out.text.lower()
    assert say(r, "no") == "Okay, cancelled."
    store.list_add("shopping", "x")
    r.handle("clear my shopping list")
    assert "cleared" in say(r, "yes")
    assert store.list_get("shopping") == []


def test_open_vs_search_routing():
    r, *_ = make_router()
    calls = []
    import fro.skills as sk

    sk._open_url = lambda u: calls.append(u)
    sk._launch = lambda t: calls.append("launch:" + t)
    assert say(r, "open chrome") == "Opening chrome."
    assert say(r, "open youtube") == "Opening youtube."
    assert "Searching Google for best laptops" in say(r, "search for best laptops")
    assert "Looking for lofi on YouTube" in say(r, "play lofi")
    assert calls[0] == "launch:chrome"
    assert calls[1].startswith("https://www.youtube.com")
    assert "google.com/search" in calls[2]


def test_scheduler_fires():
    store = Store()
    fired = []
    sched = Scheduler(store, lambda item, late: fired.append(item))
    sched.add("timer", dt.datetime.now() - dt.timedelta(seconds=1), "x")
    sched._tick()
    assert len(fired) == 1 and sched.list() == []
