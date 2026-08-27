# Trying the SNANA Pipeline Assistant

A short guide for someone testing the assistant for the first time. Should take about
ten minutes to set up.

## What this is

An LLM assistant for SNANA/Pippin work. It reads your config files, browses your working
directory, searches a curated database of known failure modes, and searches the SNANA
manual — then answers with citations to whichever of those it actually used.

It never submits jobs and never edits your files. It only reads.

## 1. Install

Requires **Python 3.10 or newer**.

```bash
git clone https://github.com/am610/SNANA_PIPELINE_ASSISTANT.git
cd SNANA_PIPELINE_ASSISTANT
pip install --upgrade pip          # matters on older cluster Pythons
pip install -e .[all]
```

If your cluster default Python is older than 3.10, make an environment first:

```bash
conda create -n snana_assistant python=3.10 -y && conda activate snana_assistant
```

## 2. Set the API key

You will have been sent one. It is capped to a small budget, so testing costs nothing
and cannot run up a bill.

```bash
export ANTHROPIC_API_KEY="<the key you were sent>"
```

Add it to `~/.bashrc` if you do not want to re-export it every login.

## 3. Run it from a directory with real SNANA files

This matters. In an empty directory there is nothing to read, and most of what the
assistant does will look like it is not working. Point it at an actual working
directory — sim inputs, HOSTLIBs, submit scripts, logs.

```bash
cd /path/to/your/snana/working/directory
snana-assistant chat
```

`chat` is a conversation: follow-up questions remember what came before, including files
already read. `/reset` starts fresh, `/exit` quits.

For a single question without the session, use `snana-assistant diagnose "..."`.

## 4. Things worth trying

Vary these to your own files — the point is to see whether it holds up on real work.

**Reading and explaining a config**

```
check sim_ia_salt_des5yr.input -- is it written correctly, what dependency files does
it call, and what is it supposed to do?
```

It should read the file, follow any `INPUT_FILE_INCLUDE` into the included file, and
report the real dependency chain.

**Finding what references what**

```
which script in this directory uses sim_ia_salt_des5yr.input?
where is DES-SN5YR_DES.HOSTLIB referenced?
```

It greps for you. You should not have to paste an `ls` or supply a path.

**A real failure**

Paste an actual error or abort message from a log. If it matches a curated failure mode
you will get a citation in square brackets, like `[hostlib-dztol-too-tight]`, with the
cause and fix. If nothing matches it should say so rather than inventing an answer.

**Follow-ups**

Ask "why does that matter?" or "what about the WGTMAP path?" after an answer. It should
resolve those against the conversation instead of starting over.

## What to report back

Most useful, roughly in order:

1. **Wrong answers stated confidently.** The worst failure mode. Especially: did it ever
   describe a file without actually reading it? If an answer looks plausible but generic,
   ask "did you read the file?" and see what it says.
2. **Questions it should have handled but did not** — cases where it asked you for
   something it could have found itself, or gave up too early.
3. **A missing failure mode.** If it could not diagnose a real problem you know the
   answer to, run `snana-assistant feedback` — it drafts a GitHub issue with your query
   so the failure mode can be added.
4. Anything confusing about the output, the setup, or the commands.

## Useful to know

- **Answers stream** as they are written. If it seems to pause, it is running a tool
  (reading a file, searching) between turns.
- **A complex question takes 10–30 seconds** — it is several model round trips, not one.
- **`--max-turns 25`** if an answer ever comes back tagged `[incomplete: ...]`, which
  means it ran out of investigation budget.
- **It sends file contents to the Anthropic API** in order to reason about them. Keep it
  pointed at your own directories; do not browse other people's data with it.
- **It only reads.** No job submission, no file edits.

## If something breaks

- `snana-assistant: command not found` — the install did not land in the active
  environment. Re-activate and `pip install -e .[all]` again.
- `No API key or local host configuration found` — `ANTHROPIC_API_KEY` is not exported
  in this shell.
- A `credit balance` or quota error — the trial budget is exhausted; say so and it can be
  raised.
