# AWT
Agent Worker Team

## Requirements

- Python 3.10+
- Dependencies used by the agent runtime are listed in [requirements.txt](requirements.txt): `groq`, `pydantic`, `python-dotenv`, and `prompt_toolkit`
- One or more `GROQ_API_KEY_1` ... `GROQ_API_KEY_9` values in `.env` for the `run` command

## CLI

Start the interactive terminal UI in CMD or PowerShell:

```powershell
python -m cli
```

It opens a project workspace where normal text starts an engineering task. AWT sends the task through the real orchestrator loop: initial decision, dynamic delegation, execution, independent review, rework, aggregation, and final result. Use `/agents`, `/config`, `/tools`, `/scan`, `/help`, and `/exit` for workspace commands. `python main.py` opens the same UI.

### System tools and safety

Agents can propose these built-in tools through structured decisions:

- `list_files` and `read_file` are read-only and limited to the workspace.
- `write_file` requires an interactive user approval before every action.
- `run_shell` requires approval, runs with `shell=False`, is limited to the workspace, and only allows `python`, `pytest`, `git status`, and `git diff` entry points.

The agent never receives direct filesystem or process access. The Orchestrator validates every request and denies tool access when no registry or approval handler is configured.

Inspect headers without an API key by passing them directly:

```powershell
python -m cli scan-headers --json `
	--header "Content-Security-Policy=default-src 'self'" `
	--header "Strict-Transport-Security=max-age=31536000" `
	--header "X-Content-Type-Options=nosniff"
```

Inspect a live URL:

```powershell
python -m cli scan-headers https://example.com
```

Run a task through the multi-agent orchestrator:

```powershell
python -m cli run "Review this repository for security issues" --timeout 600
```

`scan-headers` returns exit code `1` when findings are present, which makes it suitable for CI checks. The scanner reports missing or weak values for Content-Security-Policy, Strict-Transport-Security, X-Content-Type-Options, X-Frame-Options, Referrer-Policy, and Permissions-Policy.
