# Documentation Fixes Applied

## Summary

Conducted a thorough audit of the source code and corrected documentation to match the actual implementation.

## Critical Issues Fixed

### 1. Incorrect Reference Separator ✅
**Problem**: All documentation used `#` as the nested reference separator, but the code uses `::`.

**Evidence**:
- `constants.py`: `ID_SEP_KEY = "::"`
- `reference_resolver.py`: Normalizes `#` to `::` for backward compatibility
- All examples and tests use `::`

**Fix Applied**:
- Updated all documentation to use `::` as the primary separator
- Added backward compatibility note explaining that `#` still works (gets normalized to `::`)
- Fixed examples in:
  - `docs/index.md`
  - `docs/getting-started/quickstart.md`
  - `docs/user-guide/references.md`
  - `docs/user-guide/expressions.md`
  - `docs/user-guide/basics.md`
  - `docs/user-guide/advanced.md`
  - `docs/examples/*.md`

### 2. Missing `_mode_` Documentation ✅
**Problem**: The `_mode_` special key was not documented anywhere.

**Source**: From `config_item.py:104-108`:
```python
- ``"_mode_"`` (optional): operating mode:
    - ``"default"``: returns ``component(**kwargs)``
    - ``"callable"``: returns ``component`` or ``functools.partial(component, **kwargs)``
    - ``"debug"``: returns ``pdb.runcall(component, **kwargs)``
```

**Fix Applied**:
- Added comprehensive `_mode_` documentation to `docs/user-guide/advanced.md`
- Added `_mode_` section to `docs/user-guide/instantiation.md` with examples
- Documented all three modes with code examples

### 3. JSON Support Claim ✅
**Problem**: Initial documentation incorrectly claimed JSON support.

**Evidence**: `config_parser.py:83`: `suffixes = ("yaml", "yml")` - YAML only

**Fix Applied**:
- Removed all mentions of JSON support
- Clarified that Sparkwheel is YAML-only
- Updated descriptions in pyproject.toml, README.md, and all docs

## Verification

### Code Analysis Performed
1. ✅ Read all Python source files in `src/sparkwheel/`
2. ✅ Verified constants and special keys
3. ✅ Checked reference separator implementation
4. ✅ Verified special keys (`_target_`, `_args_`, `_disabled_`, `_requires_`, `_mode_`)
5. ✅ Confirmed YAML-only support (no JSON)

### Documentation Updated
1. ✅ Main index page
2. ✅ Quick start guide
3. ✅ All user guide pages
4. ✅ All examples
5. ✅ Advanced features page
6. ✅ README.md
7. ✅ CHANGELOG.md
8. ✅ QUICKSTART.md
9. ✅ CONTRIBUTING.md

## Correct Usage Now Documented

### References
```yaml
# Correct (primary, preferred)
model:
  num_outputs: "@dataset::num_classes"

# Also works (backward compatibility)
model:
  num_outputs: "@dataset#num_classes"
```

### Instantiation Modes
```yaml
# Default mode (instantiate normally)
model:
  _target_: torch.nn.Linear
  _mode_: "default"
  in_features: 784
  out_features: 10

# Callable mode (return function/class)
factory:
  _target_: torch.nn.Linear
  _mode_: "callable"
  in_features: 784

# Debug mode (run in pdb)
debug:
  _target_: mymodule.MyClass
  _mode_: "debug"
```

## Files Modified

### Documentation
- `docs/index.md`
- `docs/getting-started/installation.md`
- `docs/getting-started/quickstart.md`
- `docs/user-guide/basics.md`
- `docs/user-guide/references.md`
- `docs/user-guide/expressions.md`
- `docs/user-guide/instantiation.md`
- `docs/user-guide/advanced.md`
- `docs/examples/simple.md`
- `docs/examples/deep-learning.md`
- `docs/examples/custom-classes.md`
- `docs/contributing.md`

### Source Code Comments
- `src/sparkwheel/utils/misc.py` - Updated JSON comment to clarify YAML usage
- `src/sparkwheel/__init__.py` - Added note about YAML-only format

### Project Files
- `README.md`
- `CHANGELOG.md`
- `QUICKSTART.md`
- `CONTRIBUTING.md`
- `pyproject.toml`

## Result

Documentation now accurately reflects the actual implementation:
- ✅ Uses `::` as primary separator (with `#` backward compatibility note)
- ✅ Documents all special keys including `_mode_`
- ✅ Correctly states YAML-only support
- ✅ All examples use correct syntax
- ✅ Comprehensive coverage of all features
