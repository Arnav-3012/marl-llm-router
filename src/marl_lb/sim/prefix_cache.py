"""Prefix cache of one server: which conversations' earlier turns it still holds. Tier A.

After a request finishes, its whole conversation so far (prompt + answer tokens) is stored under
its conversation id. A later turn that re-sends the history (history_included, ADR-009) finds up
to that many prompt tokens already computed. Capacity is in tokens; the least recently used
conversation is evicted first.
"""

from __future__ import annotations

from collections import OrderedDict


class PrefixCache:
    def __init__(self, capacity_tokens: int):
        self.capacity = capacity_tokens
        self._store: OrderedDict[int, int] = OrderedDict()  # conv_id -> cached tokens, LRU first
        self.used = 0

    def hit_tokens(self, req, touch: bool = False) -> int:
        """Prompt tokens of `req` already cached here (0 for a first turn or a turn without
        history).
        """
        if req.turn_index == 0 or not req.history_included:
            return 0
        cached = self._store.get(req.conv_id)
        if cached is None:
            return 0
        if touch:
            self._store.move_to_end(req.conv_id)
        return min(req.prompt_tokens, cached)

    def insert(self, req) -> None:
        """Store the conversation up to and including `req`'s answer; evict LRU to fit."""
        tokens = req.prompt_tokens + req.output_tokens
        if tokens > self.capacity:
            return
        self.used -= self._store.pop(req.conv_id, 0)
        self._store[req.conv_id] = tokens
        self.used += tokens
        while self.used > self.capacity:
            _, evicted = self._store.popitem(last=False)
            self.used -= evicted
