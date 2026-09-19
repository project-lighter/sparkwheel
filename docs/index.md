# Sparkwheel

Compose configuration, then build ordinary Python objects.

Keep behavior in Python. Use YAML or dictionaries to choose objects, supply their
arguments and share dependencies. Sparkwheel handles composition and construction;
it does not run your application or replace its libraries.

**This documentation describes the unpublished `0.1.0.dev0` source checkout.**
Follow [source installation](getting-started/installation.md) before the examples.
Sparkwheel requires Python 3.10+ and PyYAML; the first example needs no Torch,
Lightning, data download or service.

## Start here

The [quick start](getting-started/quickstart.md) builds a word counter, inspects
its definition and changes its input from the command line. Then read the
[configuration model](user-guide/basics.md) to understand what is stored and when
Python code runs.

| Task | Guide |
|---|---|
| Install the current source | [Installation](getting-started/installation.md) |
| Run the first example | [Quick start](getting-started/quickstart.md) |
| Read and edit configuration | [Configuration model](user-guide/basics.md) |
| Share an object or create another instance | [References: `@` and `%`](user-guide/references.md) |
| Call my classes and functions | [Python authoring](user-guide/instantiation.md) |
| Merge, replace or delete settings | [Composition](user-guide/operators.md) |
| Accept command-line overrides | [CLI](user-guide/cli.md) |
| Check values against a schema | [Validation](user-guide/schema-validation.md) |
| Diagnose an error or unexpected result | [Troubleshooting](user-guide/troubleshooting.md) |
| Find syntax and public entrypoints | [Quick reference](user-guide/quick-reference.md) |
| Integrate construction into a framework | [Advanced contracts](user-guide/advanced.md) |

## The essential distinction

A configuration is a **definition**. Resolving it may create **live Python objects**.
`@counts` shares the resolved value of `counts` within the current resolution
mode and generation. `%counts` copies its definition; a copied `_target_` can
construct another object. Copies can themselves contain `@` references to shared
dependencies.

`get()` reads source without configured execution. `resolve()` can execute Python.
Successful `set()` or `update()` calls start a new resolution generation; they do
not rewrite objects already returned to your application.

## About

Sparkwheel originated from MONAI Bundle's configuration system. It supports
standalone Python applications and powers configuration in
[Lighter](https://project-lighter.github.io/lighter/).

[Source and issues](https://github.com/project-lighter/sparkwheel) ·
[API reference](reference/index.md)
