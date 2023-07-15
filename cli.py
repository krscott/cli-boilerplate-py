import argparse
from dataclasses import dataclass
import json
import logging
import os
import sys
from typing import Any
from tqdm.auto import tqdm

_name_to_level = {
    'CRITICAL': logging.CRITICAL,
    'FATAL': logging.FATAL,
    'ERROR': logging.ERROR,
    'WARN': logging.WARNING,
    'WARNING': logging.WARNING,
    'INFO': logging.INFO,
    'DEBUG': logging.DEBUG,
    'NOTSET': logging.NOTSET,
}

def eprint(*a: object):
    print(*a, file=sys.stderr)


def str_to_filename(s: str):
    def valid_char(c: str):
        if c.isalnum() or c in ("-", "."):
            return c
        return "_"

    return "".join(valid_char(c) for c in s)


class TqdmWrapperLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord):
        tqdm.write(self.format(record), file=sys.stderr)


def arg_env(
    name: str,
    *,
    help: str,
    default: Any = None,
    optional: bool = False,
    set_default: bool = True,
):
    """
    Helper function for using environment variable as default argparse argument
    value. Creates a keyword arg dict for `ArgumentParser.add_argument()`.

    `name`: Environment variable name

    `help`: The help string. Info about the environment default will be appended.

    `default`: Default value if argument is not specified by user

    `optional`: Allow option to be unspecified. Otherwise, argument is required
    to either be specified as CLI option, from environment, or as `default` param.

    `set_default`: Set `False` to disable default-setting logic, but still put
    environment variable name in the help string.

    ## Example
    ```
    parser.argparse.ArgumentParser()
    parser.add_argument(
        "-o",
        "--output",
        **arg_env("OUT_FILE", help="Output filename")
    )
    ```
    """

    out: dict[str, Any] = {"help": f"{help} [env:{name}]"}

    if set_default:
        if name in os.environ:
            out["default"] = os.environ[name]
        elif default is not None:
            out["default"] = default
        elif not optional:
            out["required"] = True

    return out


def json_load_env(name: str):
    """
    Load JSON data from an environment variable.
    On parse error, print helpful error message and exit.
    """
    value = os.environ[name]
    try:
        return json.loads(value)
    except json.JSONDecodeError as e:
        lines = value.split("\n")
        lines.insert(e.lineno, " " * (e.colno - 1) + "^ Error: " + e.msg)
        err_help = "\n".join(lines)
        eprint(f"Error parsing JSON environment variable '{name}':\n{err_help}")
        sys.exit(3)


def add_log_arguments(parser: argparse.ArgumentParser):
    default_console_level = "INFO"
    default_console_format = "%(levelname)s %(message)s"
    default_log_filename = f"log_{str_to_filename(parser.prog.removesuffix('.py'))}.log"
    default_log_file_level = "DEBUG"
    default_log_file_format = (
        "%(asctime)s %(levelname)s %(filename)s:%(lineno)d %(message)s"
    )

    log_levels = list(_name_to_level.keys())

    _ = parser.add_argument(
        "-v", "--verbose", action="count", default=0, help="Increase log verbosity"
    )
    _ = parser.add_argument(
        "-q", "--quiet", action="store_true", help="suppress stderr log messages"
    )
    _ = parser.add_argument(
        "--log-level",
        choices=log_levels,
        **arg_env("LOG_LEVEL", default=default_console_level, help="Base log level"),
    )
    _ = parser.add_argument(
        "--log-format",
        **arg_env("LOG_FORMAT", default=default_console_format, help="Log filename"),
    )
    _ = parser.add_argument(
        "--log-file",
        **arg_env("LOG_FILE", default=default_log_filename, help="Log filename"),
    )
    _ = parser.add_argument(
        "--log-file-level",
        choices=log_levels,
        **arg_env(
            "LOG_FILE_LEVEL", default=default_log_file_level, help="Log filename"
        ),
    )
    _ = parser.add_argument(
        "--log-file-format",
        **arg_env(
            "LOG_FILE_FORMAT", default=default_log_file_format, help="Log filename"
        ),
    )


@dataclass(kw_only=True)
class CliStderrOpts:
    verbosity: int
    quiet: bool


def init_log(log: logging.Logger, args: argparse.Namespace) -> CliStderrOpts:
    """
    Initialize log based on options specified in `add_log_arguments()`.
    Compatible with `tqdm`.
    """

    stderr_opts = CliStderrOpts(verbosity=args.verbose, quiet=args.quiet)

    if log.hasHandlers():
        log.handlers.clear()

    # Root logger, upstream of console and file loggers
    log.setLevel(logging.DEBUG)

    # File logger
    if log_filename := args.log_file:
        level = _name_to_level.get(args.log_file_level)
        log_file_handler = logging.FileHandler(log_filename)
        log_file_handler.setLevel(_name_to_level[args.log_file_level])
        log_file_handler.setFormatter(logging.Formatter(args.log_file_format))
        log.addHandler(log_file_handler)

    # Console logger
    tqdm_handler = TqdmWrapperLogHandler()

    if stderr_opts.quiet:
        # Set level that will never be printed
        level = logging.CRITICAL + 10
    else:
        # Decrease log level (toward DEBUG) one step for each verbosity level
        level = _name_to_level[args.log_level] - stderr_opts.verbosity * 10
    tqdm_handler.setLevel(level)
    tqdm_handler.setFormatter(logging.Formatter(args.log_format))
    log.addHandler(tqdm_handler)

    return stderr_opts