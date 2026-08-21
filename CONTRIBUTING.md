# Contributing to SNANA Pipeline Assistant

Thank you for helping build better cyberinfrastructure for supernova cosmology pipelines!

We welcome contributions to the knowledge base, the diagnostic tools, and the backend adapters.

## Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/am610/SNANA_PIPELINE_ASSISTANT.git
   cd SNANA_PIPELINE_ASSISTANT
   ```

2. **Set up a virtual environment:**
   We recommend isolating dependencies. Sourcing shared SNANA/DESC environment scripts first can introduce stale Python paths; if `pip` errors inside your venv, run `env -u PYTHONPATH python3 -m venv .venv`.
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e .[all]
   ```

3. **Configure API Keys:**
   Create a `.env` file in the root directory:
   ```bash
   ANTHROPIC_API_KEY=sk-...
   # Optionally:
   # OPENAI_API_KEY=sk-...
   # GOOGLE_API_KEY=...
   ```

## Workflow: Knowledge Base Growth

Knowledge base entries follow a structured format in [entries.yaml](file:///pscratch/sd/a/ayanmitr/SNANA_PIPELINE_ASSISTANT/knowledge/entries.yaml) (symptom, cause, fix, scope, status, source). We do not write arbitrary prose; this keeps retrieval deterministic.

### 1. Ingesting New Issues
We ingest resolved troubleshooting threads from GitHub issues as unverified entries:
```bash
# Ingest a single issue number:
python3 knowledge/summarize_candidate.py <issue_number>

# Ingest multiple issue numbers in a batch:
python3 knowledge/batch_summarize.py <num1> <num2> <num3> --delay 1.5
```
This runs the LLM summarizer backend to extract structured symptoms/causes/remediations and appends them to the knowledge base with `status: unverified`.

### 2. Review and Promotion (Verification)
Before an entry is served to users as fully verified, a maintainer reviews the entry and promotes it:
```bash
snana-assistant promote <entry-id>
```
This flips its status field to `verified` and saves it back. **Ground Rule: Never fabricate. Keep verified claims strictly mapped to verified sources.**

### 3. Re-indexing the LaTeX Manual
If the official SNANA manual changes, rebuild the index chunks:
```bash
python3 knowledge/build_manual_index.py
```

### 4. Updating Package Data
Before cutting a release, make sure to sync the repo data folder to the package source so it gets bundled:
```bash
cp knowledge/entries.yaml src/snana_assistant/data/
cp knowledge/manual_chunks.json src/snana_assistant/data/
```

## Running the Evaluation Suite

Before submitting any Pull Request, run the evaluation test cases to ensure that search accuracy hasn't degraded:
```bash
python3 eval/run_eval.py
```
A successful run writes updated test results to `eval/results.md` and should achieve a **100% success rate**.
