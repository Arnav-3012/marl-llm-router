# Docker (placeholder, M7)

Compose profiles to be implemented:

- **cpu**: llama-server CPU containers + router + trace replay. Runs on any machine.
- **host**: router and replay in Docker; llama-servers run natively on the Mac
  (Docker on macOS cannot use the Metal GPU) and are reached via `host.docker.internal`.

Usage commands will be added when M7 is built.
