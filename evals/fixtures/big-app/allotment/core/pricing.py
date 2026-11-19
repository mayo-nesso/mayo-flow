"""Season price of a plot for a member, in cents.

Rates come from the 2026 committee decision (see the archived plot_pricing
spec): a per-square-metre rate, a flat water surcharge, and a concession
discount applied last, rounded down to whole cents.
"""
RATE_CENTS_PER_M2 = 45
WATER_SURCHARGE_CENTS = 1500
MINIMUM_CENTS = 2500
CONCESSION_PERCENT = 40


def price_cents(plot, member):
    base = max(plot.size_m2 * RATE_CENTS_PER_M2, MINIMUM_CENTS)
    if plot.has_water:
        base += WATER_SURCHARGE_CENTS
    if member.concession:
        base = base * (100 - CONCESSION_PERCENT) // 100
    return base
