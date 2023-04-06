# SPDX-FileCopyrightText: Copyright © 2023 Jamie Nguyen <j@jamielinux.com>
# SPDX-License-Identifier: MIT
# pyright: strict

"""Main entrypoint."""

import asyncio
import contextlib
import sys

from .cli import CommandLine, parse_cli
from .platform import WINDOWS
from .polite import Polite

__all__ = ["main"]


def main() -> None:
    """Main entrypoint."""
    cli: CommandLine = parse_cli()
    polite: Polite = Polite(cli)

    if WINDOWS:
        # The default event loop implementation for Windows changed in Python 3.8, so
        # explicitly pick the Proactor event loop.
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())  # type: ignore

    with contextlib.suppress(KeyboardInterrupt):
        returncode: int = asyncio.run(polite.run_pyright())
        sys.exit(returncode)


if __name__ == "__main__":
    main()
