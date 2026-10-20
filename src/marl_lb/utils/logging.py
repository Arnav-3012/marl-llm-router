"""CSV logging for training and evaluation runs. Tier B."""

from __future__ import annotations

import csv
from pathlib import Path


class CsvLogger:
    """Append one row per .log() call; the header comes from the first row's keys."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._fields: list[str] | None = None

    def log(self, row: dict) -> None:
        new = self._fields is None
        if new:
            self._fields = list(row)
        with open(self.path, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=self._fields)
            if new:
                w.writeheader()
            w.writerow(row)
