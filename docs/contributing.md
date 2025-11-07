# Contributing

We welcome contributions to Sparkwheel! This guide will help you get started.

## Development Setup

1. Fork and clone the repository:

```bash
git clone https://github.com/yourusername/sparkwheel.git
cd sparkwheel
```

2. Install dependencies:

```bash
just setup
```

This installs all development dependencies and sets up pre-commit hooks.

## Development Commands

We use `just` for common tasks:

```bash
just lint      # Run code linter
just test      # Run tests
just coverage  # Generate coverage report
just docs      # Serve documentation locally
```

## Making Changes

1. Create a new branch:

```bash
git checkout -b feature/your-feature-name
```

2. Make your changes and ensure tests pass:

```bash
just test
just lint
```

3. Commit your changes following conventional commits:

```bash
git commit -m "Add feature X"
```

4. Push and create a pull request

## Pull Request Guidelines

- Ensure all tests pass
- Add tests for new features
- Update documentation
- Follow the code style (enforced by pre-commit hooks)
- PR title should start with a capital letter and not end with a period

## Code Quality

We use:

- **ruff** for linting and formatting
- **mypy** for type checking
- **pytest** for testing

Pre-commit hooks run automatically on commit.

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.
