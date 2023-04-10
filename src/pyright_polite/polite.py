# SPDX-FileCopyrightText: Copyright © 2023 Jamie Nguyen <j@jamielinux.com>
# SPDX-License-Identifier: MIT
# pyright: strict
# pylint: disable=no-member  # (pylint bug)

"""The Polite class for launching and handling pyright as a subprocess."""

import asyncio
import contextlib
import signal
import sys
from enum import Enum, auto
from types import FrameType
from typing import Dict, List, Optional

from .cli import CommandLine, Mode
from .platform import STATUS_CONTROL_C_EXIT, TERM_SIGNAL, WINDOWS
from .pyright import Pyright, PyrightJsonError, parse_pyright, print_filtered, print_pyright

__all__ = ["Polite"]


class StreamName(Enum):
    """Output stream names."""

    STDERR = auto()
    STDOUT = auto()


class Polite:
    """Launch pyright, handle its output and react to signals."""

    __slots__ = (
        "subproc",
        "_returncode",
        "cli",
        "stdout_lines",
        "lock",
        "signalled",
        "signal_returncodes",
    )

    def __init__(self, cli: CommandLine) -> None:
        """Prepare the instance."""
        self.subproc: asyncio.subprocess.Process
        self._returncode: int = 0

        self.cli: CommandLine = cli
        self.stdout_lines: List[str] = []
        self.lock: asyncio.Lock = asyncio.Lock()
        self.signalled: bool = False

        self.signal_returncodes: Dict[signal.Signals, int]
        if WINDOWS:
            self.signal_returncodes = {
                signal.SIGINT: STATUS_CONTROL_C_EXIT,
                signal.SIGBREAK: STATUS_CONTROL_C_EXIT,  # type: ignore
            }
        else:
            self.signal_returncodes = {
                signal.SIGHUP: 129,  # type: ignore
                signal.SIGINT: 130,
                signal.SIGQUIT: 131,  # type: ignore
                signal.SIGALRM: 142,  # type: ignore
                signal.SIGTERM: 143,
            }

    @property
    def returncode(self) -> int:
        """Getter for the return code."""
        return self._returncode

    @returncode.setter
    def returncode(self, value: Optional[int]) -> None:
        """Setter for the return code."""
        if not isinstance(value, int):
            return

        # When using `asyncio.create_subprocess_exec()`, if the subprocess is killed
        # externally with a signal then the `returncode` property for the asyncio
        # subprocess will be negative. On Linux / Darwin, returncodes must be positive,
        # so we can't just exit using the subprocess returncode without checking.
        if value < 0 and not WINDOWS:
            return

        self._returncode = value

    def unset_signal_handlers(self) -> None:
        """Unset signal handlers back to default.

        For some reason on Windows ctrl-c stops working in powershell sessions unless
        we reset signal handlers back to default (ie, `SIG_DFL`).
        """
        if WINDOWS:
            for sig in self.signal_returncodes:
                signal.signal(sig, signal.SIG_DFL)

    def signal_handler(self, signum: int, _: Optional[FrameType]) -> None:
        """Signal handler to kill the pyright subprocess gracefully.

        Args:
            signum (int): The signal number.
        """
        # Using `loop.add_signal_handler()` isn't possible on Windows. Fortunately,
        # this signal handler doesn't need to do any loop cleanup itself, so we can
        # happily just use a synchronous signal handler.

        self.unset_signal_handlers()
        self.returncode = self.signal_returncodes[signal.Signals(signum)]
        self.signalled = True

        if self.subproc.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                self.subproc.send_signal(TERM_SIGNAL)

    async def kill_subproc(self) -> None:
        """Kill the pyright subprocess with the appropriate signal."""
        if self.subproc.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                self.subproc.send_signal(TERM_SIGNAL)
        await self.subproc.wait()

    async def just_wait_for_pyright(self) -> int:
        """Just wait for pyright to exit, without doing any output filtering.

        Args:
            int: The return code we want to exit with.
        """
        with contextlib.suppress(asyncio.CancelledError):
            await self.subproc.wait()
            self.unset_signal_handlers()
            if isinstance(self.subproc.returncode, int) and self.subproc.returncode > 0:
                return self.subproc.returncode
        return 0

    async def process_bytes(self, line_bytes: bytes, stream_name: StreamName) -> None:
        """Process bytes from an output stream.

        Args:
            line_bytes (bytes): The line retrieved by `readline()`.
            stream_name (StreamName): The name of the stream.
        """
        await asyncio.sleep(0)

        line = line_bytes.decode("utf-8")
        if stream_name == StreamName.STDERR or self.cli.mode == Mode.PLAINTEXT:
            print_filtered(line)
            return

        self.stdout_lines.append(line)
        if line.startswith("}"):
            pyright: Pyright = parse_pyright("".join(self.stdout_lines))
            async with self.lock:
                print_pyright(pyright)
            self.stdout_lines.clear()

    async def stream_handler(self, stream: asyncio.StreamReader, stream_name: StreamName) -> None:
        """Handle stdout and stderr streams.

        Args:
            stream (asyncio.StreamReader): The stream to handle.
            stream_name (StreamName): The name of the stream.
        """
        # At startup, try to print any initial stderr messages first like pyright does.
        # Even with an empty dir, pyright takes >=0.3s to print to stdout anyway.
        if stream_name == StreamName.STDOUT:
            await asyncio.sleep(0.3)

        while not stream.at_eof():
            line_bytes: bytes = await stream.readline()
            if line_bytes:
                # If using pyright from pypi, sending ctrl-c in `--watch` mode will
                # always result in a (completely useless) KeyboardInterrupt traceback.
                if (
                    stream_name == StreamName.STDERR
                    and self.signalled
                    and line_bytes.startswith(b"Traceback (most recent call last):")
                ):
                    return

                await self.process_bytes(line_bytes, stream_name)

        # EOF before a closing "}" means partial JSON output.
        if stream_name == StreamName.STDOUT and self.stdout_lines:
            raise PyrightJsonError("unexpected EOF")

    async def run_pyright(self) -> int:
        """Run pyright and filter and parse its output.

        Returns:
            int: The return code we want to exit with.
        """
        # pyright's `--dependencies` and `--stats` args both include diagnostics in their
        # output, but pyright forbids `--outputjson` with these so we can't parse easily.
        # If we skip parsing and just filter noise from the output, we'd still lose colors.
        # So just avoid capturing stderr/stdout altogether for these args.
        capture: bool = self.cli.mode != Mode.UNFILTERED

        self.subproc = await asyncio.create_subprocess_exec(
            *self.cli.argv,
            stdout=asyncio.subprocess.PIPE if capture else None,
            stderr=asyncio.subprocess.PIPE if capture else None,
        )

        for sig in self.signal_returncodes:
            signal.signal(sig, self.signal_handler)

        if (
            self.cli.mode == Mode.UNFILTERED
            or self.subproc.stdout is None
            or self.subproc.stderr is None
        ):
            self.returncode = await self.just_wait_for_pyright()

        else:
            tasks = [
                asyncio.create_task(self.stream_handler(self.subproc.stderr, StreamName.STDERR)),
                asyncio.create_task(self.stream_handler(self.subproc.stdout, StreamName.STDOUT)),
            ]

            # Possible exit case scenarios:
            #
            # 1. pyright exited normally (usually anything except `--watch` mode).
            # 2. pyright was killed by a signal (usually ctrl-c in `--watch` mode).
            # 3. pyright returned bad JSON.
            # 4. pyright closed stdout and stderr file descriptors, but is still running.
            #        This is unlikely, but possible if there's a bug in pyright.
            # 5. pyright-polite received a signal.

            with contextlib.suppress(asyncio.CancelledError):
                try:
                    # Cases 1 and 2.
                    await asyncio.gather(*tasks)
                    await self.subproc.wait()
                except PyrightJsonError as exc:
                    # Case 3.
                    sys.stderr.write(f"{exc}\n")
                    self.returncode = 2
                finally:
                    # Cases 3, 4 and 5.
                    self.unset_signal_handlers()
                    await self.kill_subproc()
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)

            # We want to return the same exit code that pyright did, except:
            #
            # A. When pyright-polite receives a signal (ie, case 5), in which case we should
            #        use the appropriate exit codes for the signal received.
            # B. When the JSON is bad (ie, case 3), which should never happen really unless
            #        there's a bug in pyright or they changed their JSON schema.
            #
            # In both Case A and Case B, self.returncode would have been set to a
            # non-zero value by the time we get here.

            if self.returncode == 0:
                self.returncode = self.subproc.returncode

        return self.returncode
