# Mistakes

Log a bug or misconception that cost more than 15 minutes, with the rule that prevents it.

## Template

```
### YYYY-MM-DD — <short title>
What happened:
Time lost:
Root cause:
Prevention rule:
```

## Entries

### 2026-10-03 — Phase S scaffold started with an empty docs/context.md
What happened: The scaffold prompt referred to docs/context.md for sweep values, phases and the ownership map, but the file was empty, so building could not start.
Time lost: one round trip.
Root cause: The spec file was created but not filled before the scaffold task was issued.
Prevention rule: At session start, confirm docs/context.md is non-empty before issuing a task that depends on it.
