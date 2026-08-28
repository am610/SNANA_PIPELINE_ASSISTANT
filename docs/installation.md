# Installation

You can install the SNANA Pipeline Assistant via standard Python tools or run it inside a pre-built container.

## 1. Standard Installation (pip)

To install the package with all provider backends (Anthropic, OpenAI, Gemini):

```bash
pip install "isnana[all]"
```

To install the latest unreleased code directly from GitHub instead:

```bash
pip install "isnana[all] @ git+https://github.com/am610/SNANA_PIPELINE_ASSISTANT.git"
```

### Initial Configuration

After installation, run the configuration wizard:
```bash
snana-assistant init
```
This wizard:
* Automatically probes environment variables (`$SNDATA_ROOT`, `$SNANA_DIR`) and defaults.
* Automatically configures setup commands (like `source setup_td.sh` on Perlmutter).
* Detects running local Ollama servers and configured models.
* Stores persistent settings in `~/.config/snana-assistant/config.yaml` so you don't have to define path environment variables again.

---


## 2. Running via Docker

You can build and execute the assistant within a Docker container:

```bash
# Build the image
docker build -t snana-assistant .

# Run a diagnosis
docker run --rm \
  -v $(pwd)/.env:/app/.env \
  -v ~/.claude/snana-knowledge:/root/.claude/snana-knowledge \
  snana-assistant diagnose "My light-curve simulation crashed"
```

---

## 3. HPC Clusters (Singularity / Apptainer)

On compute clusters (like NERSC Perlmutter or Chicago Midway) where Docker is restricted, use **Singularity**:

```bash
# Run directly from Docker Hub
singularity run \
  -B $(pwd)/.env:/app/.env \
  -B ~/.claude/snana-knowledge:/root/.claude/snana-knowledge \
  docker://username/snana-assistant:latest diagnose "My light-curve simulation crashed"
```
