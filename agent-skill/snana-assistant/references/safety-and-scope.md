# Safety Boundaries and Operational Scope

The SNANA Pipeline Assistant operates strictly within safe, read-only diagnostic boundaries.

## Tool Safety Guarantees

1. **Read-Only Operations**:
   - The assistant never modifies configuration files, deletes lock files, cancels running jobs, submits batch jobs, or writes to scratch directories.
   - All remediation suggestions are presented to the user as recommended shell commands to review and run manually.

2. **Filesystem Boundaries**:
   - Directory listings (`list_directory`) are capped at 200 entries. Truncation is explicitly reported.
   - File searches (`search_files`) do NOT follow symlink directory trees (preventing infinite loops in deep cluster scratch spaces), skip known binary and archive formats (.fits, .gz, .tar, .npy, etc.), and are capped at depth 4 and 50 matches.
   - File reads (`read_text_file`) enforce a 500 KB / 1000 line ceiling. Binary and FITS files are rejected.
   - Log inspections (`read_log_tail`) read a bounded tail (default 200 lines, maximum 1000 lines).

3. **Scheduler Restraints**:
   - `check_job_status` executes only read-only status inquiries (`squeue -u $USER` or `qstat -u $USER`).
   - Destructive or state-changing commands (`sbatch`, `scancel`, `scontrol`, `qdel`, `qsub`) are strictly prohibited in diagnostic mode.

4. **Environment & Secret Protection**:
   - `inspect_snana_environment` filters and exposes only scientific and HPC variables (`SNDATA_ROOT`, `PIPPIN_DIR`, etc.).
   - Secrets, API keys, bearer tokens, passwords, and private session credentials are never dumped or inspected.
