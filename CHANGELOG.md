# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog][],
and this project adheres to [Semantic Versioning][].

[keep a changelog]: https://keepachangelog.com/
[semantic versioning]: https://semver.org/spec/

## [0.1.2]

### Added

- The sphinx extension ships templates for `sphinx.ext.autosummary` that were previously part of `cookiecutter-scverse`.

## [0.1.1]

### Fixed

- The sphinx extension no longer adds parameter types to `override` and `reset` docstrings
  if the users have `sphinx-autodoc-typehints` enabled or `autodoc_typehints = 'description' | 'both'` set.

## [0.1.0]

### Fixed

- Allow additional methods on `Settings` subclasses.
- Allow the Sphinx extension to go anywhere in the `conf.py` extension list.
- `anndata` isn’t a core dependency anymore again.

## [0.0.9]

### Added

- A Sphinx extension to take care of documentation. This moves docstring processing from import time to documentation building time.
- A reusable `datasets` subpackage (behind the `datasets` extra): typed `DatasetEntry`/
  `FileEntry` + `parse_registry` (YAML), a thin pooch-based `fetch` (SHA-256 verification,
  retries, archive processors), and a pluggable `type -> loader` registry
  (`register_loader`) so packages can share dataset-download infrastructure. Ships built-in
  `anndata` and `spatialdata` loaders (the latter behind the `spatialdata` extra); other
  types are consumer-registered.
- `anndata` is now a core dependency.

### Changed

- Docstrings are no longer generated or modified at import time.

### Fixed

- Marking a setting as `Field(deprecated=...)` will show a deprecation notice in the documentaiton.

## [0.0.8]

### Fixed

- The `Settings` class can now handle `.env` files containing unrelated environment variables.

## [0.0.7]

### Added

- A `reset` method for `Settings` to reset settings to their default values.

## [0.0.6]

### Added

- A `deprecated_arg` decorator to deprecate function arguments.

## [0.0.5]

### Added

- The `docstring_style` used by scanpy, `"scverse"`, which looks like `"numpy"` but with no parameter types in the docstring.

### Changed

- The `Settings` class and the `make_register_namespace_decorator` function now require passing a `docstring_style` argument.

### Fixed

- The `Settings` docstrings longer have `:value: PydanticUndefined` for fields with no defaults.
- Remove the “default” text from `override` parameters so we don’t imply that `override` resets all settings the user isn’t overriding.

## [0.0.4]

### Added

- A `Settings` base class that packages can inherit from for their settings. This is based
  on [Pydantic Settings](https://pydantic.dev/docs/validation/latest/concepts/pydantic_settings/) and
  provides validation for settings values as well as loading settings from environment variables and
  `.env` files.

## [0.0.3]

### Added

- A `deprecated` decorator wrapping `warnings.deprecated` that additionally modifies the
  docstring to include a deprecation notice.

## [0.0.2]

### Removed

- The Pandas utility functions

## [0.0.1]

- Initial release

[Unreleased]: https://github.com/scverse/scverse-misc/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/scverse/scverse-misc/releases/tag/v0.1.1
[0.1.1]: https://github.com/scverse/scverse-misc/releases/tag/v0.1.1
[0.1.0]: https://github.com/scverse/scverse-misc/releases/tag/v0.1.0
[0.0.9]: https://github.com/scverse/scverse-misc/releases/tag/v0.0.9
[0.0.8]: https://github.com/scverse/scverse-misc/releases/tag/v0.0.8
[0.0.7]: https://github.com/scverse/scverse-misc/releases/tag/v0.0.7
[0.0.6]: https://github.com/scverse/scverse-misc/releases/tag/v0.0.6
[0.0.5]: https://github.com/scverse/scverse-misc/releases/tag/v0.0.5
[0.0.4]: https://github.com/scverse/scverse-misc/releases/tag/v0.0.4
[0.0.3]: https://github.com/scverse/scverse-misc/releases/tag/v0.0.3
[0.0.2]: https://github.com/scverse/scverse-misc/releases/tag/v0.0.2
[0.0.1]: https://github.com/scverse/scverse-misc/releases/tag/v0.0.1
