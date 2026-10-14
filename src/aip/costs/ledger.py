"""Unit economics from usage_cost_record documents (FR37, BR12). All money is Decimal; no prices are assumed."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

COMPLETED = {"completed_with_output", "completed_abstained", "completed_no_useful_signal"}


def total_cost(records: Iterable[Mapping[str, Any]], currency: str) -> Decimal:
    total = Decimal("0")
    for record in records:
        for cost in record["costs"]:
            if cost["currency"] != currency:
                raise ValueError(f"mixed currency {cost['currency']} in a {currency} total; convert upstream")
            total += Decimal(cost["amount"])
    return total


def cost_per_comparable_run(
    records: Iterable[Mapping[str, Any]], comparable_class: str, currency: str
) -> Decimal | None:
    """All attributed cost in the class (failed runs included) / completed runs (abstained and no-signal included)."""
    in_class = [
        r for r in records if r["subject"]["subject_type"] == "run" and r["comparable_run_class"] == comparable_class
    ]
    completed = [r for r in in_class if r["run_outcome"] in COMPLETED]
    if not completed:
        return None
    return total_cost(in_class, currency) / len(completed)


@dataclass(frozen=True)
class ContributionInputs:
    r_software: Decimal
    r_data: Decimal
    c_compute: Decimal
    c_models: Decimal
    c_storage: Decimal
    c_review: Decimal
    c_support: Decimal
    c_source: Decimal
    c_destination: Decimal


def contribution(x: ContributionInputs) -> Decimal:
    return (
        x.r_software
        + x.r_data
        - x.c_compute
        - x.c_models
        - x.c_storage
        - x.c_review
        - x.c_support
        - x.c_source
        - x.c_destination
    )


def net_data_revenue_cpm(billable_impressions: int, data_cpm: Decimal, net_share: Decimal) -> Decimal:
    if not Decimal("0") <= net_share <= Decimal("1"):
        raise ValueError("net_share must be between 0 and 1")
    return Decimal(billable_impressions) / Decimal(1000) * data_cpm * net_share


def break_even_runs(period_fixed_cost: Decimal, contribution_per_run: Decimal) -> Decimal | None:
    """None when contribution per run is zero or negative: no break-even volume exists."""
    if contribution_per_run <= 0:
        return None
    return period_fixed_cost / contribution_per_run
