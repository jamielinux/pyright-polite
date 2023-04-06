# SPDX-FileCopyrightText: Copyright © 2023 Jamie Nguyen <j@jamielinux.com>
# SPDX-License-Identifier: MIT

import asyncio
import os
import signal
from unittest.mock import patch

import pytest
from pyright_polite.cli import CommandLine, Mode
from pyright_polite.polite import Polite


class MockCreateSubprocessExecRaiseProcessLookupError:
    def __init__(self):
        self._returncode = None
        self.stderr = asyncio.StreamReader()
        self.stdout = asyncio.StreamReader()
        self.stderr.feed_eof()
        self.stdout.feed_eof()

    @property
    def returncode(self):
        return self._returncode

    def send_signal(self, _):
        raise ProcessLookupError

    async def wait(self):
        await asyncio.sleep(2)
        return self._returncode


@pytest.mark.skipif("sys.platform == 'win32'", reason="POSIX-only")
async def test_processlookuperror(utils, mock_contextlib_suppress, capsys):
    async def create_mock_subprocess_exec(*args, **kwargs):
        del args, kwargs
        return MockCreateSubprocessExecRaiseProcessLookupError()

    async def sigint():
        await asyncio.sleep(0.2)
        pid = os.getpid()
        os.kill(pid, signal.SIGINT)

    argv = ["nonexistent", "--outputjson"]
    cli = CommandLine(argv=argv, mode=Mode.JSON)
    polite = Polite(cli)

    patch_exec = patch("asyncio.create_subprocess_exec", new=create_mock_subprocess_exec)
    patch_exec.start()

    patch_contextlib = patch("contextlib.suppress", new=mock_contextlib_suppress)
    patch_contextlib.start()

    try:
        tasks = [
            asyncio.create_task(sigint()),
            asyncio.create_task(polite.run_pyright()),
        ]

        results = (None, None)
        with pytest.raises(ProcessLookupError):
            results = await asyncio.gather(*tasks)
    finally:
        patch_contextlib.stop()
        patch_exec.stop()
        await utils.loop_cleanup()

    assert results[1] is None
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out == ""
