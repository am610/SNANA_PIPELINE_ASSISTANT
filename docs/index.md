# SNANA Pipeline Assistant

An LLM-based operations assistant for SNANA/Pippin pipelines (SuperNova ANAlysis — the simulation/light-curve-fitting/bias-correction engine underneath DES, LSST-DESC, Roman, and Euclid supernova cosmology).

The assistant diagnoses pipeline failures (stale locks, cached-vs-source config mismatches, scheduler job-name collisions, known config bugs) against a curated, structured knowledge base and your custom gotchas.

## Core Features

*   **Operational-First Debugging:** Automatically checks Slurm/PBS scheduler states and log tails before speculating about configuration or code bugs.
*   **Curated Knowledge Base:** Uses a structured, verified schema containing known failure-modes.
*   **Personal Gotchas Search:** Integrates directly with your custom Claude gotcha logs and session history.
*   **Manual Reference Search:** Connects to the official LaTeX source of the SNANA manual to lookup parameters on the fly.
*   **Multi-Provider Support:** Supports Anthropic (Claude), OpenAI (GPT-4), Gemini, and Local (Ollama/vLLM) backends.
