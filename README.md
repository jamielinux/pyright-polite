# pyright-polite

[![PyPi Version][pypi-img]][pypi-url]
[![License][license-img]][license-url]
[![Continuous Integration][ci-img]][ci-url]
[![Code Coverage][coverage-img]][coverage-url]
[![Python Versions][python-img]][python-url]

[pypi-img]: https://img.shields.io/pypi/v/pyright-polite.svg
[pypi-url]: https://pypi.org/project/pyright-polite
[license-img]:  https://img.shields.io/github/license/jamielinux/pyright-polite.svg
[license-url]: https://github.com/jamielinux/pyright-polite/blob/main/LICENSE
[ci-img]: https://github.com/jamielinux/pyright-polite/actions/workflows/ci.yml/badge.svg
[ci-url]: https://github.com/jamielinux/pyright-polite/actions/workflows/ci.yml
[coverage-img]: https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/jamielinux/ed2d4df7c2b137ac89778db60ef8894f/raw/pyright-polite.covbadge.json
[coverage-url]: https://github.com/jamielinux/pyright-polite/actions/workflows/ci.yml
[python-img]: https://img.shields.io/pypi/pyversions/pyright-polite.svg
[python-url]: https://pypi.org/project/pyright-polite

---

**pyright-polite** is an intelligent cross-platform wrapper for [pyright][0] that makes
it less noisy.

Force pyright to be more respectful with your attention :rotating_light:

[0]: https://github.com/microsoft/pyright

## What does it do?

With **pyright-polite**:

```console
$ pyright-polite
Found 7 source files
0 errors, 0 warnings, 0 informations
```

Without:

```console
$ pyright
WARNING: there is a new pyright version available (v1.1.300 -> v1.1.301).
Please install the new version or set PYRIGHT_PYTHON_FORCE_VERSION to `latest`

No configuration file found.
pyproject.toml file found at /projects/pyright_polite.
Loading pyproject.toml file at /projects/pyright_polite/pyproject.toml
Assuming Python version 3.11
Assuming Python platform Linux
Auto-excluding **/node_modules
Auto-excluding **/__pycache__
Auto-excluding **/.*
stubPath /projects/pyright_polite/typings is not a valid directory.
Searching for source files
Found 7 source files
pyright 1.1.300
0 errors, 0 warnings, 0 informations
Completed in 1.006sec
```

Now pyright is just as polite as your other tools:

```console
$ hatch run lint
cmd [1] | - ruff check .
cmd [2] | - black --quiet --check --diff .
cmd [3] | - pyright-polite
Found 8 source files
0 errors, 0 warnings, 0 informations
cmd [4] | - ssort --check --diff .
8 files would be left unchanged
```

Error messages are still shown (eg, if your pyright config file is invalid).

## Installation

You need `pyright` installed (ie, available somewhere in your `PATH`).

See pyright's installation instructions [here][installation]. Usually people install
either the [pyright npm][pkg_npm] or the [pyright PyPI][pkg_pypi] package.

```console
$ npm install pyright  # alternatively: pip install pyright
$ pip install pyright-polite
```

Linux, macOS and Windows are all supported.

[pkg_pypi]: https://pypi.org/project/pyright/
[pkg_npm]: https://www.npmjs.com/package/pyright
[installation]: https://microsoft.github.io/pyright/#/installation

## Usage

**pyright-polite** takes the same arguments as pyright.

```console
$ pyright-polite -h
Usage: pyright-polite [options] files...
  Options:
  --createstub <IMPORT>              Create type stub file(s) for import
  --dependencies                     Emit import dependency information
  -h,--help                          Show this help message
  --ignoreexternal                   Ignore external imports for --verifytypes
  --lib                              Use library code to infer types when stubs are missing
  --level <LEVEL>                    Minimum diagnostic level (error or warning)
  --outputjson                       Output results in JSON format
  -p,--project <FILE OR DIRECTORY>   Use the configuration file at this location
  --pythonplatform <PLATFORM>        Analyze for a specific platform (Darwin, Linux, Windows)
  --pythonversion <VERSION>          Analyze for a specific version (3.3, 3.4, etc.)
  --skipunannotated                  Skip analysis of functions with no type annotations
  --stats                            Print detailed performance stats
  -t,--typeshed-path <DIRECTORY>     Use typeshed type stubs at this location
  -v,--venv-path <DIRECTORY>         Directory that contains virtual environments
  --verbose                          Emit verbose diagnostics
  --verifytypes <PACKAGE>            Verify type completeness of a py.typed package
  --version                          Print Pyright version
  --warnings                         Use exit code of 1 if warnings are reported
  -w,--watch                         Continue to run and watch for changes


  Note: pyright-polite does not filter output from `--dependencies` or `--stats`.

```

## How does it work?

**pyright-polite** is hilariously over-engineered, but robust.

It aims to display everything in exactly the same format and colorisation as pyright
(minus the useless messages), and takes advantage of pyright's `--outputjson` option
when possible. It launches `pyright` as a subprocess and reads from both stderr and
stdout using `asyncio` tasks, which means that `--watch` is also supported.

For insight into what messages get hidden, see the [`print_filtered`][print_filtered]
method.

[print_filtered]: https://github.com/jamielinux/pyright-polite/blob/main/src/pyright_polite/pyright.py#L183-L233

## Isn't this a bit overkill?

Yes :rofl:

It was primarily a fun weekend project to learn `asyncio`.

## Why is pyright so noisy?

If you're wondering why `pyright` has to remind us that `typings is not a valid
directory` (among other useless messages) on literally every single launch, see
[pyright #4594][issue4594] for what the developers have to say:

> The current information output by the cli is there for a reason.

[issue4594]: https://github.com/microsoft/pyright/issues/4594

## License

`pyright-polite` is distributed under the terms of the [MIT][license] license.

[license]: https://spdx.org/licenses/MIT.html
