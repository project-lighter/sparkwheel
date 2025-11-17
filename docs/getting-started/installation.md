# Installation

Sparkwheel requires Python 3.10 or higher.

## Install from PyPI

The simplest way to install Sparkwheel:

```bash
pip install sparkwheel
```

## Install from Source

For the latest development version:

```bash
git clone https://github.com/project-lighter/sparkwheel.git
cd sparkwheel
pip install -e .
```

## Development Setup

If you want to contribute to Sparkwheel, we use [uv](https://github.com/astral-sh/uv) and [just](https://github.com/casey/just) for development:

### Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Install just

=== "macOS"
    ```bash
    brew install just
    ```

=== "Linux"
    ```bash
    apt install just
    ```

=== "Windows"
    ```powershell
    winget install --id Casey.Just --exact
    ```

### Setup Development Environment

```bash
git clone https://github.com/project-lighter/sparkwheel.git
cd sparkwheel
just setup
```

Check out the [`justfile`](https://github.com/project-lighter/sparkwheel/blob/main/justfile) for other available commands.

This will:

- Install all dependencies (including dev, test, and doc groups)
- Set up pre-commit hooks
- Configure your development environment

## Verify Installation

Test that Sparkwheel is installed correctly:

```python
import sparkwheel
print(sparkwheel.__version__)
```

## Next Steps

- [Quick Start](quickstart.md) - Learn the basics
- [User Guide](../user-guide/basics.md) - Deep dive into features
