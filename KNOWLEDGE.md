# Knowledge Base — Schema and Seed Entries

Derived from `~/.claude/snana-knowledge/gotchas.md` and the `pipeline-debug` checklist,
restructured into the schema Phase 1's retrieval layer will index. This file is the
seed; Phase 2 adds a submission/review path so it grows from real usage instead of
staying static.

## Schema

Each entry:
- `symptom` — what the user sees (error text, log pattern, observable behavior)
- `cause` — root cause
- `fix` — concrete remediation steps
- `scope` — `universal` (true regardless of cluster/scheduler) / `slurm` (true on any
  Slurm cluster, not Perlmutter-specific) / `perlmutter` (NERSC-specific paths or
  quirks)
- `status` — `verified` (confirmed against a real incident) / `unverified` (reported,
  not yet confirmed)
- `source` — where this came from

---

### 1. Stale BUSY_MERGE_CPU*.LOCK hangs resubmitted LCFIT job for full walltime
- **symptom:** LOG shows `Wait for ['BUSY_MERGE_CPUXXXX.LOCK'] to clear` repeated for
  hours, then `CANCELLED ... DUE TO TIME LIMIT`. Zero fitting occurs despite the job
  running its full walltime.
- **cause:** A prior merge crash or kill left a `BUSY_MERGE_CPU*.LOCK` file in
  `output/`. The resubmitted job's CMD calls `--merge` after each fit and waits
  indefinitely for the stale lock.
- **fix:** Before resubmitting any RERUN batch: `rm -f output/BUSY_MERGE_CPU*.LOCK`
- **scope:** universal (Pippin merge-driver behavior, not cluster-specific)
- **status:** verified
- **source:** EUCLID_LSST_DDF_V4_PHOTOZ FIT_DATA_EUCLID_PHZ, 2026-06-09 — RERUN_CPU0004
  wasted a full 20h walltime window on a stale lock.

### 2. Missing FITOPTXXX.FITRES in version directory after merge abort
- **symptom:** `FATAL ERROR ABORT: Missing expected PIP_...-00XX/FITOPTYYY.FITRES` in
  the merge log.
- **cause:** A merge attempt aborted mid-way (stale lock, truncated FITRES, allocation
  kill). The merge driver marked the version/FITOPT DONE in MERGE.LOG but never wrote
  the final merged FITRES file. The next merge pass finds it missing and aborts.
- **fix:**
  1. Verify raw FITRES.TEXT is intact: `grep -c '^SN:' <VERSION>_FITOPTYYY_SPLIT001.FITRES.TEXT`
  2. If intact, manually rebuild the merged file:
     ```
     cd SPLIT_JOBS_LCFIT/
     cat <PREFIX>_FITOPTYYY*FITRES.TEXT > /tmp/MERGE_tmp.FITRES
     awk '!/^VARNAMES/ || ++n <= 1' /tmp/MERGE_tmp.FITRES > /tmp/MERGE2_tmp.FITRES
     cp /tmp/MERGE2_tmp.FITRES ../PIP_...-00XX/FITOPTYYY.FITRES
     ```
  3. Truncate the FATAL ERROR from MERGE.LOG, delete ALL.DONE, run MERGE_LAST.
- **scope:** universal
- **status:** verified
- **source:** -0018/FITOPT018.FITRES, 2026-06-09 — FITRES.TEXT had 1472 intact rows.

### 3. sigint abort in BBC
- **symptom:** BBC (SALT2mu) aborts citing sigint.
- **cause:** Attempting to use a nonexistent `sigint_fix` option.
- **fix:** Use `sigmb_biascor`, not `sigint_fix` — the latter does not exist.
- **scope:** universal
- **status:** verified
- **source:** pipeline-debug checklist / project ground rules.

### 4. Missing SALT2 PDF files
- **symptom:** LCFIT/sim aborts referencing missing SALT2 probability-density files.
- **cause:** `SALT2_INFO` path in the sim input file is wrong or the referenced PDF
  files aren't present at that path.
- **fix:** Verify `SALT2_INFO` path in the sim input file against what's actually on
  disk.
- **scope:** universal
- **status:** verified
- **source:** pipeline-debug checklist / project ground rules.

### 5. HOSTLIB_DZTOL too tight
- **symptom:** HOSTLIB-related aborts or excessive event rejection during host
  matching.
- **cause:** `HOSTLIB_DZTOL` tolerance set too tight for the redshift precision
  actually available in the HOSTLIB.
- **fix:** Loosen `HOSTLIB_DZTOL` in the HOSTLIB config.
- **scope:** universal
- **status:** verified
- **source:** pipeline-debug checklist / project ground rules.

### 6. GENVERSION name silently truncated / collides at ~72 characters
- **symptom:** Sim runs under a different effective GENVERSION than what was
  specified, or two nominally-different runs collide.
- **cause:** GENVERSION strings have a length limit (~72 chars); long descriptive
  names get silently truncated, and two long names differing only in a suffix can
  become identical after truncation.
- **fix:** Keep GENVERSION names short and check for truncation collisions when using
  long descriptive names.
- **scope:** universal
- **status:** verified
- **source:** Bailey+2022 reproduction session, 2026-08-16.

### 7. Slurm job name truncation causes false "conflict" reuse
- **symptom:** Pippin reruns appear to silently reuse/interfere with a prior job.
- **cause:** Slurm job names are truncated at ~8 characters; two differently-named
  Pippin jobs can collide after truncation and `squeue -u $USER` won't obviously show
  this unless you know to look for it.
- **fix:** Check `squeue -u $USER` for duplicate truncated names before assuming a
  failure is config/code-level.
- **scope:** slurm (true on any Slurm cluster, not Perlmutter-specific)
- **status:** verified
- **source:** pipeline-debug checklist, step 1.

### 8. Fix applied to source YAML doesn't take effect
- **symptom:** A config fix is made but the pipeline still fails the same way.
- **cause:** Pippin copies YAMLs into its output staging directory at runtime; a fix
  to the source YAML isn't picked up if Pippin already cached a prior copy for that
  stage.
- **fix:** `diff <source_yaml> <pippin_output_dir>/<stage>/<cached_yaml>` — if they
  differ, fix the cached copy directly or force a rerun of that stage.
- **scope:** universal
- **status:** verified
- **source:** pipeline-debug checklist, step 2 — one of the most common false "the fix
  didn't work" reports.

---

## Entries still needed (not yet written up — candidates for next pass)
- OOM / walltime patterns from `.log` files (BATCH_MEM / BATCH_NCORE / BATCH_WALLTIME
  fixes) — mentioned throughout session history but not yet captured as a discrete
  entry with a concrete symptom string.
- Environment variable misconfiguration patterns (`SNDATA_ROOT` vs `MY_SNDATA_ROOT`
  mismatches) — flagged as a top debugging step but no concrete incident captured yet.
