import argparse
import logging
import cli

log = logging.getLogger("my_log")

parser = argparse.ArgumentParser()
cli.add_log_arguments(parser)
args = parser.parse_args()
print(args)
stderr_opts = cli.init_log(log, args)
print(stderr_opts)
