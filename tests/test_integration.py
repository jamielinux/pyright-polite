# SPDX-FileCopyrightText: Copyright © 2023 Jamie Nguyen <j@jamielinux.com>
# SPDX-License-Identifier: MIT

import subprocess

import pytest


@pytest.mark.skipif("sys.platform != 'linux'", reason="Linux-only")
def test_integration_pyright(expected_stdout_integration):
    argv = ["pyright-polite", "tests/test_integration"]
    result = subprocess.run(argv, text=True, capture_output=True)
    assert result.stderr == ""
    assert result.stdout == expected_stdout_integration
