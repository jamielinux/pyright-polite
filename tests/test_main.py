# SPDX-FileCopyrightText: Copyright © 2023 Jamie Nguyen <j@jamielinux.com>
# SPDX-License-Identifier: MIT

import pytest


def test_main_entrypoint(event_loop, utils, capsys, stderr, stdout, expected_stdout):
    utils.mock_subproc(
        event_loop,
        capsys,
        subproc_stderr=stderr,
        subproc_stdout=stdout,
        expected_stdout=expected_stdout,
    )


@pytest.mark.parametrize(
    ("subproc_returncode", "expected_returncode"),
    [
        (1, 1),
        (None, 0),
    ],
)
def test_main_entrypoint_returncodes(
    event_loop,
    utils,
    capsys,
    stderr,
    stdout,
    expected_stdout,
    subproc_returncode,
    expected_returncode,
):
    utils.mock_subproc(
        event_loop,
        capsys,
        subproc_stderr=stderr,
        subproc_stdout=stdout,
        subproc_returncode=subproc_returncode,
        expected_stdout=expected_stdout,
        expected_returncode=expected_returncode,
    )


@pytest.mark.skipif("sys.platform == 'win32'", reason="POSIX-only")
def test_main_entrypoint_negative_returncode(
    event_loop, utils, capsys, stderr, stdout, expected_stdout
):
    utils.mock_subproc(
        event_loop,
        capsys,
        subproc_stderr=stderr,
        subproc_stdout=stdout,
        subproc_returncode=-1,
        expected_stdout=expected_stdout,
        expected_returncode=0,
    )
