# Demo (placeholder, M7)

Gradio app for a Hugging Face Space (free CPU, simulator mode, no LLMs served).

- Loads trained policy weights (`demo/weights/`) and `profiling/calibration.json`.
- Controls: λ, load ρ, visibility k, policy (SED / cache-aware / MARL).
- Shows: routing decisions per server, TTFT/cost time series, the policy's point on the precomputed Pareto frontier.
