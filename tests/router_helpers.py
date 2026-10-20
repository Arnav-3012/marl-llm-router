"""Shared builders for the live router tests (mock servers only)."""

from marl_lb.router.events import EventLog
from marl_lb.router.mock import MockLlamaServer
from marl_lb.router.observation import LiveCluster
from marl_lb.router.policy_router import PolicyRouter
from marl_lb.router.server_client import InProcessTransport, LlamaClient
from tests.helpers import CLASSES, make_params

SCALE = 0.002  # mock time scale: a 1 s request takes 2 ms


class Backend:
    def __init__(self, name, cls_name, url):
        self.name, self.class_name, self.url = name, cls_name, url


def mock_stack(layout=("fast", "slow"), scale=SCALE):
    mocks = {
        f"mock://{i}": MockLlamaServer(CLASSES[c], scale, f"m{i}") for i, c in enumerate(layout)
    }
    backends = [Backend(f"s{i}", c, u) for i, (c, u) in enumerate(zip(layout, mocks, strict=True))]
    return mocks, backends, LlamaClient(InProcessTransport(mocks))


def make_router(policy, layout=("fast", "slow"), scale=SCALE, **param_kw):
    mocks, backends, client = mock_stack(layout, scale)
    params = make_params(layout, **param_kw)
    cluster = LiveCluster(params, CLASSES, 50.0)
    return PolicyRouter(backends, cluster, policy, client, __import__("time").perf_counter,
                        EventLog(), seed=0, decision_dt=0.1 * scale), mocks  # fmt: skip
