from decimal import Decimal, ROUND_HALF_UP


def to_decimal(value, places: int = 2) -> Decimal:
    quantizer = Decimal(10) ** -places
    return Decimal(str(value)).quantize(quantizer, rounding=ROUND_HALF_UP)
