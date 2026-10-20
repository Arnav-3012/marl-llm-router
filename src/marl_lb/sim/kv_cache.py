"""KV-cache token budget of one server. Tier A.

A request reserves prompt + output tokens when it starts being served and gives them back when it
finishes. The budget is what limits how many requests can be in service together besides the
slot limit; fullness feeds the observation and the KV reward term (ADR-014).
"""

from __future__ import annotations


class KVCache:
    def __init__(self, budget_tokens: int):
        if budget_tokens <= 0:
            raise ValueError("budget_tokens must be positive")
        self.budget = budget_tokens
        self.used = 0
        self._held: dict[int, int] = {}

    def can_admit(self, tokens: int) -> bool:
        return self.used + tokens <= self.budget

    def admit(self, req_id: int, tokens: int) -> None:
        if req_id in self._held:
            raise ValueError(f"request {req_id} already holds KV")
        if not self.can_admit(tokens):
            raise ValueError("KV budget exceeded")
        self._held[req_id] = tokens
        self.used += tokens

    def release(self, req_id: int) -> None:
        self.used -= self._held.pop(req_id)  # KeyError if the request holds nothing

    def fullness(self) -> float:
        return self.used / self.budget
