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

### 2. Clone and Setup

```bash
git clone https://github.com/project-lighter/sparkwheel.git
cd sparkwheel
just setup
```

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
