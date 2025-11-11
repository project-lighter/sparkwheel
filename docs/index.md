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

-   :material-cog-outline:{ .lg .middle } __Declarative__

    ---

    Build complex applications using simple YAML configs. Replace boilerplate code with clean configuration!

-   :material-link-variant:{ .lg .middle } __References__

    ---

    Link configuration values with `@` for resolved Python objects or `%` for raw YAML values. Keep your configs DRY!

-   :material-puzzle-outline:{ .lg .middle } __Composition__

    ---

    Combine multiple configuration files seamlessly. Build modular configs that can be mixed and matched.

-   :material-function-variant:{ .lg .middle } __Expressions__

    ---

    Execute Python code withing config with `$` prefix. Compute values, call functions, and create dynamic configurations.

</div>

## Bring Configuration to your Workflows

If you're dealing with **constantly changing parameters** and want to **separate configuration from code**, Sparkwheel is here to help. Define your components in YAML files and use them in Python with ease.

```yaml title="config.yaml"
model:
  _target_: torch.nn.Linear
  in_features: 784
  out_features: 10
```

```python title="main.py"
from sparkwheel import Config

config = Config.load("config.yaml")

model = config.resolve("model")
```

## Next Steps

<div class="grid cards" markdown>

-   :material-school-outline:{ .lg .middle } __Tutorials__

    ---

    Learn the basics with step-by-step guides

    [:octicons-arrow-right-24: Start learning](user-guide/basics.md)

-   :material-book-open-page-variant:{ .lg .middle } __Examples__

    ---

    Explore real-world configuration patterns

    [:octicons-arrow-right-24: See examples](examples/simple.md)

-   :material-code-tags:{ .lg .middle } __API Reference__

    ---

    Dive into the complete API documentation

    [:octicons-arrow-right-24: Browse API](reference/)

-   :material-github:{ .lg .middle } __Source Code__

    ---

    Explore the codebase and contribute

    [:octicons-arrow-right-24: View on GitHub](https://github.com/project-lighter/sparkwheel)

</div>

## About

Sparkwheel is a hard fork of [MONAI](https://github.com/Project-MONAI/MONAI)'s configuration system, stripped down to focus and improve its usability for general purposes. We're deeply grateful to the MONAI team for their excellent foundation.

Sparkwheel powers [Lighter](https://project-lighter.github.io/lighter/), our config-based deep learning framework built on PyTorch Lightning. 

<br/>