# Changelog

Changes a user of the command can see. Newest first. Release dates are on the
[releases page](https://github.com/sabachan3/l10n-sense/releases).

## 0.1.0

First release.

- `l10n-sense check` audits one translated locale file against its source file and gives every
  string a verdict: `fail`, `review`, `warn` or `ok`. Exit code 1 when a string fails, 2 when the
  command could not do its job (unreadable or malformed file, wrong options).
- Rules that need no model (`--no-model`): placeholders that differ from the source, empty and
  missing translations, the key's own name used as the translation, text left untranslated.
- A 0-100 score for every string from a model that sees the code using the string (`--src`).
  Calls go through a model CLI you are logged in to: Claude Code by default, Codex with
  `--scorer codex`. No API key, nothing hosted.
- `--second` adds an independent scorer; a string then fails only when both rate it wrong, and a
  one-sided finding is reported as `review`.
- Locale files: JSON (nested, flat, Chrome extension, Flutter ARB), YAML (with the `yaml` extra),
  gettext `.po`, Android `strings.xml`, iOS `.strings`, Xcode String Catalog.
- Scores are cached per project outside the project directory; every cached entry is validated
  before use. A string with no score is reported as unscored, never as passed.
- Text and JSON reports (`--format json`, `--out`). Invisible and control characters from the
  files under review are never written raw to the terminal or into JSON.
- Model CLIs run with every acting tool off, from an empty directory; only files under `--src`
  are read and symlinks are not followed.
- `l10n-sense --version`.
