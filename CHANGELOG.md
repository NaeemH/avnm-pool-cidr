# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0]

### Added
- `apc next-prefix POOL --size N` &mdash; print the first free `/N` subnet inside the pool.
- `apc list POOL` &mdash; show every resource currently reserving space from a pool.
- `apc usage POOL` &mdash; per-parent-prefix utilization summary (addresses + percent).
- Auth shells out to the Azure CLI (`az`); no embedded credentials.
- Console scripts: `avnm-pool-cidr` and the short alias `apc`.

[Unreleased]: https://github.com/NaeemH/avnm-pool-cidr/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/NaeemH/avnm-pool-cidr/releases/tag/v0.1.0
