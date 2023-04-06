# SPDX-FileCopyrightText: Copyright © 2023 Jamie Nguyen <j@jamielinux.com>
# SPDX-License-Identifier: MIT

from unittest.mock import patch

import pytest
from pyright_polite.cli import Mode, parse_cli


def test_help(capsys):
    with patch("sys.argv", ["pyright-polite", "--help"]):
        with pytest.raises(SystemExit) as pytest_e:
            parse_cli()
        assert pytest_e.type == SystemExit
        assert pytest_e.value.code == 0
        captured = capsys.readouterr()
        assert captured.err == ""
        assert captured.out.startswith("Usage: pyright-polite [options] files...")


def test_no_args():
    with patch("sys.argv", ["pyright-polite"]):
        result = parse_cli()
        assert result.argv[1:] == ["--outputjson"]
        assert result.mode == Mode.JSON


@pytest.mark.parametrize(
    ("args", "mode"),
    [
        (["--version"], Mode.UNFILTERED),
        (["--createstub", "datetime"], Mode.PLAINTEXT),
        (["--dependencies"], Mode.UNFILTERED),
        (["--ignoreexternal", "--verifytypes", "foo"], Mode.PLAINTEXT),
        (["--stats"], Mode.UNFILTERED),
    ],
)
def test_not_json(args, mode):
    with patch("sys.argv", ["pyright-polite", *args]):
        result = parse_cli()
        assert result.argv[1:] == args
        assert result.mode == mode


@pytest.mark.parametrize(
    ("args"),
    [
        (["--lib"]),
        (["--level", "error"]),
        (["--project", "project"]),
        (["--pythonplatform", "Linux"]),
        (["--pythonversion", "3.11"]),
        (["--skipunannotated"]),
        (["--typeshed-path", "typeshed-path"]),
        (["--venv-path", "venv-path"]),
        (["--warnings"]),
        (["--verbose"]),
        (["--watch"]),
    ],
)
def test_json(args):
    with patch("sys.argv", ["pyright-polite", *args]):
        result = parse_cli()
        assert result.argv[1:] == [*args, "--outputjson"]
        assert result.mode == Mode.JSON


def test_files():
    with patch("sys.argv", ["pyright-polite", "foo.py", "bar.py"]):
        result = parse_cli()
        assert result.argv[1:] == ["--outputjson", "foo.py", "bar.py"]
        assert result.mode == Mode.JSON


def test_bad_arg():
    with patch("sys.argv", ["pyright-polite", "--bad-arg"]):
        with pytest.raises(SystemExit) as pytest_e:
            parse_cli()

        assert pytest_e.type == SystemExit
        assert pytest_e.value.code == 4


@pytest.mark.disable_autouse()
def test_pyright_found():
    patcher_shutil = patch("shutil.which", return_value="pyright")
    patcher_shutil.start()

    patcher_access = patch("os.access", return_value=True)
    patcher_access.start()

    with patch("sys.argv", ["pyright-polite"]):
        parse_cli()

    patcher_access.stop()
    patcher_shutil.stop()


@pytest.mark.disable_autouse()
@pytest.mark.parametrize(
    "expected_returncode",
    [
        pytest.param(
            127,
            marks=pytest.mark.skipif("sys.platform == 'win32'", reason="POSIX-only"),
        ),
        pytest.param(
            9009,
            marks=pytest.mark.skipif("sys.platform != 'win32'", reason="Windows-only"),
        ),
    ],
)
def test_pyright_not_found(expected_returncode):
    patcher_shutil = patch("shutil.which", return_value=None)
    patcher_shutil.start()

    with patch("sys.argv", ["pyright-polite"]):
        with pytest.raises(SystemExit) as pytest_e:
            parse_cli()
        assert pytest_e.type == SystemExit
        assert pytest_e.value.code == expected_returncode

    patcher_shutil.stop()


@pytest.mark.disable_autouse()
@pytest.mark.skipif("sys.platform == 'win32'", reason="POSIX-only")
def test_pyright_not_executable():
    patcher_shutil = patch("shutil.which", return_value="pyright")
    patcher_shutil.start()

    patcher_access = patch("os.access", return_value=False)
    patcher_access.start()

    with patch("sys.argv", ["pyright-polite"]):
        with pytest.raises(SystemExit) as pytest_e:
            parse_cli()
        assert pytest_e.type == SystemExit
        assert pytest_e.value.code == 126

    patcher_access.stop()
    patcher_shutil.stop()
