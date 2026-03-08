"""
Telegram Alert Bot
Sends formatted trading alerts via Telegram with signal details,
key levels, and suggested risk management.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from orderflow_system.signals.aggregator import AggregatedSignal
from orderflow_system.signals.profile_framing import DailyBias
from orderflow_system.data.models import Side, TradeState, TradePhase

logger = logging.getLogger(__name__)


class TelegramAlertBot:
    """
    Sends trading alerts to a Telegram chat.
    Requires: pip install python-telegram-bot
    Set bot_token and chat_id in config/settings.py
    """

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self._bot = None
        self._enabled = bool(bot_token and chat_id)

    async def initialize(self):
        if not self._enabled:
            logger.warning(
                "Telegram bot not configured — alerts will be logged only. "
                "Set TELEGRAM bot_token and chat_id in config/settings.py"
            )
            return

        try:
            from telegram import Bot
            self._bot = Bot(token=self.bot_token)
            me = await self._bot.get_me()
            logger.info(f"Telegram bot connected: @{me.username}")
        except ImportError:
            logger.warning("python-telegram-bot not installed. Alerts logged only.")
            self._enabled = False
        except Exception as e:
            logger.error(f"Failed to initialize Telegram bot: {e}")
            self._enabled = False

    async def send_signal_alert(
        self,
        instrument: str,
        agg_signal: AggregatedSignal,
        bias: Optional[DailyBias] = None,
        trade: Optional[TradeState] = None,
    ):
        """Send a formatted alert for a trading signal."""
        direction = "🟢 LONG" if agg_signal.direction == Side.BUY else "🔴 SHORT"

        # Action-specific emoji and header
        action_map = {
            "enter": "🎯 ENTRY SIGNAL",
            "break_even": "🔒 BREAK EVEN",
            "trail": "📈 TRAIL UPDATE",
            "exit": "🚪 EXIT SIGNAL",
            "exit_warning": "⚠️ EXIT WARNING",
            "alert_only": "📊 ALERT",
        }
        header = action_map.get(agg_signal.action, "📊 SIGNAL")

        # Build message
        lines = [
            f"━━━ {header} ━━━",
            f"📌 {instrument} | {direction}",
            f"💪 Score: {agg_signal.composite_score:.0f}/100",
            "",
        ]

        # Signal details
        for sig in agg_signal.signals:
            sig_type = sig.signal_type.value.upper().replace("_", " ")
            lines.append(f"🔍 {sig_type} @ {sig.price_level:.2f} (str: {sig.strength:.0f})")
            if sig.details:
                for k, v in sig.details.items():
                    lines.append(f"   • {k}: {v}")

        lines.append("")

        # Entry action details
        if agg_signal.action == "enter":
            lines.extend([
                "📊 TRADE SETUP:",
                f"   Entry: ~{agg_signal.signals[0].price_level:.2f}" if agg_signal.signals else "",
                f"   Stop Loss: {agg_signal.suggested_sl:.2f}",
                f"   Take Profit: {agg_signal.suggested_tp:.2f}",
            ])
            if agg_signal.suggested_sl and agg_signal.signals:
                entry = agg_signal.signals[0].price_level
                risk = abs(entry - agg_signal.suggested_sl)
                reward = abs(agg_signal.suggested_tp - entry)
                if risk > 0:
                    lines.append(f"   R:R = 1:{reward/risk:.1f}")

        elif agg_signal.action == "break_even" and trade:
            lines.append(f"🔒 Move SL to {trade.break_even_price:.2f}")

        elif agg_signal.action == "trail" and trade:
            lines.append(f"📈 Trail SL to {trade.trail_stop:.2f}")

        lines.append("")

        # Bias context
        if bias:
            bias_emoji = {
                "long": "🟢", "short": "🔴",
                "neutral": "⚪", "warning": "🟠"
            }
            b_emoji = bias_emoji.get(bias.direction.value, "⚪")
            lines.extend([
                f"📉 DAILY BIAS: {b_emoji} {bias.direction.value.upper()} ({bias.confidence:.0f}%)",
                f"   Profile: {bias.profile_shape}",
                f"   POC: {bias.poc:.2f} | VAH: {bias.vah:.2f} | VAL: {bias.val:.2f}",
            ])
            if bias.merged_vah:
                lines.append(f"   Merged: VAH={bias.merged_vah:.2f}, VAL={bias.merged_val:.2f}")

        lines.extend(["", f"📝 {agg_signal.notes}", "━━━━━━━━━━━━━━━━━━━━"])

        message = "\n".join(lines)

        # Send via Telegram
        if self._enabled and self._bot:
            try:
                await self._bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                    parse_mode=None,  # Plain text for reliability
                )
                logger.info(f"Alert sent to Telegram: {header} {instrument}")
            except Exception as e:
                logger.error(f"Failed to send Telegram alert: {e}")
                logger.info(f"Alert (local):\n{message}")
        else:
            # Log to console when Telegram not configured
            logger.info(f"ALERT:\n{message}")

    async def send_daily_bias_update(self, instrument: str, bias: DailyBias):
        """Send daily bias summary at session open."""
        bias_emoji = {
            "long": "🟢", "short": "🔴",
            "neutral": "⚪", "warning": "🟠"
        }
        b_emoji = bias_emoji.get(bias.direction.value, "⚪")

        lines = [
            "━━━ 📊 DAILY BIAS UPDATE ━━━",
            f"📌 {instrument}",
            f"🧭 Bias: {b_emoji} {bias.direction.value.upper()} ({bias.confidence:.0f}%)",
            f"📐 Shape: {bias.profile_shape}",
            f"   POC: {bias.poc:.2f}",
            f"   VAH: {bias.vah:.2f}",
            f"   VAL: {bias.val:.2f}",
        ]

        if bias.lvn_levels:
            lines.append(f"   LVN: {', '.join(f'{l:.2f}' for l in bias.lvn_levels)}")

        if bias.merged_vah:
            lines.append(f"   Merged VAH: {bias.merged_vah:.2f}")
            lines.append(f"   Merged VAL: {bias.merged_val:.2f}")

        lines.extend(["", "🎯 QUALIFIED LEVELS:"])
        for lv in bias.qualified_levels:
            dir_str = "LONG" if lv.direction == Side.BUY else "SHORT"
            lines.append(
                f"   {'🟢' if lv.direction == Side.BUY else '🔴'} "
                f"{lv.level_type.value.upper()} @ {lv.price:.2f} → {dir_str} "
                f"(str: {lv.strength:.0f})"
            )

        lines.extend([
            "",
            f"📝 {bias.notes}",
            "━━━━━━━━━━━━━━━━━━━━",
        ])

        message = "\n".join(lines)

        if self._enabled and self._bot:
            try:
                await self._bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                )
            except Exception as e:
                logger.error(f"Failed to send bias update: {e}")
                logger.info(f"Bias (local):\n{message}")
        else:
            logger.info(f"BIAS UPDATE:\n{message}")
