# Plot pricing by size

**Status:** done (2026-10-09).

## Goal

Charge per season by plot size instead of a flat fee, as the committee
decided for 2026.

## Decisions

- 45 cents per square metre, minimum 25.00 per season.
- Water access adds a flat 15.00.
- Concession members get 40% off, applied after the surcharge, rounded down
  to whole cents.
- Prices are fixed at booking time (stored on the booking), so a later rate
  change does not move existing bookings.

## Plan

1. `core/pricing.py` with `price_cents(plot, member)` and unit tests.
2. Store `price_cents` on bookings (migration 0002 already has the column).
3. Return the price from the booking API.

## Tests

Rate, minimum, surcharge, concession rounding.
