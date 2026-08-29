from decimal import Decimal, ROUND_HALF_UP


def d(value) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    return Decimal(str(value))


def to_decimal(value, places: int = 2) -> Decimal:
    quantizer = Decimal(10) ** -places
    return Decimal(str(value)).quantize(quantizer, rounding=ROUND_HALF_UP)


def krw_to_usd(krw: Decimal, rate: Decimal) -> Decimal:
    return krw / rate
