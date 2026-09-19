# Contributing to Sparkwheel

Thank you for your interest in contributing to Sparkwheel!

## Development Setup

We use [uv](https://github.com/astral-sh/uv) and [just](https://github.com/casey/just) for development workflow.

### 1. Install Tools

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install just (macOS)
brew install just

# Or see https://github.com/casey/just for other platforms
```

### 2. Set up the matching source

These docs describe the supplied unpublished `0.1.0.dev0` checkout. Work from
that checkout when reproducing its behavior; a public clone may contain a
different version. [Source installation](docs/getting-started/installation.md)
is enough to use the package. For contribution tools, run from its root:

```bash
just setup
```

This contributor workflow uses or updates the checkout's conventional `.venv`,
the same path as the installation guide, and adds contributor dependencies.

This will:
- Install all dependencies (dev, test, doc groups)
- Set up pre-commit hooks
- Configure your environment

## Development Commands

We use `just` for common tasks:

```bash
just          # List all available commands
just test     # Run tests
just lint     # Run linter
just types    # Run type checker
just coverage # Generate coverage report
just docs     # Serve documentation locally
```

## Code Quality

We use:
- **ruff** for linting and formatting (replaces black + flake8)
- **mypy** for type checking
- **pytest** for testing

Pre-commit hooks will automatically run on commit.

## Keep documentation useful

Use one documentation set for people and agents. Keep behavior in ordinary
Python, teach one complete first example, and link to the canonical semantic
explanation instead of maintaining parallel copies.

- State the working directory, prerequisites, exact inputs and expected outputs
  for a runnable example. Mark excerpts through their surrounding explanation.
- Preserve the distinction between source inspection and execution, and between
  a shared result and a copied definition.
- Run changed complete examples with the documented install; record which checks
  actually ran. Review other affected snippets against source.
- Build the site strictly and check affected links/anchors. With documentation
  dependencies installed and the environment active, use:

```bash
python -m mkdocs build --strict
```

Keep explanatory Markdown under `docs/`, entrypoint guidance in README, and the
Python API reference generated from source. Prefer existing paths and descriptive
headings. New documentation machinery needs a concrete unmet need. A passing
build does not execute every code example.

## Pull Request Process

1. Fork the repository
2. Create a new branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for your changes
5. Ensure all tests pass (`just test`)
6. Ensure code quality passes (`just lint`)
7. Commit your changes (PR title should be capitalized and not end with a period)
8. Push to the branch (`git push origin feature/amazing-feature`)
9. Open a Pull Request

### PR Title Guidelines

PR titles are checked automatically and must:
- Start with a capital letter
- Not end with a period
- Be descriptive (10-72 characters)
- Examples: "Add reference validation", "Fix expression parsing bug"

## Reporting Issues

When reporting issues, please include:
- A clear description of the problem
- Steps to reproduce
- Expected behavior
- Actual behavior
- Your environment (Python version, OS, etc.)
- A minimal code example if applicable

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.

## Version preparation

Version maintenance uses the pinned `bump-my-version==0.30.1` executable through
`uvx`, independently of runtime dependency installation. The supported recipe
parts are `major`, `minor`, `patch`, and `release`:

```bash
just bump-dry release  # Preview 0.1.0.dev0 -> 0.1.0
just bump-dry patch    # A stable 0.1.0 previews 0.1.1
```

`release` removes an existing `.devN` suffix without advancing the numeric
version. Numeric bumps advance that component and reset subordinate components
to stable; `patch` from `0.1.0.dev0` therefore previews `0.1.1`, not promotion to
`0.1.0`. Use `release` for that promotion. Unsupported parts, including the raw
`dev` counter, fail before invoking the tool. Starting another development cycle
requires a separately reviewed explicit version choice.

Dry runs disable file writes, commits and tags. After release authorization,
`just bump <part>` updates project metadata, the source version constant, the
bump configuration and only Sparkwheel's editable-root version in `uv.lock`; it
also creates the configured local commit and tag. Review the diff and run the
ordinary package checks before any separately authorized push or publication.
Current development snapshots have not been tagged or published by this work.

The existing remote workflows treat pushed tags as stable releases and can
publish them. Do not use development tags with that workflow; previewing or
preparing a version locally does not authorize its remote release.
