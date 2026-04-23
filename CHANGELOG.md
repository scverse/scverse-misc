# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog][],
and this project adheres to [Semantic Versioning][].

[keep a changelog]: https://keepachangelog.com/en/1.1.0/
[semantic versioning]: https://semver.org/spec/v2.0.0.html

## [0.0.4] (unreleased)

## Added

- A `Settings` base class that packages can inherit from for their settings. This is based
  on [Pydantic Settings](https://pydantic.dev/docs/validation/latest/concepts/pydantic_settings/) and
  provides validation for settings values as well as loading settings from environment variables and
  `.env` files.

## [0.0.3]

## Added

- A `deprecated` decorator wrapping `warnings.deprecated` that additionally modifies the
  docstring to include a deprecation notice.

## [0.0.2]

## Removed

- The Pandas utility functions

## [0.0.1]

- Initial release

[0.0.4]: https://github.com/scverse/scverse-misc/releases/tag/v0.0.4
[0.0.3]: https://github.com/scverse/scverse-misc/releases/tag/v0.0.3
[0.0.2]: https://github.com/scverse/scverse-misc/releases/tag/v0.0.2
[0.0.1]: https://github.com/scverse/scverse-misc/releases/tag/v0.0.1
