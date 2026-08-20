# Usage

The SNANA Pipeline Assistant provides a CLI containing two main subcommands: `diagnose` and `promote`.

## 1. Diagnosing Failures

To ask the assistant to investigate a failure or lookup a configuration:

```bash
snana-assistant diagnose "Describe the issue or paste the abort log here"
```

### Examples
*   **Pipeline debug:**
    ```bash
    snana-assistant diagnose "My RERUN LCFIT stage is stuck waiting for a lock file."
    ```
*   **Manual parameters lookup:**
    ```bash
    snana-assistant diagnose "What does OPT_PHOTOZ = 6 do in the fitinp namelist?"
    ```
*   **Personal gotcha lookups:**
    ```bash
    snana-assistant diagnose "What did we learn about the SALT2c fix and S3G10_GENPDF.DAT?"
    ```

---

## 2. Review Loop (Promoting Entries)

When a new failure mode is ingested (via automated scraper tools), it lands in the database as `status: unverified`. To review and promote an entry to `status: verified`:

```bash
snana-assistant promote <entry-id>
```

For example:
```bash
snana-assistant promote hostlib-nbrlist-crazy-sep
```
This updates the status directly inside the underlying knowledge database.
