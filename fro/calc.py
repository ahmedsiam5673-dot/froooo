"""Safe spoken-math calculator: 'what is 15% of 80', 'five times six', 'square root of 144'."""
import ast
import math
import operator
import re

from .timeparse import words_to_numbers

_BIN = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.Pow: operator.pow, ast.Mod: operator.mod, ast.FloorDiv: operator.floordiv,
}
_UN = {ast.USub: operator.neg, ast.UAdd: operator.pos}
_NAMES = {"pi": math.pi, "e": math.e}


def _ev(node):
    if isinstance(node, ast.Expression):
        return _ev(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN:
        left, right = _ev(node.left), _ev(node.right)
        if isinstance(node.op, ast.Pow) and (abs(right) > 1000 or abs(left) > 1e9):
            raise ValueError("too big")
        return _BIN[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UN:
        return _UN[type(node.op)](_ev(node.operand))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "sqrt" and len(node.args) == 1:
        return math.sqrt(_ev(node.args[0]))
    if isinstance(node, ast.Name) and node.id in _NAMES:
        return _NAMES[node.id]
    raise ValueError("unsupported")


def fmt(x) -> str:
    if isinstance(x, float):
        if x.is_integer() and abs(x) < 1e15:
            x = int(x)
        else:
            return f"{round(x, 6):,}".rstrip("0").rstrip(".") if "." in f"{round(x, 6):,}" else f"{round(x, 6):,}"
    return f"{x:,}"


def try_eval(text: str):
    """Returns (expression_text, result_text) or None if the text is not a math question."""
    t = words_to_numbers(text.lower())
    t = re.sub(r"\b(what is|what's|whats|calculate|compute|how much is|solve|equals?|please|the answer to|evaluate|math)\b", " ", t)
    t = t.replace("?", " ").replace("×", "*").replace("÷", "/")
    t = re.sub(r"(?<=\d),(?=\d{3}\b)", "", t)
    t = re.sub(r"(\d+(?:\.\d+)?)\s*(?:%|percent)\s*of\s*", r"(\1/100)*", t)
    t = re.sub(r"square root of\s*(\d+(?:\.\d+)?)", r"sqrt(\1)", t)
    t = re.sub(r"(\d+(?:\.\d+)?)\s*squared\b", r"(\1**2)", t)
    t = re.sub(r"(\d+(?:\.\d+)?)\s*cubed\b", r"(\1**3)", t)
    for pattern, repl in (
        (r"\bto the power of\b|\braised to\b|\bpower\b|\^", "**"),
        (r"(?<=\d)\s+and\s+(?=\d)|\bplus\b", "+"),
        (r"\bminus\b|\bless\b", "-"),
        (r"\btimes\b|\bmultiplied by\b|\binto\b|(?<=\d)\s*x\s*(?=\d)", "*"),
        (r"\bdivided by\b|\bover\b", "/"),
        (r"\bmod(?:ulo)?\b", "%"),
    ):
        t = re.sub(pattern, repl, t)
    t = t.strip()
    if not re.search(r"\d", t) or not re.search(r"[\+\-\*/%]|sqrt", t):
        return None
    if not re.fullmatch(r"[0-9\s\.\+\-\*/\(\)%sqrtpie]+", t):
        return None
    try:
        value = _ev(ast.parse(t.strip(), mode="eval"))
    except Exception:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return t, fmt(value)
