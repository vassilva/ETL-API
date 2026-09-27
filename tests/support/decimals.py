from decimal import Decimal, ROUND_HALF_UP


def decimal_2(value):
    return Decimal(str(value)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )
