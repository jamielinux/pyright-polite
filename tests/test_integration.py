# SPDX-FileCopyrightText: Copyright © 2023 Jamie Nguyen <j@jamielinux.com>
# SPDX-License-Identifier: MIT

import os
import subprocess
import sys

import pytest

IN_GITHUB_ACTIONS = os.getenv("GITHUB_ACTIONS") == "true"


@pytest.mark.skipif(sys.platform != "linux", reason="Linux-only")
@pytest.mark.skipif(not IN_GITHUB_ACTIONS, reason="GitHub-only")
def test_integration_pyright(expected_stdout_integration):
    argv = ["pyright-polite", "tests/test_integration"]
    result = subprocess.run(argv, text=True, capture_output=True)
    assert result.stderr == ""
    assert result.stdout == expected_stdout_integration
