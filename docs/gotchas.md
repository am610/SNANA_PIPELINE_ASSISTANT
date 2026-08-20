# Curated Gotchas & Knowledge Base

The assistant uses two layers of knowledge for formulating diagnostics:

## 1. Curated Knowledge Base (`entries.yaml`)

The file `knowledge/entries.yaml` contains structured, verified operational failure modes. Each entry follows a strict schema:

```yaml
- id: hostlib-dztol-too-tight
  symptom: "Simulation fails with 'GEN_SNHOST_GALID: ZDIF=X exceeds dztol=Y'"
  cause: "HOSTLIB_DZTOL tolerance (default 0.002 0.040 0.0) is too tight for the simulated photo-z scatter."
  fix: "Loosen dztol in the sim input file: e.g. HOSTLIB_DZTOL: 0.010 0.050 0.0"
  scope: universal
  status: verified
  source: "YSE/Rubin sim inputs, 2026-03-24 debugging session"
```

The scope can be tagged as `universal`, `slurm`, or `perlmutter` for filtering.

---

## 2. Personal Gotchas Directory (`~/.claude/snana-knowledge/`)

If you have personal notes, markdown gotcha logs, or previous session history stored in `~/.claude/snana-knowledge/` (or configured via `SNANA_GOTCHAS_DIR`), the assistant automatically searches this folder dynamically.

This allows the agent to recall custom fixes (such as YSE paths, Euclid configurations, or custom script patches) that aren't yet in the official manual.
