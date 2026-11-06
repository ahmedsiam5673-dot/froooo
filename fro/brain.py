"""The AI part: Claude answers anything that is not a built-in command."""
import datetime as dt
import logging

from .settings import settings

log = logging.getLogger("fro.brain")

SYSTEM = (
    "You are Fro, a friendly voice assistant living on the user's Windows PC, like Siri. "
    "The user's name is {name}. Right now it is {now}. "
    "Your replies are spoken aloud and shown in a small chat, so keep them short (1-3 sentences) "
    "unless the user asks for detail. Never use markdown, bullet points, tables or emojis. "
    "Reply in the same language the user speaks (English, Bangla, Hindi, ...). "
    "If something needs real PC control that you cannot do, say so briefly and suggest the exact "
    "voice command to try (for example 'open chrome', 'set a timer for 10 minutes'). "
    "{facts}"
)

NO_KEY = (
    "I can run my PC commands without AI, but for general questions I need an Anthropic API key. "
    "Please add it in Settings."
)


class Brain:
    def __init__(self, store):
        self.store = store
        self.history = []
        self._client = None
        self._key = None

    @property
    def available(self) -> bool:
        return bool(settings.get("api_key"))

    def _get_client(self):
        key = settings.get("api_key")
        if not key:
            return None
        if self._client is None or key != self._key:
            import anthropic

            self._client = anthropic.Anthropic(api_key=key)
            self._key = key
        return self._client

    def _system(self):
        facts = self.store.facts()
        facts_text = ("Things the user told you to remember: " + "; ".join(facts) + ".") if facts else ""
        return SYSTEM.format(
            name=settings.get("user_name"),
            now=dt.datetime.now().strftime("%A %d %B %Y, %H:%M"),
            facts=facts_text,
        )

    def ask(self, text, image=None, remember=True) -> str:
        """image is (media_type, base64_data) or None."""
        try:
            client = self._get_client()
        except Exception as e:
            log.warning("Claude client error: %s", e)
            return "I couldn't start my AI brain. Please check the API key in Settings."
        if client is None:
            return NO_KEY

        if image:
            content = [
                {"type": "image", "source": {"type": "base64", "media_type": image[0], "data": image[1]}},
                {"type": "text", "text": text},
            ]
        else:
            content = text
        messages = (self.history if remember else []) + [{"role": "user", "content": content}]
        try:
            response = client.messages.create(
                model=settings.get("model"),
                max_tokens=500,
                system=self._system(),
                messages=messages,
            )
            reply = "".join(b.text for b in response.content if b.type == "text").strip()
        except Exception as e:
            log.warning("Claude request failed: %s", e)
            msg = str(e)
            if "401" in msg or "authentication" in msg.lower():
                return "My AI brain rejected the API key. Please check it in Settings."
            return "Sorry, I couldn't reach my AI brain. Check your internet connection."
        if remember:
            self.history.append({"role": "user", "content": text if not image else "[sent an image] " + text})
            self.history.append({"role": "assistant", "content": reply})
            self.history = self.history[-14:]
            while self.history and self.history[0]["role"] != "user":
                self.history.pop(0)
        return reply
