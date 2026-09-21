"""Telegram routing for atlas alerts.

The repo already ships a Telegram bot class for signal alerts, but the atlas
alert engine is separate — this is the bridge. Design decisions:

* Routing is per rule: an alert is sent only when the rule that produced it
  lists ``"telegram"`` in its ``channels`` *and* a bot token + chat id exist.
* One message per alert, plain text (no parse mode) — Telegram rejects
  unrelated markdown far too often to be worth the flair.
* A small minimum interval between sends stops an alert storm (a sweep burst
  can produce a dozen alerts in a second) from being rate-limited by Telegram
  and losing the tail.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

_SEVERITY_ICON = {"critical": "🚨", "warning": "⚠️", "info": "📊"}


def _with_context(alert: dict[str, Any], text: str) -> str:
    """§147: append a rule's evidence snapshot to whatever the channel sends.

    Appended, never substituted — the message stays first, so a lock-screen preview still reads as
    the alert itself, and a rule without a snapshot is byte-for-byte what it always was. This is the
    one appender: ``alerts.notification_text`` delegates here for a whole-alert render.
    """
    block = str(alert.get("context") or "").strip()
    if not block:
        return text
    return (text.rstrip() + "\n" + block) if text.strip() else block


class TelegramNotifier:
    """Formats and sends atlas alerts to Telegram, with a per-send throttle."""

    def __init__(
        self,
        bot_token: str = "",
        chat_id: str = "",
        enabled: bool = True,
        min_interval_s: float = 1.5,
        transport: Optional[Callable[[str], Awaitable[bool]]] = None,
    ) -> None:
        self.bot_token = str(bot_token or "").strip()
        self.chat_id = str(chat_id or "").strip()
        self.enabled = bool(enabled and self.bot_token and self.chat_id) or transport is not None
        self.min_interval_s = float(min_interval_s)
        self.sent = 0
        self.failed = 0
        self.throttled = 0
        self.last_error = ""
        self._bot = None
        self._ready = False
        self._last_sent = 0.0
        self._transport = transport          # tests / embedding inject a sender

    # ── lifecycle ─────────────────────────────────────────────
    async def start(self) -> bool:
        """Connect the bot. Returns False when not configured or unavailable."""
        if self._transport is not None:
            self._ready = True
            return True
        if not (self.bot_token and self.chat_id) or not self.enabled:
            return False
        try:
            from telegram import Bot
            self._bot = Bot(token=self.bot_token)
            me = await self._bot.get_me()
            logger.info("atlas Telegram notifier connected: @%s", getattr(me, "username", "?"))
            self._ready = True
            return True
        except ImportError:
            self.last_error = "python-telegram-bot not installed"
            logger.warning("atlas Telegram notifier: %s", self.last_error)
        except Exception as exc:
            from orderflow_system.desktop.logs import redact

            # SEC-01: same exception family as the alerts bot — and `last_error` is served by
            # the UI stats, so it must not carry the token either.
            self.last_error = redact(f"{type(exc).__name__}: {exc}")
            logger.error("atlas Telegram notifier failed to connect: %s", self.last_error)
        self._ready = False
        return False

    async def stop(self) -> None:
        # MEM-A1-03: close the bot's HTTP pool before dropping the reference — a started
        # network client is closed by whoever started it, on the engine's stop path. The
        # reference drop alone left one aiohttp/httpx pool per engine restart for the GC.
        bot, self._bot = self._bot, None
        self._ready = False
        if bot is not None:
            try:
                await bot.shutdown()
            except Exception:                      # a Telegram outage must not fail the stop
                logger.debug("atlas Telegram bot shutdown failed", exc_info=True)

    @property
    def ready(self) -> bool:
        return self._ready

    # ── sending ───────────────────────────────────────────────
    @staticmethod
    def format(alert: dict[str, Any]) -> str:
        """One compact, plain-text message per alert."""
        icon = _SEVERITY_ICON.get(str(alert.get("severity", "")).lower(), "📊")
        ts = int(alert.get("ts_ms") or time.time() * 1000)
        stamp = time.strftime("%H:%M:%S", time.localtime(ts / 1000))
        kind = str(alert.get("kind", "alert")).replace("_", " ")
        lines = [
            f"{icon} {str(alert.get('symbol', '')).upper()} · {kind.upper()}",
            str(alert.get("message") or alert.get("name") or ""),
            f"rule: {alert.get('name', '')} · {stamp}",
        ]
        return _with_context(alert, "\n".join(l for l in lines if l.strip()))

    async def send(self, alert: dict[str, Any], force: bool = False) -> bool:
        """Send one alert. Returns True when it reached Telegram."""
        if not self.enabled or not self._ready:
            return False
        now = time.monotonic()
        if not force and self.min_interval_s > 0 and now - self._last_sent < self.min_interval_s:
            self.throttled += 1
            return False
        text = self.format(alert)
        try:
            if self._transport is not None:
                ok = bool(await self._transport(text))
            else:
                await self._bot.send_message(chat_id=self.chat_id, text=text, parse_mode=None)
                ok = True
            self._last_sent = now
            if ok:
                self.sent += 1
            else:
                self.failed += 1
            return ok
        except Exception as exc:
            self.failed += 1
            self.last_error = f"{type(exc).__name__}: {exc}"
            logger.warning("atlas Telegram send failed: %s", self.last_error)
            return False

    def stats(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "ready": self._ready,
            "sent": self.sent,
            "failed": self.failed,
            "throttled": self.throttled,
            "last_error": self.last_error,
        }


# ══════════════════════════════════════════════════════════════
# ntfy.sh — phone push with no account, no key: just a topic name
# ══════════════════════════════════════════════════════════════

_NTFY_PRIORITY = {"critical": "urgent", "warning": "high", "info": "default"}
_NTFY_TAGS = {"critical": "rotating_light", "warning": "warning", "info": "chart_with_upwards_trend"}


class NtfyNotifier:
    """Push atlas alerts to a phone through ntfy (https://ntfy.sh).

    The whole setup is: install the ntfy app, subscribe to a topic name, type the
    same topic here. No account, no API key, nothing to leak — which is why it is
    the easiest channel to offer a new user. A self-hosted server works too: set
    ``server`` to your own base URL.
    """

    def __init__(
        self,
        server: str = "https://ntfy.sh",
        topic: str = "",
        enabled: bool = True,
        min_interval_s: float = 1.5,
        timeout_s: float = 8.0,
        transport: Optional[Callable[[str, dict[str, str], str], Awaitable[bool]]] = None,
    ) -> None:
        self.server = (str(server or "https://ntfy.sh").strip().rstrip("/")) or "https://ntfy.sh"
        if not self.server.startswith(("http://", "https://")):
            self.server = "https://" + self.server
        self.topic = str(topic or "").strip().strip("/")
        self.enabled = bool(enabled and self.topic) or transport is not None
        self.min_interval_s = float(min_interval_s)
        self.max_interval_s = 60.0
        self.rate_limited = 0
        self.timeout_s = float(timeout_s)
        self.sent = 0
        self.failed = 0
        self.throttled = 0
        self.last_error = ""
        self._ready = False
        self._last_sent = 0.0
        self._transport = transport

    async def start(self) -> bool:
        self._ready = bool(self.enabled and (self.topic or self._transport))
        if self.enabled and not self.topic and self._transport is None:
            self.last_error = "no topic configured"
        return self._ready

    async def stop(self) -> None:
        self._ready = False

    @property
    def ready(self) -> bool:
        return self._ready

    @property
    def url(self) -> str:
        return f"{self.server}/{self.topic}"

    @staticmethod
    def format(alert: dict[str, Any]) -> tuple[str, dict[str, str], str]:
        """(title, headers, body) — ntfy takes the message in the body and the
        rest as headers, so a notification reads well on a lock screen."""
        severity = str(alert.get("severity", "")).lower()
        kind = str(alert.get("kind", "alert")).replace("_", " ")
        symbol = str(alert.get("symbol", "")).upper()
        title = f"{symbol} · {kind.upper()}"
        headers = {
            "Title": title,
            "Priority": _NTFY_PRIORITY.get(severity, "default"),
            "Tags": _NTFY_TAGS.get(severity, "chart_with_upwards_trend"),
        }
        body = "\n".join(
            line for line in [
                str(alert.get("message") or alert.get("name") or ""),
                f"rule: {alert.get('name', '')}",
            ] if str(line).strip()
        )
        return title, headers, _with_context(alert, body)

    async def send(self, alert: dict[str, Any], force: bool = False) -> bool:
        if not self.enabled or not self._ready:
            return False
        now = time.monotonic()
        if not force and self.min_interval_s > 0 and now - self._last_sent < self.min_interval_s:
            self.throttled += 1
            return False
        _title, headers, body = self.format(alert)
        try:
            if self._transport is not None:
                ok = bool(await self._transport(self.url, headers, body))
            else:
                ok = await asyncio.to_thread(self._post, headers, body)
            self._last_sent = now
            self.sent += 1 if ok else 0
            self.failed += 0 if ok else 1
            return ok
        except Exception as exc:
            self.failed += 1
            self.last_error = f"{type(exc).__name__}: {exc}"
            logger.warning("atlas ntfy send failed: %s", self.last_error)
            return False

    def _post(self, headers: dict[str, str], body: str) -> bool:
        """Blocking POST — ntfy accepts the message as the raw request body.

        ntfy.sh rate-limits free topics (HTTP 429). Rather than hammering it, a 429
        widens this channel's throttle until the service lets messages through
        again — the alert is dropped from the push, never from the log.
        """
        import urllib.error
        import urllib.request

        req = urllib.request.Request(
            self.url,
            data=body.encode("utf-8"),
            headers={**headers, "Content-Type": "text/plain; charset=utf-8"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                if resp.status >= 400:
                    self.last_error = f"HTTP {resp.status}"
                    return False
            if self.rate_limited:
                self.min_interval_s = max(1.5, self.min_interval_s / 2)
            return True
        except urllib.error.HTTPError as exc:
            self.last_error = f"HTTP {exc.code}"
            if exc.code == 429:
                self._note_rate_limited()
            return False

    def _note_rate_limited(self) -> None:
        self.rate_limited += 1
        self.min_interval_s = min(self.max_interval_s, max(1.5, self.min_interval_s * 2))

    def stats(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled, "ready": self._ready, "topic": self.topic,
            "server": self.server, "sent": self.sent, "failed": self.failed,
            "throttled": self.throttled, "rate_limited": self.rate_limited,
            "min_interval_s": round(self.min_interval_s, 2), "last_error": self.last_error,
        }


# ══════════════════════════════════════════════════════════════
# Email (SMTP) — any mailbox; Gmail/Outlook want an app password
# ══════════════════════════════════════════════════════════════

class EmailNotifier:
    """Send atlas alerts as email. Optional, off unless fully configured.

    Kept deliberately plain: STARTTLS on 587 (or implicit TLS on 465), one
    message per alert, no attachments. A mailbox that requires an OAuth flow is
    out of scope — the wizard tells the user to create an app password instead.
    """

    def __init__(
        self,
        host: str = "",
        port: int = 587,
        username: str = "",
        password: str = "",
        to_addrs: str = "",
        from_addr: str = "",
        use_tls: bool = True,
        enabled: bool = True,
        min_interval_s: float = 10.0,
        transport: Optional[Callable[[str, str], Awaitable[bool]]] = None,
    ) -> None:
        self.host = str(host or "").strip()
        self.port = int(port or 587)
        self.username = str(username or "").strip()
        self.password = str(password or "")
        self.to_addrs = [a.strip() for a in str(to_addrs or "").replace(";", ",").split(",") if a.strip()]
        self.from_addr = str(from_addr or "").strip() or self.username
        self.use_tls = bool(use_tls)
        self.enabled = bool(enabled and self.host and self.to_addrs) or transport is not None
        self.min_interval_s = float(min_interval_s)
        self.sent = 0
        self.failed = 0
        self.throttled = 0
        self.last_error = ""
        self._ready = False
        self._last_sent = 0.0
        self._transport = transport

    async def start(self) -> bool:
        self._ready = bool(self.enabled and (self.host or self._transport))
        if self.enabled and not self._configured() and self._transport is None:
            self.last_error = "host / recipient missing"
        return self._ready

    def _configured(self) -> bool:
        return bool(self.host and self.to_addrs)

    async def stop(self) -> None:
        self._ready = False

    @property
    def ready(self) -> bool:
        return self._ready

    @staticmethod
    def format(alert: dict[str, Any]) -> tuple[str, str]:
        severity = str(alert.get("severity", "")).upper() or "INFO"
        kind = str(alert.get("kind", "alert")).replace("_", " ")
        symbol = str(alert.get("symbol", "")).upper()
        subject = f"[OrderFlow] {severity} · {symbol} · {kind}"
        ts = int(alert.get("ts_ms") or time.time() * 1000)
        body_lines = [
            str(alert.get("message") or alert.get("name") or ""),
            "",
            f"symbol:  {symbol}",
            f"kind:    {kind}",
            f"rule:    {alert.get('name', '')}",
            f"severity:{severity.lower()}",
            f"time:    {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts / 1000))}",
            f"price:   {alert.get('price', '')}",
        ]
        return subject, _with_context(alert, "\n".join(body_lines))

    async def send(self, alert: dict[str, Any], force: bool = False) -> bool:
        if not self.enabled or not self._ready:
            return False
        now = time.monotonic()
        if not force and self.min_interval_s > 0 and now - self._last_sent < self.min_interval_s:
            self.throttled += 1
            return False
        subject, body = self.format(alert)
        try:
            if self._transport is not None:
                ok = bool(await self._transport(subject, body))
            else:
                ok = await asyncio.to_thread(self._smtp_send, subject, body)
            self._last_sent = now
            self.sent += 1 if ok else 0
            self.failed += 0 if ok else 1
            return ok
        except Exception as exc:
            self.failed += 1
            self.last_error = f"{type(exc).__name__}: {exc}"
            logger.warning("atlas email send failed: %s", self.last_error)
            return False

    async def send_report(self, subject: str, body: str,
                          attachments: Optional[list[tuple[str, bytes, str]]] = None) -> bool:
        """Send a plain message with optional attachments (name, bytes, mime).

        The storage report's path. Same SMTP transport as an alert — one implementation — and it
        deliberately does not wait for ``start()``: a report is a one-shot send from a periodic
        job, which is exactly when no alert channel was ever started.
        """
        if not self._configured():
            self.last_error = "host / recipient missing"
            return False
        try:
            ok = bool(await asyncio.to_thread(self._smtp_send, subject, body, attachments or []))
            self.sent += 1 if ok else 0
            self.failed += 0 if ok else 1
            return ok
        except Exception as exc:
            self.failed += 1
            self.last_error = f"{type(exc).__name__}: {exc}"
            logger.warning("email report failed: %s", self.last_error)
            return False

    def _smtp_send(self, subject: str, body: str,
                   attachments: Optional[list[tuple[str, bytes, str]]] = None) -> bool:
        import smtplib
        from email.message import EmailMessage

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.from_addr
        msg["To"] = ", ".join(self.to_addrs)
        msg.set_content(body)
        for name, blob, mime in attachments or []:
            maintype, _, subtype = str(mime or "application/octet-stream").partition("/")
            msg.add_attachment(bytes(blob), maintype=maintype or "application",
                               subtype=subtype or "octet-stream", filename=str(name))
        if self.use_tls:
            with smtplib.SMTP(self.host, self.port, timeout=20) as smtp:
                smtp.starttls()
                if self.username:
                    smtp.login(self.username, self.password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP_SSL(self.host, self.port, timeout=20) as smtp:
                if self.username:
                    smtp.login(self.username, self.password)
                smtp.send_message(msg)
        return True

    def stats(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled, "ready": self._ready, "host": self.host,
            "to": ", ".join(self.to_addrs), "sent": self.sent, "failed": self.failed,
            "throttled": self.throttled, "last_error": self.last_error,
        }


# ══════════════════════════════════════════════════════════════
# Hub — one alert, every channel the rule asked for
# ══════════════════════════════════════════════════════════════

class NotifierHub:
    """Fans an alert out to the configured channels.

    The hub is what ``hub.notifier`` points at, so the atlas dispatch code stays
    unchanged: it calls ``send(alert)`` and ``stats()`` and never needs to know
    how many channels exist or which ones are live.
    """

    CHANNELS = ("telegram", "ntfy", "email")

    def __init__(self, **channels: Any) -> None:
        self.channels: dict[str, Any] = {k: v for k, v in channels.items() if v is not None}

    async def start(self) -> dict[str, bool]:
        out: dict[str, bool] = {}
        for name, channel in self.channels.items():
            try:
                out[name] = bool(await channel.start())
            except Exception as exc:                     # pragma: no cover - defensive
                logger.warning("notifier channel %s failed to start: %s", name, exc)
                out[name] = False
        return out

    async def stop(self) -> None:
        for channel in self.channels.values():
            try:
                await channel.stop()
            except Exception:                            # pragma: no cover - defensive
                pass

    def routing(self, alert: dict[str, Any]) -> list[str]:
        """Which channels this alert asks for, intersected with what exists."""
        wanted = [str(c).lower() for c in (alert.get("channels") or ["ui"])]
        return [name for name in self.channels if name in wanted]

    async def send(self, alert: dict[str, Any], force: bool = False) -> dict[str, bool]:
        out: dict[str, bool] = {}
        for name in self.routing(alert):
            try:
                out[name] = bool(await self.channels[name].send(alert, force=force))
            except Exception as exc:                     # pragma: no cover - defensive
                logger.warning("notifier channel %s raised: %s", name, exc)
                out[name] = False
        return out

    async def send_one(self, channel: str, alert: dict[str, Any]) -> dict[str, Any]:
        """Force-send through a single named channel (used by the test buttons)."""
        target = self.channels.get(str(channel).lower())
        if target is None:
            return {"ok": False, "error": f"channel '{channel}' is not configured"}
        try:
            ok = bool(await target.send(alert, force=True))
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        stats = target.stats() if hasattr(target, "stats") else {}
        return {"ok": ok, "channel": channel, "error": "" if ok else stats.get("last_error", "send failed")}

    def stats(self) -> dict[str, Any]:
        return {name: (channel.stats() if hasattr(channel, "stats") else {})
                for name, channel in self.channels.items()}


def build_notifiers(
    telegram_cfg: Optional[dict[str, Any]] = None,
    notify_cfg: Optional[dict[str, Any]] = None,
    telegram_enabled: bool = True,
) -> NotifierHub:
    """Build the hub from the config blocks the desktop stores.

    Every channel is optional; a channel with no credentials simply is not part
    of the hub, so a fresh install runs UI-only and nothing errors.
    """
    telegram_cfg = telegram_cfg or {}
    notify_cfg = notify_cfg or {}
    channels: dict[str, Any] = {}

    token = str(telegram_cfg.get("bot_token") or "").strip()
    chat = str(telegram_cfg.get("chat_id") or "").strip()
    if telegram_enabled and bool(telegram_cfg.get("enabled", True)) and token and chat:
        channels["telegram"] = TelegramNotifier(bot_token=token, chat_id=chat, enabled=True)

    ntfy_cfg = notify_cfg.get("ntfy") or {}
    if bool(ntfy_cfg.get("enabled", False)) and str(ntfy_cfg.get("topic") or "").strip():
        channels["ntfy"] = NtfyNotifier(
            server=str(ntfy_cfg.get("server") or "https://ntfy.sh"),
            topic=str(ntfy_cfg.get("topic") or ""),
            enabled=True,
        )

    email_cfg = notify_cfg.get("email") or {}
    if bool(email_cfg.get("enabled", False)) and str(email_cfg.get("host") or "").strip():
        channels["email"] = EmailNotifier(
            host=str(email_cfg.get("host") or ""),
            port=int(email_cfg.get("port") or 587),
            username=str(email_cfg.get("username") or ""),
            password=str(email_cfg.get("password") or ""),
            to_addrs=str(email_cfg.get("to") or ""),
            from_addr=str(email_cfg.get("from") or ""),
            use_tls=bool(email_cfg.get("use_tls", True)),
            enabled=True,
        )

    return NotifierHub(**channels)
