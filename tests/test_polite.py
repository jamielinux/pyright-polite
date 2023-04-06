# SPDX-FileCopyrightText: Copyright © 2023 Jamie Nguyen <j@jamielinux.com>
# SPDX-License-Identifier: MIT

import asyncio
import signal
from unittest.mock import patch

import pytest
from pyright_polite.cli import Mode
from pyright_polite.polite import StreamName
from pyright_polite.pyright import PyrightJsonError


async def test_stderr_with_extra_message(utils, capsys, stderr_with_extra_message):
    await utils.mock_subproc_async(
        capsys,
        subproc_stderr=stderr_with_extra_message,
        expected_stdout="pyright-polite should not filter this line.\n",
    )


async def test_no_source_files_found(utils, capsys, stdout_no_files):
    await utils.mock_subproc_async(
        capsys,
        subproc_stdout=stdout_no_files,
        expected_stdout="Found 0 source files\n0 errors, 0 warnings, 0 informations\n",
    )


async def test_empty_bytes(utils, capsys):
    side_effect = [False] * 10 + [True] * 30
    with patch("asyncio.streams.StreamReader.at_eof", side_effect=side_effect):
        await utils.mock_subproc_async(
            capsys,
        )


@pytest.mark.parametrize(
    ("subproc_stdout", "error"),
    [
        ("stdout_no_json", "unexpected EOF"),
        pytest.param(
            "stdout_invalid_json",
            "Expecting property name enclosed in double quotes: line 2 column 1 (char 2)",
            marks=pytest.mark.skipif(
                "platform.python_implementation() != 'CPython'", reason="CPython-only"
            ),
        ),
        pytest.param(
            "stdout_invalid_json",
            "Key name must be string at char: line 2 column 1 (char 2)",
            marks=pytest.mark.skipif(
                "platform.python_implementation() != 'PyPy'", reason="PyPy-only"
            ),
        ),
        ("stdout_no_summary", "summary is missing"),
        ("stdout_summary_wrong_type", "summary is invalid"),
        ("stdout_summary_no_analyzed", "summary is missing filesAnalyzed"),
        ("stdout_summary_analyzed_wrong_type", "summary.filesAnalyzed is not of type int"),
        ("stdout_no_diagnostics", "generalDiagnostics is missing"),
        ("stdout_diagnostics_wrong_type", "generalDiagnostics is invalid"),
        ("stdout_diagnostic_wrong_type", "invalid diagnostic"),
        ("stdout_diagnostic_no_range", "diagnostic with missing or invalid range"),
        ("stdout_diagnostic_invalid_severity", "diagnostic with invalid severity"),
    ],
)
async def test_bad_json(utils, capsys, request, subproc_stdout, error):
    expected_stderr = f"pyright-polite: error: pyright returned unexpected JSON ({error})\n"
    await utils.mock_subproc_async(
        capsys,
        subproc_stdout=request.getfixturevalue(subproc_stdout),
        expected_stderr=expected_stderr,
        expected_returncode=2,
    )


async def test_createstub(utils, capsys, stdout_createstub):
    await utils.mock_subproc_async(
        capsys,
        args=("--createstub", "datetime"),
        mode=Mode.PLAINTEXT,
        subproc_stdout=stdout_createstub,
        expected_stdout="Type stub was created for 'datetime'\n",
    )


async def test_dependencies(utils, capsys, stderr_dependencies, stdout_dependencies):
    await utils.mock_subproc_async(
        capsys,
        args=("--dependencies",),
        mode=Mode.UNFILTERED,
        subproc_stderr=stderr_dependencies,
        subproc_stdout=stdout_dependencies,
        expected_stderr="",  # not captured by pyright-polite in unfiltered mode
        expected_stdout="",  # not captured by pyright-polite in unfiltered mode
    )


async def test_dependencies_nonzero_exit(utils, capsys, stderr_dependencies, stdout_dependencies):
    await utils.mock_subproc_async(
        capsys,
        args=("--dependencies",),
        mode=Mode.UNFILTERED,
        subproc_stderr=stderr_dependencies,
        subproc_stdout=stdout_dependencies,
        subproc_returncode=2,
        expected_stderr="",  # not captured by pyright-polite in unfiltered mode
        expected_stdout="",  # not captured by pyright-polite in unfiltered mode
        expected_returncode=2,
    )


async def test_tasks_still_running(utils, capsys):
    async def mock_stream_handler(*args, **kwargs):
        """End the stdout task early, keep the stderr task running."""
        del kwargs
        if args[2] == StreamName.STDOUT:
            raise PyrightJsonError("unexpected EOF")
        await asyncio.sleep(3)

    with patch("pyright_polite.polite.Polite.stream_handler", new=mock_stream_handler):
        await utils.mock_subproc_async(
            capsys,
            subproc_stdout=b"foo}\n",
            expected_stderr="pyright-polite: error: pyright returned unexpected JSON (unexpected EOF)\n",
            expected_returncode=2,
        )


@pytest.mark.skipif("sys.platform == 'win32'", reason="POSIX-only")
@pytest.mark.parametrize(
    ("sig", "returncode"),
    [
        (signal.SIGINT, 130),
        (signal.SIGTERM, 143),
    ],
)
async def test_signals_posix(utils, capsys, sig, returncode):
    await utils.mock_send_signal(
        capsys,
        signal_type=sig,
        expected_returncode=returncode,
    )
