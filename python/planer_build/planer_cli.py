#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK

import argparse
from dataclasses import dataclass, field
import os
from os.path import isfile
import sys

import argcomplete
# import mk_build.configure
from mk_build.config import Config as BuildConfig
from mk_build import environ, eprint, Path

from mk_build import CompletedProcess, log, run
from mk_build.util import isdir
from mk_build.validate import ensure_type

import planer_build.configure as configure_
from planer_build.configure import Config as PlanerConfig
from .message import build_dir_not_found
from .tools import arduino_cli


class FatalError(Exception):
    pass


@dataclass
class CLI:
    config: PlanerConfig = field(default_factory=PlanerConfig)
    config_file: BuildConfig = field(default_factory=BuildConfig)
    environment: dict = field(default_factory=dict)

    def __post_init__(self, *args, **kwargs) -> None:
        self.init(**kwargs)

    def init(self, **kwargs) -> None:
        if 'source' not in kwargs or kwargs['source'] is None:
            source = os.getcwd()
            log.info(f'Auto-detected source directory: {source}')
        else:
            source = kwargs['source']

        # The top build directory will have been set when we imported
        # mk_build.config above. Override it if provided.

        if 'build' in kwargs and kwargs['build'] is not None:
            build = str(Path(kwargs['build']).absolute())
            os.environ['top_build_dir'] = build
        else:
            build = environ('top_build_dir')

        # TODO not sure if we need this in environment

        os.environ['top_source_dir'] = source

        path = f'{build}/config.toml'

        if isfile(path):
            self.config = PlanerConfig.from_file(path)
            self.config_file = BuildConfig.from_file(path)

        # If arguments are provided, override config file.

        self.config_file.top_source_dir = Path(source)
        self.config_file.top_build_dir = Path(build)

        log.debug(f'CLI {self}')

    def configure(self, args) -> None:
        # TODO get this from a known path

        cfg = PlanerConfig.from_file('config.toml.default')
        log.debug(f'config {cfg}')

        top_build_dir = self.config_file.top_build_dir

        if not isdir(top_build_dir):
            eprint(str.format(build_dir_not_found, top_build_dir))

            raise FatalError()

        path = f'{self.config_file.top_build_dir}/config.toml'

        cfg.write_toml(path, 'w')

        self.config_file = BuildConfig()

        log.debug(f'configuration: {self.config_file}')
        log.debug(f'write configuration: {path}')

        self.config_file.write(path, 'a')

        top_build_dir = ensure_type(top_build_dir, Path)

        configure_.envrc_write(top_build_dir)

        # mk_build.configure.main()

    def init_ide(self, args) -> None:
        # detect installation

        try:
            self.config.environment = {
                'arduino': environ('ARDUINO', required=True),
                'arduino_ide': environ('ARDUINO_IDE', required=True),
                'arduino_ide_data': environ('ARDUINO_IDE_DATA', required=True),
                'arduino_cli': environ('ARDUINO_CLI', required=True)
            }
        except Exception as e:
            eprint(e)

            raise FatalError()

        # TODO modify settings.json

        # install core for board

        arduino = self.config.arduino
        core = ensure_type(arduino.core, str)
        version = ensure_type(arduino.version, str)

        log.info(f'Install core {core}')

        if arduino_cli.core_install(f'{core}@{version}').returncode != 0:
            raise Exception()

        # modify platform settings for builds
        # modify arduino-cli.yaml (sketchbook)

        top_source_dir = self.config_file.top_source_dir
        top_build_dir = self.config_file.top_build_dir

        top_source_dir = ensure_type(top_source_dir, Path)
        top_build_dir = ensure_type(top_build_dir, Path)

        configure_.arduino_ide_configure(
            self.config,
            top_source_dir,
            top_build_dir
        )

    def monitor(self, args) -> None:
        board = self.config.arduino.board
        port = self.config.arduino.port

        run([
            'arduino-cli', 'monitor',
            '-q',
            '-b', board,
            '-p', port,
            '-v'
        ])

    def upload(self, args) -> None:
        # arduino-cli upload $sketch -b $BOARD -p $port -v && \
        # arduino-cli upload --input-file $sketch -b $BOARD -p $port -v && \
        # arduino-cli monitor -q --raw -b $BOARD -p $port -c baudrate=115200

        board = self.config.arduino.board
        port = self.config.arduino.port

        run([
            'arduino-cli', 'upload',
            '--input-file', args.filename,
            '-b', board,
            '-p', port,
            '-v'
        ])


def build(args) -> CompletedProcess:
    return run(['gup', '-j', '4'])


class Parser:
    def __init__(self, cli) -> None:
        self.parser = argparse.ArgumentParser(
            prog='ProgramName',
            description='What the program does',
            epilog='Text at the bottom of help')

        self.subparsers = self.parser.add_subparsers(required=True)

        self._init_configure(cli)
        self._init_init_ide(cli)
        self._init_build()
        self._init_monitor(cli)
        self._init_upload(cli)

        self.parser.add_argument('-l', '--log-level', type=int)
        self.parser.add_argument('--source')
        self.parser.add_argument('--build')

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

        cli.init(**vars(args))

        del args.func

        func(args)

    def _init_build(self) -> None:
        subparser = self.subparsers.add_parser('build')
        subparser.set_defaults(func=build)

    def _init_configure(self, cli) -> None:
        subparser = self.subparsers.add_parser('configure')
        subparser.set_defaults(func=cli.configure)

    def _init_init_ide(self, cli) -> None:
        subparser = self.subparsers.add_parser('init-ide')
        subparser.set_defaults(func=cli.init_ide)

    def _init_monitor(self, cli) -> None:
        subparser = self.subparsers.add_parser('monitor')
        subparser.set_defaults(func=cli.monitor)

    def _init_upload(self, cli) -> None:
        subparser = self.subparsers.add_parser('upload')
        subparser.add_argument('filename')
        subparser.add_argument('-b', '--board')
        subparser.add_argument('-p', '--port', type=int)
        subparser.set_defaults(func=cli.upload)


def main() -> None:
    try:
        cli = CLI()

        Parser(cli)
    except FatalError:
        sys.exit(1)


if __name__ == '__main__':
    main()
