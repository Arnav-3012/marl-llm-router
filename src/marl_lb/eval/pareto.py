"""Pareto frontier of (cost, latency) points, both to be minimised. Tier A."""

from __future__ import annotations


def pareto_front(points: list) -> list:
    """Indices of the non-dominated points of [(cost, latency), ...], in input order.

    A point is dominated if another is no worse in both coordinates and strictly better in at least
    one.
    Exact duplicates do not dominate each other, so both stay on the frontier.
    """
    keep = []
    for i, (ci, li) in enumerate(points):
        dominated = any(
            (cj <= ci and lj <= li) and (cj < ci or lj < li)
            for j, (cj, lj) in enumerate(points)
            if j != i
        )
        if not dominated:
            keep.append(i)
    return keep
