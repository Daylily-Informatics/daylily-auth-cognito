# daylily-cognito Docs

## Start Here

- [../README.md](../README.md): repo overview, quickstart, current flat-config model, and CLI surface

## Additional Repo Notes

- [../CHANGELOG.md](../CHANGELOG.md): released changes
- [../AI_DIRECTIVE.md](../AI_DIRECTIVE.md): project-specific implementation guidance

## Source Of Truth

Prefer the current code and root README for operational behavior.

Current expected model:

- one effective YAML config file selected by `daycog config path` or root `--config PATH`
- built-in `daycog config ...` for generic config-file lifecycle
- `daycog auth-config ...` for Cognito-specific config sync and inspection

Older examples are useful only if they still match the current CLI and library APIs.
