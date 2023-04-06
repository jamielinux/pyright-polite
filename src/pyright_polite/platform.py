# SPDX-FileCopyrightText: Copyright © 2023 Jamie Nguyen <j@jamielinux.com>
# SPDX-License-Identifier: MIT
# pyright: strict
# pylint: disable=no-member

"""Platform-specific global variables."""

import platform
import signal

__all__ = ["LINUX", "DARWIN", "WINDOWS", "STATUS_CONTROL_C_EXIT", "TERM_SIGNAL"]

# `platform.system()` has the most thorough heuristics for determining the OS. It tries
# `os.uname()`, `sys.platform` and OS-specific calls in that order (stopping when it gets
# an answer), and then normalizes into categories that include Linux, Darwin, Windows.
PLATFORM: str = platform.system()
LINUX: bool = PLATFORM == "Linux"
DARWIN: bool = PLATFORM == "Darwin"
WINDOWS: bool = PLATFORM == "Windows"

# On Windows, pyright returns -1073741510 exit code when it receives CTRL_C_EVENT or
# CTRL_BREAK_EVENT. This number is the signed int representation of 0xC000013A, which is
# the general Windows error code indicating that a program was terminated with Ctrl-C.
STATUS_CONTROL_C_EXIT: int = -1073741510

# Send this signal to pyright when we want it to exit. Some people install pypi-pyright,
# which runs npm-pyright as a subprocess; importantly, for that scenario we must send a
# SIGINT (Linux/Darwin) or CTRL_C_EVENT (Windows) to pypi-pyright, instead of SIGTERM
# or anything else, otherwise it will leave npm-pyright running. The same signals are
# also appropriate when working directly with npm-pyright.
TERM_SIGNAL: signal.Signals = signal.CTRL_C_EVENT if WINDOWS else signal.SIGINT  # type: ignore
