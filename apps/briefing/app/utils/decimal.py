from decimal import Decimal, ROUND_HALF_UP


def to_decimal(value, places: int = 2) -> Decimal:
    quantizer = Decimal(10) ** -places
    return Decimal(str(value)).quantize(quantizer, rounding=ROUND_HALF_UP)


def to_percent(value: Decimal, target: Decimal) -> Decimal:
    if target == 0:
        return Decimal(0)
    return to_decimal(Decimal((value - target) / target * 100))


def krw_to_usd(krw: Decimal, rate: Decimal) -> Decimal:
    return krw / rate
