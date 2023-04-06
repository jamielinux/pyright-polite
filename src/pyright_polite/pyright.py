# SPDX-FileCopyrightText: Copyright © 2023 Jamie Nguyen <j@jamielinux.com>
# SPDX-License-Identifier: MIT
# pyright: strict

"""Methods and classes for parsing and formatting pyright's JSON output."""

import dataclasses
import json
import re
import sys
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar

from colorama import Fore

T = TypeVar("T")


__all__ = ["PyrightJsonError", "parse_pyright", "print_filtered", "print_pyright"]


class PyrightJsonError(Exception):
    """An error in the pyright JSON output."""

    def __init__(self, msg: str):
        """Error message."""
        super().__init__(f"pyright-polite: error: pyright returned unexpected JSON ({msg})")


class Severity(Enum):
    """Severity levels for pyright diagnostics."""

    ERROR = auto()
    WARNING = auto()


class SeverityColor(Enum):
    """Terminal colors for pyright severity levels."""

    ERROR = Fore.RED
    WARNING = Fore.CYAN


@dataclasses.dataclass(frozen=True)
class Diagnostic:
    """A single diagnostic from the pyright run."""

    file: str
    severity: Severity
    message: str
    start_line: int
    start_char: int
    rule: Optional[str] = None


@dataclasses.dataclass(frozen=True)
class Summary:
    """The summary from the pyright run."""

    analyzed: int
    errors: int
    warnings: int
    informations: int


@dataclasses.dataclass(frozen=True)
class Pyright:
    """All summary and diagnostic information from the pyright run."""

    summary: Summary
    diagnostics: List[Diagnostic]


def _get_key_validate(dictionary: Dict[str, Any], name: str, key: str, expected_type: Type[T]) -> T:
    if key not in dictionary:
        raise PyrightJsonError(f"{name} is missing {key}")

    if not isinstance(dictionary[key], expected_type):
        raise PyrightJsonError(f"{name}.{key} is not of type {expected_type.__name__}")

    return dictionary[key]


def _parse_summary(json_output: Dict[str, Any]) -> Summary:
    if "summary" not in json_output:
        raise PyrightJsonError("summary is missing")

    if not isinstance(json_output["summary"], dict):
        raise PyrightJsonError("summary is invalid")

    summary: Dict[str, Any] = json_output["summary"]
    analyzed: int = _get_key_validate(summary, "summary", "filesAnalyzed", int)
    errors: int = _get_key_validate(summary, "summary", "errorCount", int)
    warnings: int = _get_key_validate(summary, "summary", "warningCount", int)
    informations: int = _get_key_validate(summary, "summary", "informationCount", int)

    return Summary(analyzed, errors, warnings, informations)


def _parse_diagnostics(json_output: Dict[str, Any]) -> List[Diagnostic]:
    diagnostics: List[Diagnostic] = []

    if "generalDiagnostics" not in json_output:
        raise PyrightJsonError("generalDiagnostics is missing")
    if not isinstance(json_output["generalDiagnostics"], list):
        raise PyrightJsonError("generalDiagnostics is invalid")

    item: Any
    for item in json_output["generalDiagnostics"]:
        if not isinstance(item, dict):
            raise PyrightJsonError("invalid diagnostic")

        dictionary: Dict[str, Any] = item

        file: str = _get_key_validate(dictionary, "diagnostic", "file", str)

        severity_field: str = _get_key_validate(dictionary, "diagnostic", "severity", str)
        severity_field = severity_field.upper()
        if not any(severity_field == sev.name for sev in Severity):
            raise PyrightJsonError("diagnostic with invalid severity")
        severity: Severity = getattr(Severity, severity_field)

        # When a diagnostic spans multiple lines, pyright indents additional lines by
        # four spaces. Well, actually two spaces and two non-breaking spaces due to
        # https://github.com/microsoft/pyright/commit/a67c0240ab. pyright's JSON output
        # only includes the two non-breaking spaces, so we add two more regular spaces.
        message_field: str = _get_key_validate(dictionary, "diagnostic", "message", str)
        message: str = message_field.replace("\n", "\n  ")

        if "range" not in item or not isinstance(item["range"], dict):
            raise PyrightJsonError("diagnostic with missing or invalid range")
        range_dict: Dict[str, Any] = item["range"]
        start_dict: Dict[str, Any] = _get_key_validate(range_dict, "diagnostic", "start", dict)
        start_line = _get_key_validate(start_dict, "range.start", "line", int)
        start_char = _get_key_validate(start_dict, "range.start", "character", int)

        # Not all diagnostics have a rule.
        rule: str = dictionary.get("rule", None)

        diagnostic: Diagnostic = Diagnostic(file, severity, message, start_line, start_char, rule)
        diagnostics.append(diagnostic)

    return diagnostics


def _print_analyzed(summary: Summary) -> None:
    suffix = "s" if summary.analyzed != 1 else ""
    sys.stdout.write(f"Found {summary.analyzed} source file{suffix}\n")


def _print_diagnostics(diagnostics: List[Diagnostic]) -> None:
    file: str = ""
    for diagnostic in diagnostics:
        msg: List[str] = []
        if diagnostic.file != file:
            file = diagnostic.file
            msg.append(f"{file}\n")

        msg.append(f"  {file}:")
        msg.append(f"{Fore.YELLOW}{diagnostic.start_line + 1}{Fore.RESET}:")
        msg.append(f"{Fore.YELLOW}{diagnostic.start_char + 1}{Fore.RESET} - ")

        color: SeverityColor = SeverityColor[diagnostic.severity.name].value
        msg.append(f"{color}{diagnostic.severity.name.lower()}{Fore.RESET}: {diagnostic.message}")

        if diagnostic.rule:
            msg.append(f" {Fore.LIGHTBLACK_EX}({diagnostic.rule}){Fore.RESET}")

        msg.append("\n")
        sys.stdout.write("".join(msg))


def _print_summary(summary: Summary) -> None:
    msg: str = (
        f"{summary.errors} errors, "
        f"{summary.warnings} warnings, "
        f"{summary.informations} informations"
        "\n"
    )
    sys.stdout.write(msg)


def print_filtered(line: str) -> None:
    """Filter out lines that are usually completely useless to see over and over.

    If the input line doesn't match the regex, print it to stdout.

    Args:
        line (str): The line of text to filter.
    """
    ignore_start: Tuple[str, ...] = (
        # Assuming Python version 3.11
        # Assuming Python platform Linux
        "Assuming ",
        # Auto-excluding **/node_modules
        # Auto-excluding **/__pycache__
        # Auto-excluding **/.*
        "Auto-excluding ",
        # Completed in ...sec
        "Completed in ",
        # Found 2 source files
        "Found ",
        # Loading pyproject.toml file at ...
        "Loading ",
        # No configuration file found.
        "No configuration ",
        # No include entries specified; assuming ...
        "No include entries ",
        # No source files found.
        "No source ",
        # No pyproject.toml file found.
        "No pyproject.toml ",
        # Please install the new version or set PYRIGHT_PYTHON_FORCE_VERSION to `latest`
        "Please install the new version",
        # Searching for source files
        "Searching ",
        # WARNING: there is a new pyright version available (vX.X.X -> vX.X.X).
        "WARNING: there is a new pyright",
        # pyproject.toml file found at ...
        "pyproject.toml file found ",
        # pyright MAJOR.MINOR.PATCH
        r"pyright \d+\.\d+\.\d+",
        # stubPath .../typings is not a valid directory.
        "stubPath ",
    )
    ignore_pattern: re.Pattern[str] = re.compile(rf"^({'|'.join(ignore_start)})")

    if not ignore_pattern.search(line):
        # readline() may return partial data (ie, without a newline character) if it
        # receives an EOF from the stream and there's no "\n". Make sure we append a
        # newline character in that situation.
        output_line: str = line if line.endswith("\n") else f"{line}\n"
        sys.stdout.write(output_line)


def parse_pyright(json_data: str) -> Pyright:
    """Parse pyright's JSON output.

    Args:
        json_data (str): The JSON output from pyright as a string.

    Returns:
        Pyright: Pyright object containing the parsed summary and diagnostics.
    """
    try:
        json_output: Dict[str, Any] = json.loads(json_data)
    except json.JSONDecodeError as exc:
        raise PyrightJsonError(f"{exc}") from exc

    summary: Summary = _parse_summary(json_output)
    diagnostics: List[Diagnostic] = _parse_diagnostics(json_output)
    return Pyright(summary, diagnostics)


def print_pyright(pyright: Pyright) -> None:
    """Format the summary and diagnostic data we've parsed from pyright.

    Args:
        pyright (Pyright): Pyright object containing the parsed summary and diagnostics.
    """
    _print_analyzed(pyright.summary)
    _print_diagnostics(pyright.diagnostics)
    _print_summary(pyright.summary)
