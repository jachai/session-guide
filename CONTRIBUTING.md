# Contributing

Issues and pull requests are welcome. session-guide is mostly a skill: `skills/session-guide/SKILL.md` and its
`references/`. It has one helper script, `skills/session-guide/scripts/peek.py`, which uses only the standard library
and runs on Python 3.9+. Please keep it that way: no runtime dependencies.

## Tests

The tests need [uv](https://docs.astral.sh/uv/), which fetches the Python versions for you. CI runs the oldest and
newest supported versions on Ubuntu and macOS:

```sh
uv run --no-project --python 3.9 python -m unittest discover -s tests
uv run --no-project --python 3.14 python -m unittest discover -s tests
uvx pyflakes skills scripts tests
python3 scripts/demo.py
claude plugin validate .
```

Every test builds its own Claude config dir in a temp folder and sets `CLAUDE_CONFIG_DIR`, so nothing reads your
real `~/.claude`. New tests should do the same.

## Changing the guide's rules

Rules in `SKILL.md` exist because a multi-session run went wrong without them. If you change or add one, explain in
the PR the situation it fixes. Keep the guide advisory: a change that lets the guide build, merge or touch shared
environments needs a strong case. When in doubt, the guide should ask the user once rather than act.

## Privacy

Never commit real session data: no transcripts, ledgers, session names, prompts or paths from your own machine. This
applies to tests, issues and examples. Use `scripts/demo.py` or made-up fixtures instead.

## Releases

1. Move the `Unreleased` notes in `CHANGELOG.md` under a new version heading.
2. Bump `__version__` in `peek.py` and `version` in `.claude-plugin/plugin.json`.
3. Push a `vX.Y.Z` tag. The release workflow runs the tests, checks the versions match and creates a GitHub release
   with that version's changelog notes. Plugin users get the update through `/plugin marketplace update`.
