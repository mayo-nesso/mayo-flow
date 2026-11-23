import unittest

from allotment.core.models import Member, Plot
from allotment.core.pricing import price_cents


def plot(size, water=False):
    return Plot(1, "A1", size, water)


def member(concession=False):
    return Member(1, "Ines", concession, None)


class PricingTest(unittest.TestCase):
    def test_rate_per_m2(self):
        self.assertEqual(price_cents(plot(100), member()), 4500)

    def test_minimum(self):
        self.assertEqual(price_cents(plot(10), member()), 2500)

    def test_water_surcharge(self):
        self.assertEqual(price_cents(plot(100, True), member()), 6000)

    def test_concession_last_rounded_down(self):
        self.assertEqual(price_cents(plot(101, True), member(True)), 3627)
