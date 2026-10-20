"""Q-network, replay buffer, DDQN update (hand-computed batch), masked epsilon-greedy, training
episode.
"""

import numpy as np
import pytest
import torch
import yaml
from torch import nn

from marl_lb.agents.dqn_agent import DQNAgent, epsilon_at
from marl_lb.agents.networks import QNetwork, masked_argmax
from marl_lb.agents.replay_buffer import ReplayBuffer
from marl_lb.config import ROOT
from marl_lb.sim.cluster import Transition
from marl_lb.train.loop import make_agents, run_learning_episode
from tests.helpers import make_cluster, stream_of


def cfg(**kw) -> dict:
    c = yaml.safe_load((ROOT / "configs" / "dqn.yaml").read_text())
    c.update(
        batch_size=1, reward_scale=1.0, gamma=0.5, target_update=1000, epsilon_decay_episodes=10
    )
    c["replay"] = {**c["replay"], "warmup": 1}
    c.update(kw)
    return c


def constant_net(bias):
    """A network whose output ignores its input: Q = bias for every state (so the maths is
    hand-checkable).
    """
    net = nn.Linear(7, 3)
    nn.init.zeros_(net.weight)
    net.bias.data = torch.tensor(bias, dtype=torch.float32)
    return net


def test_network_shape_and_masked_argmax():
    q = QNetwork()(torch.zeros(5, 7))
    assert q.shape == (5, 3)
    best = masked_argmax(torch.tensor([[1.0, 9.0, 3.0]]), torch.tensor([[True, False, True]]))
    assert best.item() == 2  # the highest Q (action 1) is illegal


def test_replay_buffer_capacity_overwrite_and_sample_shapes():
    buf = ReplayBuffer(3)
    for i in range(5):
        buf.add(
            np.full(7, i, np.float32),
            np.ones(3, bool),
            i % 3,
            float(i),
            np.full(7, i + 1, np.float32),
            np.ones(3, bool),
        )
    assert len(buf) == 3
    assert sorted(buf.reward.tolist()) == [2.0, 3.0, 4.0]  # the two oldest were overwritten
    b = buf.sample(8, np.random.default_rng(0))
    assert b["obs"].shape == (8, 7) and b["mask"].shape == (8, 3) and b["action"].shape == (8,)


def test_ddqn_target_is_chosen_by_online_net_and_evaluated_by_target_net():
    ag = DQNAgent(cfg(), seed=0)
    ag.q = constant_net([1.0, 5.0, 3.0])  # online: Q(s) = [1, 5, 3]
    ag.target = constant_net([10.0, 20.0, 5.0])  # target: Q(s') = [10, 20, 5]
    ag.opt = torch.optim.Adam(ag.q.parameters(), lr=0.0)  # inspect the loss only
    ag.buffer.add(
        np.zeros(7, np.float32),
        np.ones(3, bool),
        0,
        2.0,
        np.zeros(7, np.float32),
        np.array([True, False, True]),
    )
    loss, mean_q = ag.learn()
    # next mask hides action 1; online picks action 2 (Q=3); target evaluates it: 5.
    # y = 2 + 0.5 * 5 = 4.5; q_taken = 1.0; Huber(delta 1) = |4.5 - 1| - 0.5 = 3.0
    # (vanilla DQN would take the target's best legal value 10: y = 7, loss 5.5)
    assert mean_q == pytest.approx(1.0) and loss == pytest.approx(3.0)


def test_target_network_syncs_after_the_configured_number_of_steps():
    ag = DQNAgent(cfg(target_update=3), seed=0)
    ag.buffer.add(
        np.zeros(7, np.float32), np.ones(3, bool), 0, 1.0, np.ones(7, np.float32), np.ones(3, bool)
    )
    ag.learn(), ag.learn()
    assert not all(
        torch.equal(a, b) for a, b in zip(ag.q.parameters(), ag.target.parameters(), strict=True)
    )
    ag.learn()
    assert all(
        torch.equal(a, b) for a, b in zip(ag.q.parameters(), ag.target.parameters(), strict=True)
    )


def test_epsilon_greedy_never_picks_an_illegal_action():
    ag = DQNAgent(cfg(), seed=1)
    ag.q = constant_net([0.0, 100.0, 0.0])  # greedy would love action 1
    mask = np.array([True, False, True])
    obs = np.zeros(7, np.float32)
    assert all(ag.act(obs, mask, epsilon=1.0) in (0, 2) for _ in range(200))
    assert {ag.act(obs, mask, epsilon=1.0) for _ in range(200)} == {0, 2}
    assert all(ag.act(obs, mask, epsilon=0.0) in (0, 2) for _ in range(20))


def test_epsilon_schedule_is_linear_then_flat():
    c = cfg()
    assert epsilon_at(0, c) == pytest.approx(c["epsilon"]["start"])
    assert epsilon_at(5, c) == pytest.approx((c["epsilon"]["start"] + c["epsilon"]["end"]) / 2)
    assert epsilon_at(99, c) == pytest.approx(c["epsilon"]["end"])


def test_a_learning_episode_runs_and_agents_receive_their_own_transitions():
    c = cfg(batch_size=8)
    c["replay"] = {**c["replay"], "warmup": 8}
    c.update(learn_every=1, updates_per_learn=1)
    cl = make_cluster(layout=("fast", "slow"), k="full", ttft_target=5.0, tpot_target=0.2)
    agents = make_agents(c, cl.n, seed=0)
    rng = np.random.default_rng(0)
    stream = stream_of(
        zip(
            np.cumsum(rng.exponential(0.3, 120)),
            rng.integers(100, 800, 120),
            rng.integers(5, 40, 120),
            strict=True,
        )
    )
    stats = run_learning_episode(cl, agents, stream, 0, epsilon=1.0, cfg=c)
    assert all(len(a.buffer) > 0 for a in agents)
    assert stats["act_accept"] + stats["act_forward"] + stats["act_defer"] > 0
    assert np.isfinite(stats["return_mean"]) and np.isfinite(stats["td_loss"])


def test_solo_agent_leaves_the_other_agents_on_the_fallback_policy():
    c = cfg(batch_size=8)
    cl = make_cluster(layout=("fast", "slow"), k="full")
    agents = make_agents(c, cl.n, seed=0, solo=0)
    assert agents[0] is not None and agents[1] is None


def test_transition_record_has_the_adr_010_fields():
    assert {"obs", "mask", "action", "tick", "reward", "next_obs", "next_mask", "truncated"} <= set(
        Transition.__slots__
    )


def test_widen_output_keeps_old_actions_and_new_one_is_never_preferred():
    import torch

    from marl_lb.agents.networks import QNetwork
    from marl_lb.train.loop import widen_output

    torch.manual_seed(0)
    old, new = QNetwork(7, (16, 16), 3), QNetwork(7, (16, 16), 4)
    new.load_state_dict(widen_output(old.state_dict(), 4))
    x = torch.randn(200, 7)
    qo, qn = old(x), new(x)
    assert torch.allclose(qn[:, :3], qo, atol=1e-6)  # the three old outputs are unchanged
    assert torch.allclose(qn[:, 3], qo.mean(dim=1), atol=1e-5)  # the new one starts as their mean
    assert (qn.argmax(dim=1) == qo.argmax(dim=1)).all()  # so the greedy action does not change
    same = widen_output(old.state_dict(), 3)  # no new outputs: identical weights
    assert all(torch.equal(same[k], v) for k, v in old.state_dict().items())
