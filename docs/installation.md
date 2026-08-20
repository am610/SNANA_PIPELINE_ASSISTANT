# Installation

You can install the SNANA Pipeline Assistant via standard Python tools or run it inside a pre-built container.

## 1. Standard Installation (pip)

To install the package with all provider backends (Anthropic, OpenAI, Gemini):

```bash
pip install "snana-assistant[all] @ git+https://github.com/am610/SNANA_PIPELINE_ASSISTANT.git"
```

### Environment Setup
Create a `.env` file in your workspace directory (or home folder) containing your API keys:

```env
ANTHROPIC_API_KEY=your-api-key
# Optional custom paths:
# SNANA_DIR=/path/to/snana
# SNANA_GOTCHAS_DIR=/path/to/gotchas
```

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
