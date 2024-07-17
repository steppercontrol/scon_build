#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK

import argparse
from dataclasses import dataclass, field
from importlib.resources import files
import json
import os
from os import chmod
from os import makedirs, walk
from os.path import isdir, isfile
import shutil
from stat import S_IRUSR, S_IWUSR, S_IRGRP, S_IROTH
import sys
from typing import Any, Tuple

import argcomplete
import mk_build
from mk_build.config import Config as BuildConfig
from mk_build import environ, eprint, gup, Path

from mk_build import CompletedProcess, log, run
from mk_build.validate import ensure_type

import planer_build.configure as configure_
from planer_build.configure import Config as PlanerConfig
from .error import FatalError
from .message import build_dir_bad_location, build_dir_not_found
from .tools import arduino_cli
from .util import wsl_from_win


_builders_dir = 'builders'


@dataclass
class CLI:
    config: PlanerConfig = field(default_factory=PlanerConfig)
    config_file: BuildConfig = field(default_factory=BuildConfig)
    environment: dict[str, str] = field(default_factory=dict)

    def init(self, load: bool, **kwargs: Any) -> None:
        self._init_log(kwargs['log_level'])

        log.debug(f'parsed args {kwargs}')

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
            build = ensure_type(environ('top_build_dir'), str)

        # TODO not sure if we need this in environment

        os.environ['top_source_dir'] = source

        path = f'{build}/config.toml'

        if load and isfile(path):
            self.config = PlanerConfig.from_file(path)
            self.config_file = BuildConfig.from_file(path)

        # If arguments are provided, override config file.

        self.config_file.top_source_dir = Path(source)
        self.config_file.top_build_dir = Path(build)

        self._validate_dirs()

        # Determine paths for Arduino installation.

        self._environment_import(**kwargs)

    def configure(self, args: argparse.Namespace) -> None:
        top_build_dir = self.config_file.top_build_dir
        top_build_dir = ensure_type(top_build_dir, Path)

        top_source_dir = self.config_file.top_source_dir
        top_source_dir = ensure_type(top_source_dir, Path)

        if args.config is None:
            scon_config = f'{top_source_dir}/config.toml.default'
        else:
            scon_config = f'{args.config}'

        cfg = PlanerConfig.from_file(scon_config)

        def _planer() -> None:
            """ Write project configuration to config.toml. """

            if not isdir(top_build_dir):
                eprint(str.format(build_dir_not_found, top_build_dir))

                raise FatalError()

            path = f'{self.config_file.top_build_dir}/config.toml'

            cfg.write_toml(path, 'w')

        def _build() -> None:
            """ Write build configuration to config.toml. """

            path = f'{self.config_file.top_build_dir}/config.toml'

            log.debug(f'configuration: {self.config_file}')
            log.debug(f'write configuration: {path}')

            self.config_file.write(path, 'a')

        def _config_h() -> None:
            """ Write project configuration to config.h. """
            path = f'{self.config_file.top_build_dir}/config.h'

            cfg.write_config_h(path)

        def _gup() -> None:
            """ Copy gup files. """

            log.debug(f"source {files('planer_build.gup._build')}")

            fs = files('planer_build.gup')

            log.debug(f'fs {fs}')

            _build = ensure_type(fs.joinpath('_build'), Path)

            attrs = S_IRUSR | S_IWUSR | S_IRGRP | S_IROTH

            top_build_dir = ensure_type(self.config_file.top_build_dir, Path)

            for it in walk(str(_build)):
                dir_name = Path(it[0]).relative_to(_build)

                dir_names = it[1]
                file_names = it[2]

                for d in dir_names:
                    makedirs(
                        Path(top_build_dir, d),
                        exist_ok=True
                    )

                for name in file_names:
                    source = Path(_build, dir_name, name)
                    dest = Path(top_build_dir, dir_name)
                    dest_file = Path(dest, name)

                    # print(f'src {source} dest {dest}')

                    shutil.copy(source, dest)
                    chmod(dest_file, attrs)

            builders = str(fs.joinpath(_builders_dir))

            for it2 in walk(builders):
                dir_name = Path(it2[0]).relative_to(builders)

                dir_names = it2[1]
                file_names = list(
                    filter(
                        lambda x: (x == 'Gupfile' or x.endswith('.gup')
                                   or x.endswith('.py')),
                        it2[2]
                    )
                )

                for d in dir_names:
                    makedirs(
                        Path(top_build_dir, d),
                        exist_ok=True
                    )

                dest_dir = Path(top_build_dir, _builders_dir)
                makedirs(dest_dir, exist_ok=True)

                for name in file_names:
                    source = Path(builders, dir_name, name)
                    dest = Path(top_build_dir, _builders_dir, dir_name)
                    dest_file = Path(dest, name)

                    # print(f'src {source} dest {dest}')

                    shutil.copy(source, dest)

                    chmod(dest_file, attrs)

            '''
            shutil.copytree(
                _build,
                self.config_file.top_build_dir,
                dirs_exist_ok=True
            )
            '''

            '''
            breakpoint()

            log.debug(f'fs {fs}')

            if not fs.is_file():
                for it in fs.iterdir():
                    if isdir(it):
                        shutil.copytree(
                            it,
                            self.config_file.top_build_dir,
                            dirs_exist_ok=True
                        )
                    else:
                        shutil.copy(it, self.config_file.top_build_dir)
            else:
                assert False
                with as_file(fs) as fi:
                    log.debug(f'fi {fi}')

                    shutil.copytree(
                        fi,
                        self.config_file.top_build_dir,
                        dirs_exist_ok=True
                    )

            builders_dest = f'{self.config_file.top_build_dir}/builders'

            makedirs(builders_dest, exist_ok=True)

            fs = files('planer_build.gup.builders')

            with as_file(fs) as fi:
                shutil.copytree(
                    fi,
                    builders_dest,
                    dirs_exist_ok=True
                )
            '''

        _planer()
        _build()
        _config_h()

        configure_.envrc_write(top_build_dir)

        _gup()

    def init_env(self, args: argparse.Namespace) -> None:
        if args.shell:
            configure_.shell_configure()

        if args.arduino_core:
            # install core for board

            arduino = self.config.arduino
            core = ensure_type(arduino.core, str)
            version = ensure_type(arduino.version, str)

            log.info(f'Install core {core}')

            if arduino_cli.core_install(f'{core}@{version}').returncode != 0:
                raise Exception()

        if args.arduino_ide:
            # TODO modify settings.json

            # modify platform settings for builds
            # modify arduino-cli.yaml (sketchbook)

            top_source_dir = self.config_file.top_source_dir
            top_build_dir = self.config_file.top_build_dir

            top_source_dir = ensure_type(top_source_dir, Path)
            top_build_dir = ensure_type(top_build_dir, Path)

            configure_.arduino_ide_configure(
                self.config,
                self.config_file,
                top_source_dir,
                top_build_dir
            )

    def build(self, args: argparse.Namespace) -> CompletedProcess[bytes]:
        # TODO pass extra args to gup instead of forcing _build/all.

        env = {
            'ARDUINO_CLI': self.config.environment['arduino_cli']
        }

        if len(args.targets) == 0:
            targets = ['_build/all']
        else:
            targets = args.targets

        return ensure_type(
            gup(targets, jobs=4, env=env),
            CompletedProcess
        )

    def clean(self, args: argparse.Namespace) -> None:
        """ Clean the build directory. """

        (_, build_dir) = self._ensure_dirs()

        def is_config_file(path: Path) -> bool:
            parent = path.parent.name
            name = path.name

            return (parent == _builders_dir or name.endswith('.gup')
                    or name == 'Gupfile' or name == 'config.h'
                    or name == 'config.toml')

        for it in walk(build_dir):
            path = Path(it[0])
            paths = [Path(path, x) for x in it[2]]

            to_delete = list(filter(lambda x: not is_config_file(x), paths))
            to_delete = [Path(path, x) for x in to_delete]

            for jj in to_delete:
                os.remove(jj)

    def upload(self, args: argparse.Namespace) -> None:
        # arduino-cli upload $sketch -b $BOARD -p $port -v && \
        # arduino-cli upload --input-file $sketch -b $BOARD -p $port -v && \
        # arduino-cli monitor -q --raw -b $BOARD -p $port -c baudrate=115200

        arduino_cli.upload(args.filename)

    def monitor(self, args: argparse.Namespace) -> None:
        arduino_cli.monitor()

    def _init_log(self, log_level: int) -> None:
        if log_level == 0:
            log_level_str = 'WARNING'
        if log_level == 1:
            log_level_str = 'INFO'
        elif log_level == 2:
            log_level_str = 'DEBUG'

        log.init(log_level_str)

        if log_level >= 1:
            log.set_detail(1)

        os.environ['MK_LOG_LEVEL'] = log_level_str

    def _validate_dirs(self) -> Tuple[Path, Path]:
        (top_source_dir, top_build_dir) = self._ensure_dirs()

        if top_build_dir == top_source_dir:
            raise ValueError(build_dir_bad_location)

        return (top_source_dir, top_build_dir)

    def _ensure_dirs(self) -> Tuple[Path, Path]:
        top_build_dir = self.config_file.top_build_dir
        top_build_dir = ensure_type(top_build_dir, Path)

        top_source_dir = self.config_file.top_source_dir
        top_source_dir = ensure_type(top_source_dir, Path)

        return (top_source_dir, top_build_dir)

    def _environment_import(self, **kwargs: Any) -> None:
        if 'wsl' in kwargs and kwargs['wsl']:
            env = {'WSL': 'y'}
        else:
            env = {}

        set_env = mk_build.path(
            ensure_type(files('planer_build.tools'), Path),
            'planer_set_env'
        )

        result = run([set_env], env=env, capture_output=True)

        stdout = json.loads(result.stdout)

        if self.config_file.system.build.system == 'wsl':
            os.environ['ARDUINO_IDE'] = wsl_from_win(stdout['arduino_ide'])
            os.environ['ARDUINO_CLI'] = wsl_from_win(stdout['arduino_cli'])

            stdout['arduino'] = wsl_from_win(stdout['arduino'])
            stdout['arduino_ide'] = wsl_from_win(stdout['arduino_ide'])
            stdout['arduino_ide_data'] = wsl_from_win(
                stdout['arduino_ide_data'])
            stdout['arduino_cli'] = wsl_from_win(stdout['arduino_cli'])
        else:
            os.environ['ARDUINO_IDE'] = stdout['arduino_ide']
            os.environ['ARDUINO_CLI'] = stdout['arduino_cli']

        self.config.environment = stdout

        log.debug(f'environment {self.config.environment}')


class Parser:
    def __init__(self, cli: CLI) -> None:
        self.parser = argparse.ArgumentParser(
            prog='ProgramName',
            description='What the program does',
            epilog='Text at the bottom of help')

        self.subparsers = self.parser.add_subparsers(required=True)

        self._init_configure(cli)
        self._init_init_env(cli)
        self._init_build(cli)
        self._init_clean(cli)
        self._init_monitor(cli)
        self._init_upload(cli)

        self.parser.add_argument('-l', '--log-level', type=int, default=0)
        self.parser.add_argument('--source')
        self.parser.add_argument('--build')
        self.parser.add_argument('--wsl', action='store_true')

        argcomplete.autocomplete(self.parser)

        parsed = self.parser.parse_args(sys.argv[1:])

        func = parsed.func
        args = parsed

        load = func != cli.configure

        cli.init(load, **vars(args))

        del args.func

        func(args)

    def _init_build(self, cli: CLI) -> None:
        subparser = self.subparsers.add_parser('build')
        subparser.add_argument('targets', nargs='*')
        subparser.set_defaults(func=cli.build)

    def _init_clean(self, cli: CLI) -> None:
        subparser = self.subparsers.add_parser('clean')
        subparser.set_defaults(func=cli.clean)

    def _init_configure(self, cli: CLI) -> None:
        subparser = self.subparsers.add_parser('configure')
        subparser.add_argument('--config', type=str)
        subparser.set_defaults(func=cli.configure)

    def _init_init_env(self, cli: CLI) -> None:
        subparser = self.subparsers.add_parser('init')
        subparser.add_argument('--shell', action='store_true')
        subparser.add_argument('--arduino-ide', action='store_true')
        subparser.add_argument('--arduino-core', action='store_true')
        subparser.set_defaults(func=cli.init_env)

    def _init_monitor(self, cli: CLI) -> None:
        subparser = self.subparsers.add_parser('monitor')
        subparser.set_defaults(func=cli.monitor)

    def _init_upload(self, cli: CLI) -> None:
        subparser = self.subparsers.add_parser('upload')
        subparser.add_argument('filename')
        subparser.add_argument('-b', '--board')
        subparser.add_argument('-p', '--port', type=int)
        subparser.set_defaults(func=cli.upload)


def main() -> None:
    try:
        cli = CLI()

        Parser(cli)
    except ValueError as e:
        eprint(e)
        sys.exit(1)
    except FatalError as e:
        eprint(e)
        sys.exit(1)


if __name__ == '__main__':
    main()
