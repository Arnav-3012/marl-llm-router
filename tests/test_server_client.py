"""Streaming client and mock server (Sh.L1)."""

import asyncio

from marl_lb.router.mock import MockLlamaServer, start_http
from marl_lb.router.server_client import HttpTransport, LlamaClient
from tests.helpers import FAST, SLOW
from tests.router_helpers import SCALE, mock_stack


# ---- client ------------------------------------------------------------------------------------
def test_client_streams_tokens_and_measures_ttft_and_tpot_in_process():
    mocks, backends, client = mock_stack()
    comp = asyncio.run(client.complete(backends[0].url, list(range(100)), 8))
    assert comp.n_tokens == 8 and comp.ttft_s > 0 and comp.tpot_s > 0
    assert comp.t_send < comp.t_first < comp.t_done and comp.timings["predicted_n"] == 8


def test_client_parses_the_sse_stream_of_a_real_http_server():
    server = MockLlamaServer(FAST, SCALE)
    url, stop = start_http(server)

    async def go():
        client = LlamaClient(HttpTransport(timeout_s=10))
        try:
            ok = await client.health(url)
            comp = await client.complete(url, list(range(50)), 5)
            down = await client.health("http://127.0.0.1:9")
        finally:
            await client.transport.aclose()
        return ok, comp, down

    try:
        ok, comp, down = asyncio.run(go())
    finally:
        stop()
    assert ok is True and down is False
    assert comp.n_tokens == 5 and comp.text.count("t") == 5


def test_mock_prefix_cache_makes_a_repeated_prompt_prefill_faster():
    async def run():
        m = MockLlamaServer(SLOW, 1.0)  # real time: 1 token decoded, so prefill dominates
        prompt = list(range(300))
        t = {}
        for key in ("cold", "warm"):
            t0 = asyncio.get_event_loop().time()
            async for chunk in m.generate({"prompt": prompt, "n_predict": 1, "cache_prompt": True}):
                if not chunk["stop"]:
                    t[key] = asyncio.get_event_loop().time() - t0
                    break
            async for _ in m.generate({"prompt": prompt, "n_predict": 1}):  # drain and store
                pass
        return t

    t = asyncio.run(run())
    assert t["warm"] < t["cold"]
