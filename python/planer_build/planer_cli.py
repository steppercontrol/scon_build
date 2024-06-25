#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK

import argparse
import os
import sys

import argcomplete
# import mk_build.configure
from mk_build.config import Config
from mk_build import Path

from mk_build import log, run, wsl

import planer_build.configure as configure_


class CLI:
    config: configure_.ConfigH

    def __init__(self):
        self.config = configure_.ConfigH.from_file('config.toml.default')

    def monitor(self, args):
        board = self.config.board
        port = self.config.port

        run([
            'arduino-cli', 'monitor',
            '-q',
            '-b', board,
            '-p', port,
            '-v'
        ])

    def upload(self, args):
        # arduino-cli upload $sketch -b $BOARD -p $port -v && \
        # arduino-cli upload --input-file $sketch -b $BOARD -p $port -v && \
        # arduino-cli monitor -q --raw -b $BOARD -p $port -c baudrate=115200

        board = self.config.board
        port = self.config.port

        run([
            'arduino-cli', 'upload',
            '--input-file', args.filename,
            '-b', board,
            '-p', port,
            '-v'
        ])


_cli = CLI()


def build(args):
    run(['gup', '-j', '4'])


def init_ide(args):
    # assume Arduino IDE is installed in

    # C:\Users\ChillRuns\AppData\Local\Programs\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe

    # LOCALAPPDATA                   C:\Users\ChillRuns\AppData\Local
    # C:\Users\ChillRuns\AppData\Local\Programs\Arduino IDE\Arduino IDE.exe
    # C:\Users\ChillRuns\.arduinoIDE\arduino-cli.yaml
    # USERPROFILE                    C:\Users\ChillRuns

    # detect installation
    # modify settings.json
    # modify arduino-cli.yaml (sketchbook)
    # modify platform settings for builds
    # install board
    pass


def configure(args):
    source = os.getcwd() if args.source is None else args.source
    build = f'{source}/_build' if args.build is None else str(Path(args.build).absolute())

    os.environ['top_source_dir'] = source
    os.environ['top_build_dir'] = build

    log.info(f'Auto-detected source directory: {source}')
    log.info(f'Auto-detected build directory: {build}')

    cfg = configure_.ConfigH.from_file('config.toml.default')
    log.debug(f'config {cfg}')

    path = f'{build}/config.toml'

    with open(path, 'w') as fi:
        fi.write(cfg.toml)

    config_file = Config()

    log.debug(f'configuration: {config_file}')
    log.debug(f'write configuration: {path}')

    config_file.write(path, 'a')

    # mk_build.configure.main()


class Parser:
    def __init__(self):
        self.parser = argparse.ArgumentParser(
            prog='ProgramName',
            description='What the program does',
            epilog='Text at the bottom of help')

        self.subparsers = self.parser.add_subparsers(required=True)

        self._init_configure()
        self._init_init_ide()
        self._init_build()
        self._init_upload()

        self.parser.add_argument('-l', '--log-level', type=int)

        argcomplete.autocomplete(self.parser)

        parsed = self.parser.parse_args(sys.argv[1:])

        func = parsed.func
        # args = vars(parsed)
        # del args['func']
        args = parsed

        if args.log_level == 1:
            log.set_level('INFO')
        elif args.log_level == 2:
            log.set_level('DEBUG')

        log.debug(f'parsed {parsed}')

        del args.func

        func(args)

    def _init_build(self):
        subparser = self.subparsers.add_parser('build')
        subparser.set_defaults(func=build)

    def _init_configure(self):
        subparser = self.subparsers.add_parser('configure')
        subparser.add_argument('--source')
        subparser.add_argument('--build')
        subparser.set_defaults(func=configure)

    def _init_init_ide(self):
        subparser = self.subparsers.add_parser('init-ide')
        subparser.set_defaults(func=init_ide)

    def _init_monitor(self):
        subparser = self.subparsers.add_parser('monitor')
        subparser.set_defaults(func=_cli.monitor)

    def _init_upload(self):
        subparser = self.subparsers.add_parser('upload')
        subparser.add_argument('filename')
        subparser.add_argument('-b', '--board')
        subparser.add_argument('-p', '--port', type=int)
        subparser.set_defaults(func=_cli.upload)


def main():
    Parser()


if __name__ == '__main__':
    main()
