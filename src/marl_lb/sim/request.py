"""The request record the simulator moves around. Tier B.

Built from a data.traces.StreamRequest by Request.from_stream. The fields after `history_included`
are runtime state that the cluster and servers update.
"""

from __future__ import annotations


class Request:
    __slots__ = (
        "id", "arrival", "prompt_tokens", "output_tokens", "conv_id", "turn_index",
        "history_included", "ttft_target", "tpot_target", "hops", "defers",
        "holder", "server", "status", "cached_tokens", "pf_left", "dec_left",
        "t_enqueue", "t_first", "t_done", "attributed_s", "resident_ticks", "hot_ticks",
        "decisions", "last_holder",
    )  # fmt: skip

    def __init__(self, id, arrival, prompt_tokens, output_tokens, conv_id, turn_index,
                 history_included, ttft_target, tpot_target):  # fmt: skip
        self.id, self.arrival = id, arrival
        self.prompt_tokens, self.output_tokens = prompt_tokens, output_tokens
        self.conv_id, self.turn_index, self.history_included = conv_id, turn_index, history_included
        self.ttft_target, self.tpot_target = ttft_target, tpot_target
        self.hops = self.defers = 0
        self.holder = self.server = self.last_holder = (
            None  # agent index holding it / server index serving it
        )
        self.status = "new"  # new | held | queued | active | done | dropped
        self.cached_tokens = 0  # prompt tokens found in the serving server's prefix cache
        self.pf_left = 0.0  # remaining prefill work, seconds (before interference)
        self.dec_left = output_tokens  # remaining decode tokens
        self.t_enqueue = self.t_first = self.t_done = None
        self.attributed_s = 0.0  # service seconds attributed to this request (ADR-014)
        self.resident_ticks = self.hot_ticks = 0  # ticks holding KV / of those with KV > threshold
        self.decisions: list = []  # decision records of agents that acted on it (ADR-010)

    @classmethod
    def from_stream(cls, i: int, s, ttft_target: float, tpot_target: float) -> Request:
        return cls(i, s.arrival_s, s.prompt_tokens, s.output_tokens, s.conversation_id,
                   s.turn_index, s.history_included, ttft_target, tpot_target)  # fmt: skip

    @property
    def ttft(self) -> float | None:
        return None if self.t_first is None else self.t_first - self.arrival

    @property
    def tpot(self) -> float | None:
        """Mean seconds per output token after the first (0 for one-token answers)."""
        if self.t_done is None or self.t_first is None:
            return None
        n = self.output_tokens - 1
        return (self.t_done - self.t_first) / n if n > 0 else 0.0

    @property
    def e2e(self) -> float | None:
        return None if self.t_done is None else self.t_done - self.arrival

    def sla_met(self) -> bool:
        """Both targets met (a request that never finished has not met them)."""
        return (
            self.status == "done"
            and self.ttft <= self.ttft_target
            and self.tpot <= self.tpot_target
        )
