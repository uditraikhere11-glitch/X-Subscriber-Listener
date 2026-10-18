"""Conservative, explainable parser for candidate trading posts.

A match is a candidate for human review, never an order instruction. The parser
intentionally refuses text lacking a direction, identifiable symbol, or price cue.
"""
from __future__ import annotations

import re
from typing import Any

DIRECTION_PATTERNS = {
    "BUY": re.compile(r"\b(?:BUY|BOUGHT|LONG|BULLISH)\b", re.I),
    "SELL": re.compile(r"\b(?:SELL|SOLD|SHORT|BEARISH)\b", re.I),
}
SYMBOL_LABEL = re.compile(r"\b(?:SYMBOL|STOCK|SCRIPT|SCRIP|NSE)\s*[:=-]\s*([A-Z][A-Z0-9&._-]{1,19})\b", re.I)
DOLLAR_SYMBOL = re.compile(r"\$([A-Z][A-Z0-9._-]{1,14})\b")
KNOWN_INDICES = ("BANKNIFTY", "MIDCPNIFTY", "FINNIFTY", "NIFTY", "SENSEX", "BANKEX")
PRICE = r"(?:₹|INR\s*)?([0-9][0-9,]*(?:\.[0-9]+)?)"
ENTRY_RE = re.compile(r"\b(?:ENTRY|BUY\s+ABOVE|BUY\s+AT|SELL\s+BELOW|SELL\s+AT|ABOVE|BELOW|CMP)\s*[:=@-]?\s*" + PRICE, re.I)
SL_RE = re.compile(r"\b(?:SL|STOP\s*LOSS|STOPLOSS)\s*[:=@-]?\s*" + PRICE, re.I)
TARGET_RE = re.compile(r"\b(?:TARGET(?:S)?|TGT|TP)\s*(?:[1-5])?\s*[:=@-]?\s*" + PRICE, re.I)
OPTION_RE = re.compile(r"\b(\d{4,6})\s*(CE|PE)\b", re.I)
FUTURE_RE = re.compile(r"\b(?:FUT|FUTURES|FUTURE)\b", re.I)
NEGATED = re.compile(r"\b(?:NOT\s+(?:A\s+)?BUY|NO\s+BUY|AVOID\s+(?:BUY|SELL)|DO\s+NOT\s+(?:BUY|SELL))\b", re.I)


def _price(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value.replace(",", ""))
    except ValueError:
        return None


def extract_symbol(text: str) -> str | None:
    match = SYMBOL_LABEL.search(text.upper()) or DOLLAR_SYMBOL.search(text.upper())
    if match:
        return match.group(1).upper().strip("._-")
    upper = text.upper()
    for index in KNOWN_INDICES:
        if re.search(rf"\b{re.escape(index)}\b", upper):
            return index
    # Deliberately avoid guessing arbitrary uppercase words as ticker symbols.
    return None


def parse_candidate(text: str) -> dict[str, Any] | None:
    if not text or NEGATED.search(text):
        return None
    directions = [name for name, pattern in DIRECTION_PATTERNS.items() if pattern.search(text)]
    if len(directions) != 1:
        return None
    symbol = extract_symbol(text)
    if not symbol:
        return None

    entry_match = ENTRY_RE.search(text)
    sl_match = SL_RE.search(text)
    targets = [_price(m.group(1)) for m in TARGET_RE.finditer(text)]
    targets = [p for p in targets if p is not None]
    entry = _price(entry_match.group(1)) if entry_match else None
    stop_loss = _price(sl_match.group(1)) if sl_match else None
    # A direction and symbol without a price cue is usually commentary, not a signal.
    if entry is None and stop_loss is None and not targets:
        return None

    option = OPTION_RE.search(text)
    instrument = "OPTION" if option else ("FUTURE" if FUTURE_RE.search(text) else "EQUITY_OR_INDEX")
    missing = []
    if entry is None:
        missing.append("entry")
    if stop_loss is None:
        missing.append("stop_loss")
    if not targets:
        missing.append("target")
    populated = sum(value is not None for value in (entry, stop_loss)) + bool(targets)
    confidence = "medium" if populated >= 2 else "low"
    return {
        "candidate": True,
        "parser_version": 1,
        "direction": directions[0],
        "symbol": symbol,
        "instrument": instrument,
        "option_strike": int(option.group(1)) if option else None,
        "option_type": option.group(2).upper() if option else None,
        "entry": entry,
        "stop_loss": stop_loss,
        "targets": targets,
        "confidence": confidence,
        "missing_fields": missing,
        "requires_human_review": True,
        "live_trading_allowed": False,
    }
