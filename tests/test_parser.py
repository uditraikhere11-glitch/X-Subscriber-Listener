from x_listener.parser import parse_candidate


def test_parses_basic_buy_signal():
    result = parse_candidate("BUY SYMBOL: RELIANCE ENTRY: 1250 SL: 1220 TARGET: 1300")
    assert result is not None
    assert result["direction"] == "BUY"
    assert result["symbol"] == "RELIANCE"
    assert result["entry"] == 1250.0
    assert result["stop_loss"] == 1220.0
    assert result["targets"] == [1300.0]
    assert result["live_trading_allowed"] is False


def test_parses_option_candidate():
    result = parse_candidate("BUY $NIFTY 25000 CE ENTRY 120 SL 95 TARGET 160")
    assert result is not None
    assert result["symbol"] == "NIFTY"
    assert result["instrument"] == "OPTION"
    assert result["option_strike"] == 25000
    assert result["option_type"] == "CE"


def test_rejects_commentary_without_price_fields():
    assert parse_candidate("BUY SYMBOL: RELIANCE looking good today") is None


def test_rejects_negated_call_to_action():
    assert parse_candidate("NOT A BUY SYMBOL: TCS ENTRY: 4000") is None


def test_rejects_ambiguous_direction():
    assert parse_candidate("BUY SYMBOL: TCS ENTRY: 4000 but SELL SYMBOL: INFY") is None


def test_does_not_guess_arbitrary_uppercase_words_as_symbol():
    assert parse_candidate("BUY THIS STOCK ENTRY: 120 SL: 110 TARGET: 140") is None


def test_accepts_missing_fields_but_marks_them_for_review():
    result = parse_candidate("SELL NSE: INFY STOPLOSS: 1480")
    assert result is not None
    assert result["missing_fields"] == ["entry", "target"]
    assert result["requires_human_review"] is True
