"""A stand-in for llama-server, for tests and rehearsals without real models. Tier B.

Speaks the part of the llama-server API the router uses (GET /health, streamed POST /completion
with one SSE chunk per token and a final chunk carrying timings) and takes its time from the
calibrated service model (calibration.json: a, q, r, t0, k, max_batch), multiplied by `time_scale`
so a test that would take a minute finishes in a second. It is a mock: it shows the router works,
never what a real server does.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse


class MockLlamaServer:
    def __init__(self, cls: dict, time_scale: float = 0.01, name: str = "mock"):
        self.cls, self.scale, self.name = cls, time_scale, name
        self.active = 0
        self.waiting = 0
        self._sem: asyncio.Semaphore | None = None
        self._last_prompt: dict[int, list] = {}  # first token id -> last prompt seen (prefix cache)
        self.app = self._build_app()

    def _slots(self) -> asyncio.Semaphore:
        if self._sem is None:  # created inside the running loop
            self._sem = asyncio.Semaphore(int(self.cls["max_batch"]))
        return self._sem

    def _prefill_s(self, prompt: list, cache_prompt: bool) -> tuple[float, int]:
        cached = 0
        if cache_prompt and prompt and isinstance(prompt[0], int):
            prev = self._last_prompt.get(prompt[0], [])
            while cached < min(len(prev), len(prompt)) and prev[cached] == prompt[cached]:
                cached += 1
        effective = (len(prompt) - cached) + self.cls["cached_token_cost_ratio"] * cached
        q = self.cls.get("prefill_quad", 0.0)
        return self.cls["a"] * effective + q * effective**2, cached

    async def generate(self, body: dict) -> AsyncIterator[dict]:
        """The chunks of one streamed completion (also usable in-process, without HTTP)."""
        prompt = body["prompt"]
        n_predict = int(body.get("n_predict", 16))
        prompt_ids = prompt if isinstance(prompt, list) else list(range(len(str(prompt)) // 4 + 1))
        self.waiting += 1
        async with self._slots():
            self.waiting -= 1
            self.active += 1
            try:
                t_start = time.perf_counter()
                pf_s, cached = self._prefill_s(prompt_ids, bool(body.get("cache_prompt", True)))
                await asyncio.sleep(pf_s * self.scale * (1 + 0.1 * (self.active - 1)))
                for n in range(n_predict):
                    step = (self.cls["t0"] + self.cls["k"] * self.active) / max(self.active, 1)
                    await asyncio.sleep(step * self.scale)
                    yield {"content": f"t{n} ", "stop": False}
                if prompt_ids:
                    self._last_prompt[prompt_ids[0]] = prompt_ids
                yield {
                    "stop": True,
                    "timings": {
                        "prompt_n": len(prompt_ids) - cached,
                        "cache_n": cached,
                        "prompt_ms": pf_s * 1e3,
                        "predicted_n": n_predict,
                        "total_ms": (time.perf_counter() - t_start) * 1e3,
                    },
                }
            finally:
                self.active -= 1

    def _build_app(self) -> FastAPI:
        app = FastAPI()

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        @app.post("/completion")
        async def completion(request: Request):
            body = await request.json()
            if not body.get("stream", False):
                return JSONResponse({"error": "mock supports stream=true only"}, status_code=400)

            async def sse():
                async for chunk in self.generate(body):
                    yield f"data: {json.dumps(chunk)}\n\n"

            return StreamingResponse(sse(), media_type="text/event-stream")

        return app


def start_http(server: MockLlamaServer, host: str = "127.0.0.1") -> tuple[str, callable]:
    """Serve one mock on an ephemeral local port in a thread; returns (url, stop)."""
    import uvicorn

    config = uvicorn.Config(server.app, host=host, port=0, log_level="error")
    srv = uvicorn.Server(config)
    thread = threading.Thread(target=srv.run, daemon=True)
    thread.start()
    while not srv.started:
        time.sleep(0.01)
    port = srv.servers[0].sockets[0].getsockname()[1]

    def stop() -> None:
        srv.should_exit = True
        thread.join(timeout=5)

    return f"http://{host}:{port}", stop
