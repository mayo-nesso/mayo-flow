"""Row-to-object helpers."""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Plot:
    id: int
    code: str
    size_m2: int
    has_water: bool

    @classmethod
    def from_row(cls, row):
        return cls(row["id"], row["code"], row["size_m2"],
                   bool(row["has_water"]))


@dataclass(frozen=True)
class Member:
    id: int
    name: str
    concession: bool
    email: Optional[str]

    @classmethod
    def from_row(cls, row):
        return cls(row["id"], row["name"], bool(row["concession"]),
                   row["email"])


@dataclass(frozen=True)
class Booking:
    id: int
    plot_id: int
    member_id: int
    season: str
    status: str
    price_cents: int
    created_at: str
    cancelled_at: Optional[str]

    @classmethod
    def from_row(cls, row):
        return cls(row["id"], row["plot_id"], row["member_id"],
                   row["season"], row["status"], row["price_cents"],
                   row["created_at"], row["cancelled_at"])
