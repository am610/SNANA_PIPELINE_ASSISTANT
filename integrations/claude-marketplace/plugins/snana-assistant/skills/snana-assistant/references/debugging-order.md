# SNANA / Pippin Operational Debugging Order

Experienced SNANA operators always rule out environmental and orchestrator issues before opening source code or re-running extensive simulations.

## Stage 1: Scheduler & Orchestrator Check
- **Tool**: `check_job_status`
- **What to look for**:
  - Are batch jobs actively running, stuck in pending (`PD`), or stuck in completing (`CG`)?
  - Did jobs exit prematurely without updating status files?
  - **Job name collisions**: Slurm truncates job names in standard displays (often ~8-10 chars). If multiple parallel tasks share a common prefix, the monitor may mistake one task's state for another's.

## Stage 2: Staged-vs-Source Configuration Verification
- **Tool**: `diff_config(source_path, cached_path)`
- **What to look for**:
  - Pippin copies user YAML/input files into its output staging area (`<OUTPUT_DIR>/<STAGE_NAME>/...`).
  - If a user modifies the root `pippin.yml` or input file but re-runs without properly clearing cache or passing refresh flags, Pippin continues executing the stale cached copy.
  - Diffing the source file against the cached file immediately verifies whether the intended change was actually live.

## Stage 3: Environment Verification
- **Tool**: `inspect_snana_environment`
- **What to look for**:
  - Is `SNDATA_ROOT` set? Is `MY_SNDATA_ROOT` overriding intended standard models?
  - Are cluster-specific scratch paths (`SCRATCH`, `PSCRATCH`) mounted and writeable?
  - Check whether `SNANA_DIR` points to the expected release or development build.

## Stage 4: Resource Limits & Log Signatures
- **Tool**: `read_log_tail(log_path, n_lines)`
- **Common Signatures**:
  - `OOM` or `Killed` -> Out-of-memory error caused by high galaxy library density (`HOSTLIB`) or large batch sizes.
  - `TIMEOUT` or `DUE TO TIME LIMIT` -> Walltime exhaustion. Check if jobs were stuck waiting on a lock (e.g. `BUSY_MERGE_CPUXXXX.LOCK`) or if split counts need increasing.
  - `Segmentation fault` or `FATAL ERROR` -> Missing survey filters, uninitialized table, or array overflow (e.g. `MXSNLC` exceeded).

## Stage 5: Structured Knowledge Base & Manual Lookup
- **Tools**: `search_knowledge(query)`, `search_manual(query)`
- **What to do**:
  - Search using the exact literal error message from the log.
  - Review matching entries, their scope (`universal`, `slurm`, `perlmutter`), and verification status.
  - Check manual passages for exact parameter keywords and syntax.

## Stage 6: Code & Filesystem Search
- **Tools**: `search_files(pattern, path, glob)`, `read_text_file(file_path)`
- **What to do**:
  - Find which pipeline script or submission wrapper invoked a specific input file.
  - Read specific configuration blocks without loading huge log files or datasets.
