---
title: Sparkwheel
---
<!-- BEGIN: DO NOT REMOVE THIS SECTION -->

#

<style>
    /* Remove content from the left bar (otherwise there's "Home" just sitting there) */
    .md-nav--primary {
    display: none;
    }
</style>

<!-- END: DO NOT REMOVE THIS SECTION -->

<div style="display: flex; justify-content: center;"><img src="assets/images/sparkwheel_banner.png" style="width:65%;"/></div>

<!-- pip install -->
<div style="width:65%; margin:auto; text-align:center">
</br>

```bash
pip install sparkwheel
```
</div>
</br>


<div class="grid cards" markdown>

-   :material-cog-outline:{ .lg .middle } __Declarative Configuration__

    ---

    Define complex Python objects in clean YAML files. Replace boilerplate instantiation code with simple `_target_` declarations.

-   :material-link-variant:{ .lg .middle } __Smart References__

    ---

    Use `@` for **resolved references** (instantiated objects, computed values) or `%` for **raw references** (unprocessed YAML). Keep configurations DRY and maintainable.

-   :material-puzzle-outline:{ .lg .middle } __Flexible Composition__

    ---

    Configs compose naturally by default (merge dicts, extend lists). Use `=` to replace or `~` to delete. Build modular configs for experiments and environments.

-   :material-function-variant:{ .lg .middle } __Python Expressions__

    ---

    Execute code with `$` prefix. Compute values, call functions, and create dynamic configurations on the fly.

-   :material-shield-check-outline:{ .lg .middle } __Schema Validation__

    ---

    Validate configs with Python dataclasses. Catch errors early with type checking and required field validation.

-   :material-console:{ .lg .middle } __CLI Overrides__

    ---

    Override any config value from command line. Perfect for hyperparameter sweeps and quick experiments.

</div>

## Python Objects from YAML

If you're tired of **hardcoding parameters** and want **configuration-driven workflows**, Sparkwheel makes it effortless. Define components in YAML, reference and compose them freely, then instantiate in Python.

=== "Config"

    ```yaml title="config.yaml"
    dataset:
      path: "/data/train"
      num_classes: 10
      batch_size: 32

    model:
      _target_: torch.nn.Sequential
      _args_:
        - _target_: torch.nn.Linear
          in_features: 784
          out_features: "@dataset::num_classes"  # Reference!
        - _target_: torch.nn.ReLU

    training:
      epochs: 10
      learning_rate: 0.001
      steps_per_epoch: "$10000 // @dataset::batch_size"  # Expression!
    ```

=== "Python"

    ```python title="train.py"
    from sparkwheel import Config

    # Load config (or multiple configs!)
    config = Config.load("config.yaml")

    # Access raw values
    batch_size = config["dataset::batch_size"]  # 32

    # Resolve references and expressions
    steps = config.resolve("training::steps_per_epoch")  # 312

    # Instantiate Python objects automatically
    model = config.resolve("model")  # Actual torch.nn.Sequential!
    ```

=== "Experiment Override"

    ```yaml title="experiment_large.yaml"
    # Override specific values, keep the rest (merges by default!)
    model:
      _args_:
        - 0:  # Override first layer
            out_features: 20  # More classes

    training:
      learning_rate: 0.0001  # Lower LR
      # epochs inherited from base!
    ```

    ```python
    # Load base + experiment (composes automatically!)
    config = Config.load(["config.yaml", "experiment_large.yaml"])

    # Or override from CLI
    config = Config.from_cli(
        "config.yaml",
        ["training::learning_rate=0.01", "dataset::batch_size=64"]
    )
    ```

## Understanding References

Sparkwheel has two types of references with distinct purposes:

!!! abstract "@ - Resolved References"

    **Get the final, computed value** after instantiation and evaluation.

    ```yaml
    model:
      _target_: torch.nn.Linear
      in_features: 784
      out_features: 10

    # @ follows the reference and gets the instantiated object
    trained_model: "@model"  # Gets the actual torch.nn.Linear instance
    ```

    Use `@` when you want the **result** of computation.

!!! abstract "% - Raw References"

    **Get the unprocessed YAML content** before any resolution.

    ```yaml
    # base.yaml
    defaults:
      learning_rate: 0.001

    # config.yaml
    # % copies the raw YAML definition (can be from external files or same file)
    optimizer:
      lr: "%base.yaml::defaults::learning_rate"  # Gets raw value: 0.001

    # Or reference within same file
    backup_defaults: "%defaults"  # Gets the entire defaults dict as-is
    ```

    Use `%` when you want to **copy/import raw YAML** (like copy-paste).

## Why Sparkwheel?

!!! tip "Familiar, But More Powerful"

    If you've used **Hydra** or **OmegaConf**, you'll feel right at home. Sparkwheel adds:

    - **Composition-by-default** - Configs merge/extend naturally, no operators needed for common case
    - **List extension** - Lists extend by default (unique vs Hydra!)
    - **`=` replace operator** - Explicit control when you need replacement
    - **`~` delete operator** - Remove inherited keys cleanly (idempotent!)
    - **Python expressions with `$`** - Compute values dynamically
    - **Dataclass validation** - Type-safe configs without boilerplate
    - **Dual reference system** - `@` for resolved values, `%` for raw YAML
    - **Simpler API** - Less magic, clearer behavior

    ```yaml
    # Merges by default - no operator needed!
    model:
      hidden_size: 1024  # Override just this
      ~dropout: null     # Remove dropout
      # Other fields preserved automatically!
    ```

## Start Learning

<div class="grid cards" markdown>

-   :material-rocket-launch-outline:{ .lg .middle } __Quick Start__

    ---

    Get productive in 5 minutes with a hands-on tutorial

    [:octicons-arrow-right-24: Quick Start](getting-started/quickstart.md)

-   :material-book-open-page-variant:{ .lg .middle } __User Guide__

    ---

    Deep dive into references, expressions, and composition

    [:octicons-arrow-right-24: Core Concepts](user-guide/basics.md)

-   :material-lightbulb-on-outline:{ .lg .middle } __Examples__

    ---

    See complete real-world configuration patterns

    [:octicons-arrow-right-24: View Examples](examples/simple.md)

-   :material-code-tags:{ .lg .middle } __API Reference__

    ---

    Complete API documentation and reference

    [:octicons-arrow-right-24: Browse API](reference/)

</div>

## Feature Deep Dives

<div class="grid cards" markdown>

-   :material-link:{ .lg .middle } [**References**](user-guide/references.md)

    Link config values with `@` to eliminate duplication

-   :material-code-braces:{ .lg .middle } [**Expressions**](user-guide/expressions.md)

    Execute Python code in configs with `$`

-   :material-merge:{ .lg .middle } [**Composition & Operators**](user-guide/operators.md)

    Composition-by-default with `=` (replace) and `~` (delete) operators

-   :material-check-circle-outline:{ .lg .middle } [**Schema Validation**](user-guide/schema-validation.md)

    Validate with Python dataclasses

-   :material-console-line:{ .lg .middle } [**CLI Support**](user-guide/cli.md)

    Override configs from command line

-   :material-cog-transfer:{ .lg .middle } [**Instantiation**](user-guide/instantiation.md)

    Create Python objects with `_target_`

</div>

## About

Sparkwheel is a hard fork of [MONAI Bundle](https://github.com/Project-MONAI/MONAI/tree/dev/monai/bundle)'s configuration system, refined and expanded for general-purpose use. We're deeply grateful to the MONAI team for their excellent foundation.

Sparkwheel powers [Lighter](https://project-lighter.github.io/lighter/), a configuration-driven deep learning framework built on PyTorch Lightning.

**Ready to contribute?** [:octicons-mark-github-16: View on GitHub](https://github.com/project-lighter/sparkwheel)

<br/>
