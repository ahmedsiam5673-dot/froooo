"""Understand spoken durations ("in 10 minutes") and times ("tomorrow at 7:30 pm")."""
import datetime as dt
import re

_ONES = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
         "eighty": 80, "ninety": 90}
_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_UNIT = r"(?:hours?|hrs?|h|minutes?|mins?|m|seconds?|secs?|s)"
_DUR = re.compile(r"(\d+(?:\.\d+)?)\s*(" + _UNIT + r")\b")
_REL = re.compile(r"(?:\b(?:in|after|for|within)\s+)?(?:\d+(?:\.\d+)?\s*" + _UNIT + r"\b(?:\s*(?:and\s+)?)?)+")


def words_to_numbers(text: str) -> str:
    """'twenty five minutes' -> '25 minutes', 'half an hour' -> '30 minutes'."""
    t = text.lower()
    t = re.sub(r"\ba quarter of an hour\b", "15 minutes", t)
    t = re.sub(r"\bhalf an hour\b|\bhalf hour\b", "30 minutes", t)
    t = re.sub(r"\b(?:an|one|1) hour and a half\b", "90 minutes", t)
    t = re.sub(r"\b(\d+) and a half hours?\b", lambda m: f"{int(m.group(1)) * 60 + 30} minutes", t)
    t = re.sub(r"\b(?:an|a)\s+(?=(?:hour|minute|second|min|sec)s?\b)", "1 ", t)
    tokens = t.split()
    out, i = [], 0
    while i < len(tokens):
        core = tokens[i].strip(",.")
        if core in _TENS:
            val = _TENS[core]
            if i + 1 < len(tokens):
                nxt = tokens[i + 1].strip(",.")
                if nxt in _ONES and 1 <= _ONES[nxt] <= 9:
                    val += _ONES[nxt]
                    i += 1
            out.append(str(val))
        elif core in _ONES:
            out.append(str(_ONES[core]))
        else:
            out.append(tokens[i])
        i += 1
    return " ".join(out)


def _unit_seconds(unit: str) -> int:
    u = unit.lower()
    if u.startswith("h"):
        return 3600
    if u.startswith("m"):
        return 60
    return 1


def parse_duration(text: str):
    """Total seconds in the text, or None."""
    t = words_to_numbers(text)
    found, total = False, 0.0
    for m in _DUR.finditer(t):
        found = True
        total += float(m.group(1)) * _unit_seconds(m.group(2))
    return total if found else None


def _remove_spans(text, spans):
    out, last = [], 0
    for a, b in sorted(spans):
        out.append(text[last:a])
        last = b
    out.append(text[last:])
    return re.sub(r"\s+", " ", " ".join(out)).strip()


def extract_time(text: str, now: dt.datetime = None):
    """Find a time in the text. Returns (datetime or None, the text without the time words)."""
    now = now or dt.datetime.now()
    t = words_to_numbers(text)

    # 1) relative: "in 10 minutes", "for 1 hour 30 minutes"
    rel = _REL.search(t)
    if rel:
        secs = sum(float(m.group(1)) * _unit_seconds(m.group(2)) for m in _DUR.finditer(rel.group(0)))
        if secs > 0:
            return now + dt.timedelta(seconds=secs), _remove_spans(t, [rel.span()])

    # 2) absolute
    spans = []
    day_offset, evening = None, False

    m = re.search(r"\bday after tomorrow\b", t)
    if m:
        day_offset = 2
        spans.append(m.span())
    else:
        m = re.search(r"\btomorrow\b", t)
        if m:
            day_offset = 1
            spans.append(m.span())
    for word in ("tonight", "this evening", "this afternoon", "in the evening", "in the afternoon"):
        m = re.search(r"\b" + word + r"\b", t)
        if m:
            evening = True
            day_offset = 0 if day_offset is None else day_offset
            spans.append(m.span())
            break
    m = re.search(r"\btoday\b", t)
    if m:
        day_offset = 0 if day_offset is None else day_offset
        spans.append(m.span())
    for idx, name in enumerate(_WEEKDAYS):
        m = re.search(r"\b(?:on\s+|next\s+)?" + name + r"\b", t)
        if m:
            ahead = (idx - now.weekday()) % 7 or 7
            day_offset = ahead
            spans.append(m.span())
            break

    hour = minute = None
    ambiguous = False
    m = re.search(r"\b(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?(?!\w)", t)
    if m:
        hour, minute = int(m.group(1)) % 12 + (12 if m.group(3) == "p" else 0), int(m.group(2) or 0)
        spans.append(m.span())
    else:
        m = re.search(r"\b(?:at\s+)?(\d{1,2}):(\d{2})\b", t)
        if m:
            hour, minute = int(m.group(1)), int(m.group(2))
            ambiguous = hour <= 12
            spans.append(m.span())
        else:
            m = re.search(r"\bat\s+(\d{1,2})\b(?!\s*(?:minutes?|hours?|%))", t)
            if m:
                hour, minute, ambiguous = int(m.group(1)), 0, int(m.group(1)) <= 12
                spans.append(m.span())
            else:
                m = re.search(r"\b(noon|midnight)\b", t)
                if m:
                    hour, minute = (12 if m.group(1) == "noon" else 0), 0
                    spans.append(m.span())

    if hour is None and day_offset is None:
        return None, text
    if hour is None:
        hour, minute = 9, 0
    if hour > 23 or minute > 59:
        return None, text

    base = (now + dt.timedelta(days=day_offset or 0)).replace(second=0, microsecond=0)
    if ambiguous:
        if evening and hour < 12:
            hour += 12
        elif day_offset is None:
            first = base.replace(hour=hour % 12, minute=minute)
            second = base.replace(hour=hour % 12 + 12, minute=minute)
            due = first if first > now else second if second > now else first + dt.timedelta(days=1)
            return due, _remove_spans(t, spans)
        elif hour == 12:
            hour = 12
    elif evening and hour < 12:
        hour += 12
    due = base.replace(hour=hour, minute=minute)
    if due <= now and day_offset is None:
        due += dt.timedelta(days=1)
    return due, _remove_spans(t, spans)


def human_duration(seconds: float) -> str:
    seconds = int(round(seconds))
    if seconds < 60:
        return f"{seconds} second{'s' if seconds != 1 else ''}"
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    parts = []
    if h:
        parts.append(f"{h} hour{'s' if h != 1 else ''}")
    if m:
        parts.append(f"{m} minute{'s' if m != 1 else ''}")
    if s and not h:
        parts.append(f"{s} second{'s' if s != 1 else ''}")
    return " and ".join(parts)
