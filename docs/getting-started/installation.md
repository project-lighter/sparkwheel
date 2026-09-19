# Installation

Sparkwheel requires Python 3.10 or newer. It depends on PyYAML; Torch and Lightning
are optional application libraries, not Sparkwheel requirements.

**Current source:** `0.1.0.dev0` is an unpublished development version. Install this
checkout to follow these docs; an existing PyPI release may have different
behavior. The instructions below use Python 3.11 and an isolated environment.

## Install from Source

Use the supplied Sparkwheel source checkout that accompanies this documentation.
This unpublished snapshot is not obtained by installing a registry release or
necessarily by cloning the public repository. If you do not have that checkout,
obtain it from the person who supplied these development docs.

From that checkout's repository root, create the environment and install the source:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

On Windows, use `py -3.11 -m venv .venv` and activate it with
`.venv\Scripts\Activate.ps1` in PowerShell, then run the same pip command.

Keep this environment active for the examples. An editable installation follows
changes in this checkout; record its revision when you need reproducibility.

## Verify Installation

Run from the activated environment:

```bash
python -c "import sparkwheel; print(sparkwheel.__version__); print(sparkwheel.__file__)"
```

Expect version `0.1.0.dev0` and an import path inside your checkout's
`src/sparkwheel` directory. If the version or path differs, check the active Python
with `python -m pip show sparkwheel` before continuing.

## Install from PyPI

For an application targeting a released version, install that release and use its
matching documentation. The source-install path above is the supported route for
the development behavior described here.

## Development Setup

Contributors can use the repository's `just setup` workflow with `uv` and `just`
installed. It installs development groups and configures hooks. See the
[justfile](https://github.com/project-lighter/sparkwheel/blob/main/justfile) for the
maintainer commands. These tools are not needed to use Sparkwheel.

## Next Steps

Continue to the [quick start](quickstart.md). It runs independently of any
machine-learning framework.
