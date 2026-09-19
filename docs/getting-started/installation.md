# Installation

Sparkwheel requires Python 3.10 or newer and PyYAML. Torch and Lightning are not required. The examples below use Python 3.11 and a fresh environment.

The current source version is **0.1.0.dev0**. Its source is public; older PyPI releases may have different behavior. The command below selects the **immutable reviewed snapshot** `c2286a0626748e913296d7127c16060cb705b6d0`. It predates later review-branch changes; release handoffs name the exact revision they qualify.

## Install from Source

With Python 3.11 and Git installed, start in a new working directory:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install "sparkwheel @ git+https://github.com/project-lighter/sparkwheel.git@c2286a0626748e913296d7127c16060cb705b6d0"
python -m pip check
```

This installs a normal package from the public Git revision. It needs network access but no supplied checkout or GitHub account. On Windows, use `py -3.11 -m venv .venv` and activate `.venv\Scripts\Activate.ps1` in PowerShell, then run the same pip commands.

Keep the environment active for the examples. The full commit pin does not follow branch updates, and changes in an unrelated local clone do not change the installed package.

## Verify Installation

```bash
python -c "import sparkwheel; print(sparkwheel.__version__); print(sparkwheel.__file__)"
```

Expect `0.1.0.dev0` and a path inside this environment's `site-packages/sparkwheel`. If the version or path differs, check `python -m pip show sparkwheel` and the active environment before continuing. pip's distribution metadata also records the installed VCS commit ID.

## Install from PyPI

For an application targeting a released version, install that release and use its matching documentation. The explicit source revision above provides the development behavior described here while the corresponding stable release is being prepared.

## Development Setup

Only contributors need an editable clone. From a new working directory with the environment active:

```bash
git clone https://github.com/project-lighter/sparkwheel.git sparkwheel
git -C sparkwheel checkout --detach c2286a0626748e913296d7127c16060cb705b6d0
python -m pip install --editable ./sparkwheel
```

Edits in this clone now affect imports. Create a working branch before committing changes. For tests, docs and hooks, install `uv` and `just`, then use `just setup` from the clone. See [Contributing](https://github.com/project-lighter/sparkwheel/blob/codex/reliability-and-documentation/CONTRIBUTING.md). Contributor tools are not required for package use.

## Next Steps

Continue to the [quick start](quickstart.md), which runs independently of a machine-learning framework.
