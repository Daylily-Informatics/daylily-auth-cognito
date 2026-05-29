# Shell Session Defaults

- Default to an interactive shell for shell work. On this Mac, use the user's default shell unless the user explicitly asks for another shell.
- For AWS EC2, ParallelCluster, and other remote Linux hosts, default to an interactive `bash` login shell as `ubuntu`. Do not use `root` unless the user explicitly grants permission for that specific work; use targeted `sudo` from `ubuntu` when escalation is required.
- For Daylily/DayOA/DAY-EC headnode workflow work, use an interactive `ubuntu` tmux/login-shell pane for controllers and workflow commands. Run setup as separate commands in that pane (`source dyoainit`, then `dy-a ...`, then `dy-r ...`) so aliases/functions are defined before use.
- SSM Run Command is for simple inspection or for writing helper scripts through the supported helpers. Do not launch workflow controllers or rely on `dy-*` aliases from non-interactive SSM scripts.

# Daycog CLI Policy

## Session Setup

Always start by activating the repo environment:

```bash
source ./activate
```

## Command Ownership

- Use `daycog ...` as the primary interface for normal Cognito and shared auth work.
- Do not bypass `daycog` with raw AWS CLI mutations, ad hoc `python -m ...`, or direct config-file edits just because something is missing or broken.

## No Circumvention Policy

- If the intended CLI path is broken or incomplete, stop, diagnose, and ask for permission before circumventing it.
- Prefer patience and repair of the intended CLI workflow over inventing a shortcut.

## Daycog Examples

- Start with `source ./activate`
- Use `daycog status`
- Use `daycog config path`
- Use `daycog --json auth-config print`
- Use `daycog ...` directly for Cognito pool, app, and user lifecycle
