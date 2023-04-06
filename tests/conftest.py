# SPDX-FileCopyrightText: Copyright © 2023 Jamie Nguyen <j@jamielinux.com>
# SPDX-License-Identifier: MIT

import asyncio
import inspect
import os
from unittest.mock import patch

import pytest
from colorama import Fore
from pyright_polite.cli import CommandLine, Mode
from pyright_polite.main import main
from pyright_polite.polite import Polite


class MockCreateSubprocessExec:
    def __init__(self, returncode, stderr, stdout):
        self._returncode = returncode
        self.stderr = asyncio.StreamReader()
        self.stdout = asyncio.StreamReader()
        self.stderr.feed_data(stderr)
        self.stdout.feed_data(stdout)
        self.stderr.feed_eof()
        self.stdout.feed_eof()

    @property
    def returncode(self):
        return self._returncode

    def send_signal(self, _):
        pass

    async def wait(self):
        await asyncio.sleep(2)
        return self._returncode


class MockContextlibSuppress:
    """Mocked version of contextlib.suppress().

    Instead of suppressing all exceptions passed as arguments, it suppresses everything
    except the exceptions passed as arguments. This is useful if we want test whether
    an exception is raised properly, despite suppressing it in the application.
    """

    def __init__(self, *exceptions):
        self._exceptions = exceptions

    def __enter__(self):
        pass

    def __exit__(self, exctype, excinst, exctb):
        del excinst, exctb
        return exctype is None or not issubclass(exctype, self._exceptions)


@pytest.fixture()
def mock_contextlib_suppress():
    return MockContextlibSuppress


class Utils:
    @staticmethod
    async def loop_cleanup():
        loop = asyncio.get_running_loop()
        tasks = [t for t in asyncio.all_tasks(loop) if t is not asyncio.current_task(loop)]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    @staticmethod
    def mock_subproc(
        event_loop,
        capsys,
        args=("--outputjson",),
        subproc_stderr=b"",
        subproc_stdout=b"",
        subproc_returncode=0,
        expected_stderr="",
        expected_stdout="",
        expected_returncode=0,
    ):
        """Run with a mocked asyncio.create_subprocess_exec()."""

        async def create_mock_subprocess_exec(*args, **kwargs):
            del args, kwargs
            return MockCreateSubprocessExec(subproc_returncode, subproc_stderr, subproc_stdout)

        patcher_argv = patch("sys.argv", ["pyright-polite", *args])
        patcher_argv.start()
        patcher_exec = patch("asyncio.create_subprocess_exec", new=create_mock_subprocess_exec)
        patcher_exec.start()

        try:
            with pytest.raises(SystemExit) as pytest_e:
                main()
            assert pytest_e.type == SystemExit
            assert pytest_e.value.code == expected_returncode
            captured = capsys.readouterr()
            assert captured.err == expected_stderr
            assert captured.out == expected_stdout
        finally:
            patcher_argv.stop()
            patcher_exec.stop()
            event_loop.close()

    @staticmethod
    async def mock_subproc_async(
        capsys,
        args=("--outputjson",),
        mode=Mode.JSON,
        subproc_stderr=b"",
        subproc_stdout=b"",
        subproc_returncode=0,
        expected_stderr="",
        expected_stdout="",
        expected_returncode=0,
        expected_exception=None,
    ):
        """Run async with a mocked asyncio.create_subprocess_exec()."""

        async def create_mock_subprocess_exec(*args, **kwargs):
            del args, kwargs
            return MockCreateSubprocessExec(subproc_returncode, subproc_stderr, subproc_stdout)

        argv = ["nonexistent", *args]
        cli = CommandLine(argv=argv, mode=mode)
        polite = Polite(cli)
        with patch("asyncio.create_subprocess_exec", new=create_mock_subprocess_exec):
            try:
                if expected_exception:
                    with pytest.raises(expected_exception):
                        await polite.run_pyright()
                else:
                    assert await polite.run_pyright() == expected_returncode
            finally:
                await Utils.loop_cleanup()

        captured = capsys.readouterr()
        assert captured.err == expected_stderr
        assert captured.out == expected_stdout

    @staticmethod
    async def mock_send_signal(
        capsys,
        signal_type,
        args=("--outputjson",),
        subproc_returncode=0,
        expected_returncode=0,
    ):
        """Send a signal to pyright-polite."""

        async def create_mock_subprocess_exec(*args, **kwargs):
            del args, kwargs
            return MockCreateSubprocessExec(subproc_returncode, b"", b"")

        async def sigint():
            await asyncio.sleep(0.2)
            pid = os.getpid()
            os.kill(pid, signal_type)

        argv = ["nonexistent", *args]
        cli = CommandLine(argv=argv, mode=Mode.JSON)
        polite = Polite(cli)

        patch_exec = patch("asyncio.create_subprocess_exec", new=create_mock_subprocess_exec)
        patch_exec.start()

        try:
            tasks = [
                asyncio.create_task(sigint()),
                asyncio.create_task(polite.run_pyright()),
            ]

            results = (None, None)
            results = await asyncio.gather(*tasks)
        finally:
            patch_exec.stop()
            await Utils.loop_cleanup()

        assert results[1] == expected_returncode
        captured = capsys.readouterr()
        assert captured.err == ""
        assert captured.out == ""


@pytest.fixture()
def utils():
    return Utils


@pytest.fixture(autouse=True)
def mock_find_pyright(request):
    if "disable_autouse" in request.keywords:
        yield
    else:
        with patch("pyright_polite.cli.find_pyright", return_value="pyright") as mock:
            yield mock


@pytest.fixture()
def stderr():
    string = inspect.cleandoc(
        """
        No configuration file found.
        pyproject.toml file found at /tmp/testproject/pyright_polite.
        Loading pyproject.toml file at /tmp/testproject/pyright_polite/pyproject.toml
        Assuming Python version 3.11
        Assuming Python platform Linux
        Auto-excluding **/node_modules
        Auto-excluding **/__pycache__
        Auto-excluding **/.*
        stubPath /tmp/testproject/pyright_polite/typings is not a valid directory.
        Searching for source files
        Found 7 source files
        pyright 1.1.300
        Completed in 0.925sec
        """
    )
    return string.encode("utf-8")


@pytest.fixture()
def stderr_with_extra_message(stderr):
    string = "pyright-polite should not filter this line.\n"
    return string.encode("utf-8") + stderr


@pytest.fixture()
def stdout():
    string = inspect.cleandoc(
        """
        {
            "version": "1.1.300",
            "time": "1679589553221",
            "generalDiagnostics": [
                {
                    "file": "/tmp/testproject/src/testproject/testproject.py",
                    "severity": "error",
                    "message": "Import \\"foo\\" could not be resolved",
                    "range": {
                        "start": {
                            "line": 24,
                            "character": 5
                        },
                        "end": {
                            "line": 24,
                            "character": 16
                        }
                    },
                    "rule": "reportMissingImports"
                },
                {
                    "file": "/tmp/testproject/src/testproject/testproject.py",
                    "severity": "warning",
                    "message": "Wildcard import from a library not allowed",
                    "range": {
                        "start": {
                            "line": 21,
                            "character": 21
                        },
                        "end": {
                            "line": 21,
                            "character": 22
                        }
                    },
                    "rule": "reportWildcardImportFromLibrary"
                },
                {
                    "file": "/tmp/testproject/src/testproject/testproject.py",
                    "severity": "error",
                    "message": "Cannot access member \\"strptime\\" for type \\"Type[time]\\"\\n  Member \\"strptime\\" is unknown",
                    "range": {
                        "start": {
                            "line": 163,
                            "character": 45
                        },
                        "end": {
                            "line": 163,
                            "character": 53
                        }
                    },
                    "rule": "reportGeneralTypeIssues"
                },
                {
                    "file": "/tmp/testproject/src/testproject/testproject.py",
                    "severity": "error",
                    "message": "Cannot access member \\"struct_time\\" for type \\"Type[time]\\"\\n  Member \\"struct_time\\" is unknown",
                    "range": {
                        "start": {
                            "line": 163,
                            "character": 26
                        },
                        "end": {
                            "line": 163,
                            "character": 37
                        }
                    },
                    "rule": "reportGeneralTypeIssues"
                },
                {
                    "file": "/tmp/testproject/tests/test_testproject_to_unixtime.py",
                    "severity": "error",
                    "message": "Import \\"testproject\\" could not be resolved",
                    "range": {
                        "start": {
                            "line": 3,
                            "character": 5
                        },
                        "end": {
                            "line": 3,
                            "character": 13
                        }
                    },
                    "rule": "reportMissingImports"
                },
                {
                    "file": "/tmp/testproject/tests/test_is_valid_testproject.py",
                    "severity": "error",
                    "message": "Import \\"testproject\\" could not be resolved",
                    "range": {
                        "start": {
                            "line": 1,
                            "character": 5
                        },
                        "end": {
                            "line": 1,
                            "character": 13
                        }
                    },
                    "rule": "reportMissingImports"
                },
                {
                    "file": "/tmp/testproject/tests/test_unixtime_to_testproject.py",
                    "severity": "error",
                    "message": "Import \\"testproject\\" could not be resolved",
                    "range": {
                        "start": {
                            "line": 1,
                            "character": 5
                        },
                        "end": {
                            "line": 1,
                            "character": 13
                        }
                    }
                }
            ],
            "summary": {
                "filesAnalyzed": 5,
                "errorCount": 6,
                "warningCount": 1,
                "informationCount": 0,
                "timeInSec": 0.439
            }
        }
        """,
    )
    return string.encode("utf-8")


@pytest.fixture()
def expected_stdout():
    return (
        inspect.cleandoc(
            f"""
            Found 5 source files
            /tmp/testproject/src/testproject/testproject.py
              /tmp/testproject/src/testproject/testproject.py:{Fore.YELLOW}25{Fore.RESET}:{Fore.YELLOW}6{Fore.RESET} - {Fore.RED}error{Fore.RESET}: Import "foo" could not be resolved {Fore.LIGHTBLACK_EX}(reportMissingImports){Fore.RESET}
              /tmp/testproject/src/testproject/testproject.py:{Fore.YELLOW}22{Fore.RESET}:{Fore.YELLOW}22{Fore.RESET} - {Fore.CYAN}warning{Fore.RESET}: Wildcard import from a library not allowed {Fore.LIGHTBLACK_EX}(reportWildcardImportFromLibrary){Fore.RESET}
              /tmp/testproject/src/testproject/testproject.py:{Fore.YELLOW}164{Fore.RESET}:{Fore.YELLOW}46{Fore.RESET} - {Fore.RED}error{Fore.RESET}: Cannot access member "strptime" for type "Type[time]"
                Member "strptime" is unknown {Fore.LIGHTBLACK_EX}(reportGeneralTypeIssues){Fore.RESET}
              /tmp/testproject/src/testproject/testproject.py:{Fore.YELLOW}164{Fore.RESET}:{Fore.YELLOW}27{Fore.RESET} - {Fore.RED}error{Fore.RESET}: Cannot access member "struct_time" for type "Type[time]"
                Member "struct_time" is unknown {Fore.LIGHTBLACK_EX}(reportGeneralTypeIssues){Fore.RESET}
            /tmp/testproject/tests/test_testproject_to_unixtime.py
              /tmp/testproject/tests/test_testproject_to_unixtime.py:{Fore.YELLOW}4{Fore.RESET}:{Fore.YELLOW}6{Fore.RESET} - {Fore.RED}error{Fore.RESET}: Import "testproject" could not be resolved {Fore.LIGHTBLACK_EX}(reportMissingImports){Fore.RESET}
            /tmp/testproject/tests/test_is_valid_testproject.py
              /tmp/testproject/tests/test_is_valid_testproject.py:{Fore.YELLOW}2{Fore.RESET}:{Fore.YELLOW}6{Fore.RESET} - {Fore.RED}error{Fore.RESET}: Import "testproject" could not be resolved {Fore.LIGHTBLACK_EX}(reportMissingImports){Fore.RESET}
            /tmp/testproject/tests/test_unixtime_to_testproject.py
              /tmp/testproject/tests/test_unixtime_to_testproject.py:{Fore.YELLOW}2{Fore.RESET}:{Fore.YELLOW}6{Fore.RESET} - {Fore.RED}error{Fore.RESET}: Import "testproject" could not be resolved
            6 errors, 1 warnings, 0 informations
            """,
        )
        + "\n"
    )


@pytest.fixture()
def stdout_createstub():
    string = inspect.cleandoc(
        """
        No configuration file found.
        pyproject.toml file found at /tmp/testproject/pyright_polite.
        Loading pyproject.toml file at /tmp/testproject/pyright_polite/pyproject.toml
        Assuming Python version 3.11
        Assuming Python platform Linux
        Auto-excluding **/node_modules
        Auto-excluding **/__pycache__
        Auto-excluding **/.*
        stubPath /tmp/testproject/pyright_polite/typings is not a valid directory.
        Type stub was created for 'datetime'
        """
    )
    return string.encode("utf-8")


@pytest.fixture()
def stderr_dependencies():
    string = inspect.cleandoc(
        """
        Pyproject file "/tmp/testproject/pyproject.toml" is missing "[tool.pyright]" section.
        stubPath /tmp/testproject/typings is not a valid directory.
        """
    )
    return string.encode("utf-8")


@pytest.fixture()
def stdout_dependencies():
    string = inspect.cleandoc(
        f"""
        No configuration file found.
        pyproject.toml file found at /tmp/testproject.
        Loading pyproject.toml file at /tmp/testproject/pyproject.toml
        Assuming Python platform Linux
        Searching for source files
        Found 3 source files
        pyright 1.1.300
        /tmp/testproject/testproject/__init__.py
          /tmp/testproject/testproject/__init__.py:{Fore.YELLOW}5{Fore.RESET}:{Fore.YELLOW}10{Fore.RESET} - {Fore.RED}error{Fore.RESET}: Expression of type "Literal[1]" cannot be assigned to declared type "str"
            "Literal[1]" is incompatible with "str" {Fore.LIGHTBLACK_EX}(reportGeneralTypeIssues){Fore.RESET}
        1 error, 0 warnings, 0 informations
        Completed in 0.459sec

        ./tests/__init__.py
         Imports     1 file
         Imported by 0 files

        ./testproject/__init__.py
         Imports     1 file
         Imported by 0 files

        ./testproject/__about__.py
         Imports     1 file
         Imported by 0 files

        3 files not explicitly imported
            /tmp/testproject/tests/__init__.py
            /tmp/testproject/testproject/__init__.py
            /tmp/testproject/testproject/__about__.py
        """
    )
    return string.encode("utf-8")


@pytest.fixture()
def stdout_no_files():
    string = inspect.cleandoc(
        """
            {
                "version": "1.1.300",
                "time": "1679589553221",
                "generalDiagnostics": [],
                "summary": {
                    "filesAnalyzed": 0,
                    "errorCount": 0,
                    "warningCount": 0,
                    "informationCount": 0,
                    "timeInSec": 0.439
                }
            }
        """
    )
    return string.encode("utf-8")


@pytest.fixture()
def stdout_no_json():
    return b"foo\n"


@pytest.fixture()
def stdout_invalid_json():
    return b"{\nfoo bar baz\n}\n"


@pytest.fixture()
def stdout_no_summary():
    string = inspect.cleandoc(
        """
            {
                "version": "1.1.300",
                "time": "1679589553221",
                "generalDiagnostics": []
            }
        """
    )
    return string.encode("utf-8")


@pytest.fixture()
def stdout_summary_wrong_type():
    string = inspect.cleandoc(
        """
            {
                "version": "1.1.300",
                "time": "1679589553221",
                "generalDiagnostics": [],
                "summary": "foo"
            }
        """
    )
    return string.encode("utf-8")


@pytest.fixture()
def stdout_summary_no_analyzed():
    string = inspect.cleandoc(
        """
            {
                "version": "1.1.300",
                "time": "1679589553221",
                "generalDiagnostics": [],
                "summary": {
                    "errorCount": 0,
                    "warningCount": 0,
                    "informationCount": 0,
                    "timeInSec": 0.439
                }
            }
        """,
    )
    return string.encode("utf-8")


@pytest.fixture()
def stdout_summary_analyzed_wrong_type():
    string = inspect.cleandoc(
        """
            {
                "version": "1.1.300",
                "time": "1679589553221",
                "generalDiagnostics": [],
                "summary": {
                    "filesAnalyzed": "0",
                    "errorCount": 0,
                    "warningCount": 0,
                    "informationCount": 0,
                    "timeInSec": 0.439
                }
            }
        """,
    )
    return string.encode("utf-8")


@pytest.fixture()
def stdout_no_diagnostics():
    string = inspect.cleandoc(
        """
            {
                "version": "1.1.300",
                "time": "1679589553221",
                "summary": {
                    "filesAnalyzed": 5,
                    "errorCount": 0,
                    "warningCount": 0,
                    "informationCount": 0,
                    "timeInSec": 0.439
                }
            }
        """,
    )
    return string.encode("utf-8")


@pytest.fixture()
def stdout_diagnostics_wrong_type():
    string = inspect.cleandoc(
        """
            {
                "version": "1.1.300",
                "time": "1679589553221",
                "generalDiagnostics": "foo",
                "summary": {
                    "filesAnalyzed": 5,
                    "errorCount": 0,
                    "warningCount": 0,
                    "informationCount": 0,
                    "timeInSec": 0.439
                }
            }
        """,
    )
    return string.encode("utf-8")


@pytest.fixture()
def stdout_diagnostic_wrong_type():
    string = inspect.cleandoc(
        """
            {
                "version": "1.1.300",
                "time": "1679589553221",
                "generalDiagnostics": ["blah"],
                "summary": {
                    "filesAnalyzed": 5,
                    "errorCount": 0,
                    "warningCount": 0,
                    "informationCount": 0,
                    "timeInSec": 0.439
                }
            }
        """,
    )
    return string.encode("utf-8")


@pytest.fixture()
def stdout_diagnostic_no_range():
    string = inspect.cleandoc(
        """
            {
                "version": "1.1.300",
                "time": "1679589553221",
                "generalDiagnostics": [
                    {
                        "file": "/tmp/testproject/src/testproject/testproject.py",
                        "severity": "error",
                        "message": "Import \\"foo\\" could not be resolved",
                        "rule": "reportMissingImports"
                    }
                ],
                "summary": {
                    "filesAnalyzed": 5,
                    "errorCount": 0,
                    "warningCount": 0,
                    "informationCount": 0,
                    "timeInSec": 0.439
                }
            }
        """,
    )
    return string.encode("utf-8")


@pytest.fixture()
def stdout_diagnostic_invalid_severity():
    string = inspect.cleandoc(
        """
            {
                "version": "1.1.300",
                "time": "1679589553221",
                "generalDiagnostics": [
                    {
                        "file": "/tmp/testproject/src/testproject/testproject.py",
                        "severity": "foo",
                        "message": "Import \\"foo\\" could not be resolved",
                        "range": {
                            "start": {
                                "line": 24,
                                "character": 5
                            },
                            "end": {
                                "line": 24,
                                "character": 16
                            }
                        },
                        "rule": "reportMissingImports"
                    }
                ],
                "summary": {
                    "filesAnalyzed": 5,
                    "errorCount": 0,
                    "warningCount": 0,
                    "informationCount": 0,
                    "timeInSec": 0.439
                }
            }
        """,
    )
    return string.encode("utf-8")
