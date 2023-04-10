# SPDX-FileCopyrightText: Copyright © 2023 Jamie Nguyen <j@jamielinux.com>
# SPDX-License-Identifier: MIT
# pyright: strict

"""Handle command-line arguments."""

import argparse
import dataclasses
import os
import shutil
import sys
from enum import Enum, auto
from typing import List, Optional, Set, Union

from .platform import WINDOWS
from .pyright import Severity

__all__ = ["parse_cli"]

HELP: str = """\
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

"""


UNFILTERED_ARGS: Set[str] = {
    "--dependencies",
    "--stats",
    "--version",
}


PLAINTEXT_ARGS: Set[str] = {
    "--createstub",
    "--ignoreexternal",
    "--verifytypes",
}

NON_JSON_ARGS: Set[str] = PLAINTEXT_ARGS | UNFILTERED_ARGS


class ArgumentParser(argparse.ArgumentParser):
    """A subclass of `argparse.ArgumentParser` just to change the returncode."""

    def error(self, message: str):
        """Custom `error` method to exit with a returncode of 4 instead of 2.

        Pyright exits with a returncode of 4 when launched with invalid command-line
        arguments, so we should do the same.

        The `exit_on_error` parameter for `argparse.ArgumentParser` was only introduced
        in Python 3.9, so we can't make use of that.
        """
        self.print_usage(sys.stderr)
        args = {"prog": self.prog, "message": message}
        self.exit(4, ("%(prog)s: error: %(message)s\n") % args)


class CustomHelpFormatter(argparse.HelpFormatter):
    """Custom help formatter to display exactly the same help text as pyright."""

    def format_help(self) -> str:
        """Print help message."""
        return HELP


class Mode(Enum):
    """The mode of operation for pyright-polite."""

    # Filter stderr. Parse JSON output in stdout.
    JSON = auto()

    # Filter both stderr and stdout. No JSON expected.
    PLAINTEXT = auto()

    # Don't capture stderr/stdout (ie, let pyright write directly to the terminal).
    UNFILTERED = auto()


@dataclasses.dataclass(frozen=True)
class CommandLine:
    """The argv list and the deduced mode of operation."""

    argv: List[str]
    mode: Mode


def find_pyright() -> str:
    """Find the pyright executable.

    `asyncio.create_subprocess_exec()` requires the full path on Windows, and we want to
    avoid using `asyncio.create_subprocess_shell()`.

    Returns:
        str: The fully-qualified absolute path to the pyright executable.
    """
    # The default mode for shutil.which() is `F_OK | X_OK`, but to give a more helpful
    # error message we'll check X_OK in a separate step.
    pyright: Optional[str] = shutil.which("pyright", mode=os.F_OK)

    if pyright is None:
        sys.stderr.write("pyright-polite: error: pyright could not be found in your PATH\n")
        returncode = 9009 if WINDOWS else 127
        sys.exit(returncode)
    if not os.access(pyright, os.X_OK):  # always True on Windows
        sys.stderr.write("pyright-polite: error: pyright is not executable\n")
        sys.exit(126)

    return pyright


def prepare_argv(parsed_args: argparse.Namespace) -> List[str]:
    """Prepare argv for `asyncio.create_subprocess_exec()`.

    This includes the pyright executable (ie, argv[0]).

    pyright has args that are incompatible with each other, but instead of recreating
    pyright's compatibility logic we'll just let pyright complain if it receives
    incompatible args.

    Args:
        parsed_args (argparse.Namespace): The parsed arguments.

    Returns:
        List[str]: The argv list to pass to `asyncio.create_subprocess_exec()`.
    """
    pyright: str = find_pyright()
    argv: List[str] = [pyright]

    # If --version is passed anywhere on the command-line, ignore all other arguments
    # and just skip to executing `pyright --version`.
    if parsed_args.version:
        argv.append("--version")
        return argv

    arg_mapping = {
        "createstub": "--createstub",
        "dependencies": "--dependencies",
        "ignoreexternal": "--ignoreexternal",
        "lib": "--lib",
        "level": "--level",
        "project": "--project",
        "pythonplatform": "--pythonplatform",
        "pythonversion": "--pythonversion",
        "skipunannotated": "--skipunannotated",
        "stats": "--stats",
        "typeshed_path": "--typeshed-path",
        "venv_path": "--venv-path",
        "warnings": "--warnings",
        "verbose": "--verbose",
        "verifytypes": "--verifytypes",
        "watch": "--watch",
    }

    for arg_property, flag in arg_mapping.items():
        arg_value: Union[bool, List[str], None] = getattr(parsed_args, arg_property)
        if arg_value:
            argv.append(flag)
            if isinstance(arg_value, list):
                argv.append(arg_value[0])

    # If the user passes `--outputjson` manually, always pass this to pyright even if
    # it will clash with one of the other command-line arguments that don't support
    # this mode. We'll just let pyright complain to the user about the clash.
    if parsed_args.outputjson or not any(arg in NON_JSON_ARGS for arg in argv[1:]):
        argv.append("--outputjson")

    for file in parsed_args.files:
        argv.append(file)

    return argv


def deduce_mode(args: List[str]) -> Mode:
    """Deduce the mode of operation based on the arguments passed to pyright.

    Returns:
        Mode: The deduced mode of operation.
    """
    mode: Mode = Mode.JSON

    if "--outputjson" in args:
        return mode

    if any(arg in PLAINTEXT_ARGS for arg in args):
        mode = Mode.PLAINTEXT

    if any(arg in UNFILTERED_ARGS for arg in args):
        mode = Mode.UNFILTERED

    return mode


def parse_cli() -> CommandLine:
    """Handle command-line arguments.

    Returns:
        CommandLine: The argv list and the deduced mode of operation.
    """
    parser: argparse.ArgumentParser = ArgumentParser(
        formatter_class=CustomHelpFormatter,
        allow_abbrev=False,
    )
    parser.add_argument("--createstub", nargs=1, type=str)
    parser.add_argument("--dependencies", action="store_true")
    parser.add_argument("--ignoreexternal", action="store_true")
    parser.add_argument("--lib", action="store_true")
    parser.add_argument("--level", nargs=1, choices=[s.name.lower() for s in Severity])
    parser.add_argument("--outputjson", action="store_true")
    parser.add_argument("-p", "--project", nargs=1, type=str)
    parser.add_argument("--pythonplatform", nargs=1, type=str)
    parser.add_argument("--pythonversion", nargs=1, type=str)
    parser.add_argument("--skipunannotated", action="store_true")
    parser.add_argument("--stats", action="store_true")
    parser.add_argument("-t", "--typeshed-path", nargs=1, type=str)
    parser.add_argument("-v", "--venv-path", nargs=1, type=str)
    parser.add_argument("--warnings", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--verifytypes", nargs=1, type=str)
    parser.add_argument("--version", action="store_true")
    parser.add_argument("-w", "--watch", action="store_true")
    parser.add_argument("files", nargs="*")

    parsed_args: argparse.Namespace = parser.parse_args()
    argv: List[str] = prepare_argv(parsed_args)
    mode: Mode = deduce_mode(argv[1:])
    return CommandLine(argv=argv, mode=mode)
