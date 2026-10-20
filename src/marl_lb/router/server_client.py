"""Async client for llama-server: streamed completions with timings, and health. Tier B.

A Transport does the byte work (HttpTransport for real servers, InProcessTransport for a mock
without sockets), so the router code is the same for both. Every streamed chunk is one token, as in
the profiling client (profiling/bench_server.py).
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field

import httpx


@dataclass
class Completion:
    t_send: float
    t_first: float
    t_done: float
    n_tokens: int
    text: str
    timings: dict = field(default_factory=dict)

    @property
    def ttft_s(self) -> float:
        return self.t_first - self.t_send

    @property
    def tpot_s(self) -> float:
        """Mean seconds per token after the first (0 for a one-token answer)."""
        return (self.t_done - self.t_first) / (self.n_tokens - 1) if self.n_tokens > 1 else 0.0


class HttpTransport:
    def __init__(self, timeout_s: float = 600.0):
        self.client = httpx.AsyncClient(timeout=timeout_s)

    async def health(self, url: str) -> bool:
        try:
            r = await self.client.get(f"{url}/health", timeout=5.0)
            return r.status_code == 200 and r.json().get("status") == "ok"
        except (httpx.HTTPError, ValueError):
            return False

    async def stream(self, url: str, body: dict) -> AsyncIterator[dict]:
        async with self.client.stream("POST", f"{url}/completion", json=body) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    yield json.loads(line[6:])

    async def aclose(self) -> None:
        await self.client.aclose()


class InProcessTransport:
    """Calls MockLlamaServer objects directly (url -> mock), no sockets."""

    def __init__(self, mocks: dict):
        self.mocks = mocks

    async def health(self, url: str) -> bool:
        return url in self.mocks

    async def stream(self, url: str, body: dict) -> AsyncIterator[dict]:
        async for chunk in self.mocks[url].generate(body):
            yield chunk

    async def aclose(self) -> None:
        return None


class LlamaClient:
    def __init__(self, transport, clock: Callable[[], float] = time.perf_counter):
        self.transport, self.clock = transport, clock

    async def health(self, url: str) -> bool:
        return await self.transport.health(url)

    async def complete(
        self,
        url: str,
        prompt,
        n_predict: int,
        cache_prompt: bool = True,
        on_first: Callable[[float], None] | None = None,
        on_token: Callable[[int, float], None] | None = None,
    ) -> Completion:
        """One streamed /completion call. on_first(t) fires at the first token, on_token(n, t) at
        every token (n counts from 1)."""
        body = {
            "prompt": prompt,
            "n_predict": n_predict,
            "temperature": 0,
            "cache_prompt": cache_prompt,
            "stream": True,
        }
        t_send = self.clock()
        t_first, n, parts, final = None, 0, [], {}
        async for chunk in self.transport.stream(url, body):
            if chunk.get("stop"):
                final = chunk
                break
            n += 1
            now = self.clock()
            if t_first is None:
                t_first = now
                if on_first:
                    on_first(now)
            if on_token:
                on_token(n, now)
            parts.append(chunk.get("content", ""))
        if t_first is None:
            raise RuntimeError(f"{url}: no tokens streamed")
        return Completion(
            t_send, t_first, self.clock(), n, "".join(parts), final.get("timings", {})
        )
