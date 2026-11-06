"""Unit conversion: 'convert 5 km to miles', 'how many cm in 3 inches', '72 f to c'."""
import re

_U = {}


def _add(cat, factor, *names):
    for n in names:
        _U[n] = (cat, factor)


_add("len", 0.001, "mm", "millimeter", "millimetre")
_add("len", 0.01, "cm", "centimeter", "centimetre")
_add("len", 1, "m", "meter", "metre")
_add("len", 1000, "km", "kilometer", "kilometre")
_add("len", 0.0254, "in", "inch", "inche")
_add("len", 0.3048, "ft", "foot", "feet")
_add("len", 0.9144, "yd", "yard")
_add("len", 1609.344, "mi", "mile")
_add("mass", 1e-6, "mg", "milligram")
_add("mass", 0.001, "g", "gram")
_add("mass", 1, "kg", "kilogram", "kilo")
_add("mass", 1000, "tonne", "ton", "metric ton")
_add("mass", 0.45359237, "lb", "lbs", "pound")
_add("mass", 0.0283495231, "oz", "ounce")
_add("vol", 0.001, "ml", "milliliter", "millilitre")
_add("vol", 1, "l", "liter", "litre")
_add("vol", 3.785411784, "gal", "gallon")
_add("vol", 0.946352946, "quart", "qt")
_add("vol", 0.473176473, "pint", "pt")
_add("vol", 0.2365882365, "cup")
_add("vol", 0.01478676478, "tbsp", "tablespoon")
_add("vol", 0.00492892159, "tsp", "teaspoon")
_add("time", 1, "s", "sec", "second")
_add("time", 60, "min", "minute")
_add("time", 3600, "hr", "hour", "h")
_add("time", 86400, "day")
_add("time", 604800, "week")
_add("speed", 1, "m/s", "mps")
_add("speed", 0.2777778, "km/h", "kmh", "kph", "kilometers per hour", "kilometres per hour")
_add("speed", 0.44704, "mph", "miles per hour")
_add("speed", 0.514444, "knot", "kn")
_add("data", 1, "byte", "b")
_add("data", 1024, "kb", "kilobyte")
_add("data", 1024 ** 2, "mb", "megabyte")
_add("data", 1024 ** 3, "gb", "gigabyte")
_add("data", 1024 ** 4, "tb", "terabyte")
_add("area", 1, "sqm", "square meter", "square metre")
_add("area", 1e6, "sqkm", "square kilometer", "square kilometre")
_add("area", 0.09290304, "sqft", "square foot", "square feet")
_add("area", 4046.8564224, "acre")
_add("area", 10000, "hectare", "ha")

_TEMP = {"c": "c", "celsius": "c", "centigrade": "c", "f": "f", "fahrenheit": "f", "k": "k", "kelvin": "k"}

_PATTERN = re.compile(
    r"(-?\d+(?:\.\d+)?)\s*(?:degrees?\s+)?([a-z/²°\s]+?)\s+(?:to|in|into|as)\s+(?:degrees?\s+)?([a-z/²°\s]+?)\s*$"
)
_HOWMANY = re.compile(r"how many\s+([a-z/\s]+?)\s+(?:are\s+)?in\s+(?:a\s+|an\s+)?(-?\d+(?:\.\d+)?)?\s*([a-z/\s]+?)\s*$")


def _norm(unit: str):
    u = unit.strip().lower().replace("°", "").replace("degrees", "").replace("degree", "").strip()
    u = re.sub(r"^(?:the|a|an)\s+", "", u)
    if u in _U or u in _TEMP:
        return u
    for suffix in ("es", "s"):
        if u.endswith(suffix) and (u[: -len(suffix)] in _U or u[: -len(suffix)] in _TEMP):
            return u[: -len(suffix)]
    if u.endswith("ies") and u[:-3] + "y" in _U:
        return u[:-3] + "y"
    return u


def parse(text: str):
    """Returns (value, from_word, to_word) or None."""
    t = text.lower().replace("?", "").strip()
    t = re.sub(r"^(?:convert|what is|what's|how much is|change)\s+", "", t)
    m = _HOWMANY.search(t)
    if m:
        target, num, source = m.group(1), m.group(2), m.group(3)
        return float(num) if num else 1.0, source.strip(), target.strip()
    m = _PATTERN.search(t)
    if m:
        return float(m.group(1)), m.group(2).strip(), m.group(3).strip()
    return None


def convert(value: float, src: str, dst: str):
    """Returns the converted number, or None if the units are unknown or incompatible."""
    a, b = _norm(src), _norm(dst)
    if a in _TEMP and b in _TEMP:
        x, y = _TEMP[a], _TEMP[b]
        celsius = value if x == "c" else (value - 32) * 5 / 9 if x == "f" else value - 273.15
        return celsius if y == "c" else celsius * 9 / 5 + 32 if y == "f" else celsius + 273.15
    if a in _U and b in _U and _U[a][0] == _U[b][0]:
        return value * _U[a][1] / _U[b][1]
    return None
