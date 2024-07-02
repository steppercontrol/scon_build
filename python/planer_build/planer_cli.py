#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK

import argparse
from dataclasses import dataclass, field
from importlib.resources import files
import os
from os import chmod
from os import makedirs, walk
from os.path import isdir, isfile
import shutil
from stat import S_IRUSR, S_IWUSR, S_IRGRP, S_IROTH
import sys
from typing import Tuple

import argcomplete
from mk_build.config import Config as BuildConfig
from mk_build import environ, eprint, Path

from mk_build import CompletedProcess, log, run
from mk_build.validate import ensure_type

import planer_build.configure as configure_
from planer_build.configure import Config as PlanerConfig
from .message import build_dir_bad_location, build_dir_not_found
from .tools import arduino_cli


_builders_dir = 'builders'


class FatalError(Exception):
    pass


@dataclass
class CLI:
    config: PlanerConfig = field(default_factory=PlanerConfig)
    config_file: BuildConfig = field(default_factory=BuildConfig)
    environment: dict = field(default_factory=dict)

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

        self._validate_dirs()

    def configure(self, args) -> None:
        top_build_dir = self.config_file.top_build_dir
        top_build_dir = ensure_type(top_build_dir, Path)

        top_source_dir = self.config_file.top_source_dir
        top_source_dir = ensure_type(top_source_dir, Path)

        cfg = PlanerConfig.from_file(f'{top_source_dir}/config.toml.default')

        def _planer():
            """ Write project configuration to config.toml. """

            if not isdir(top_build_dir):
                eprint(str.format(build_dir_not_found, top_build_dir))

                raise FatalError()

            path = f'{self.config_file.top_build_dir}/config.toml'

            cfg.write_toml(path, 'w')

        def _build():
            """ Write build configuration to config.toml. """

            self.config_file = BuildConfig()

            path = f'{self.config_file.top_build_dir}/config.toml'

            log.debug(f'configuration: {self.config_file}')
            log.debug(f'write configuration: {path}')

            self.config_file.write(path, 'a')

        def _config_h():
            """ Write project configuration to config.h. """
            path = f'{self.config_file.top_build_dir}/config.h'

            cfg.write_config_h(path)

        def _gup():
            """ Copy gup files. """

            log.debug(f"source {files('planer_build.gup._build')}")

            fs = files('planer_build.gup')

            log.debug(f'fs {fs}')

            _build = fs.joinpath('_build')

            import pprint

            attrs = S_IRUSR | S_IWUSR | S_IRGRP | S_IROTH

            for it in walk(_build):
                dir_name = Path(it[0]).relative_to(_build)

                dir_names = it[1]
                file_names = it[2]

                pprint.pprint(it)

                for d in dir_names:
                    makedirs(
                        Path(self.config_file.top_build_dir, d),
                        exist_ok=True
                    )

                for name in file_names:
                    source = Path(_build, dir_name, name)
                    dest = Path(self.config_file.top_build_dir, dir_name)
                    dest_file = Path(dest, name)

                    print(f'src {source} dest {dest}')

                    shutil.copy(source, dest)
                    chmod(dest_file, attrs)

            builders = fs.joinpath(_builders_dir)

            for it in walk(builders):
                dir_name = Path(it[0]).relative_to(builders)

                dir_names = it[1]
                file_names = filter(
                    lambda x: (x == 'Gupfile' or x.endswith('.gup')
                               or x.endswith('.py')),
                    it[2]
                )

                pprint.pprint(it)

                for d in dir_names:
                    makedirs(
                        Path(self.config_file.top_build_dir, d),
                        exist_ok=True
                    )

                dest_dir = Path(self.config_file.top_build_dir, _builders_dir)
                makedirs(dest_dir, exist_ok=True)

                for name in file_names:
                    source = Path(builders, dir_name, name)
                    dest = Path(self.config_file.top_build_dir, _builders_dir,
                                dir_name)
                    dest_file = Path(dest, name)

                    print(f'src {source} dest {dest}')

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

    def init_env(self, args) -> None:
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

        if args.shell:
            configure_.shell_configure()

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
                top_source_dir,
                top_build_dir
            )

        if args.arduino_core:
            # install core for board

            arduino = self.config.arduino
            core = ensure_type(arduino.core, str)
            version = ensure_type(arduino.version, str)

            log.info(f'Install core {core}')

            if arduino_cli.core_install(f'{core}@{version}').returncode != 0:
                raise Exception()

    def build(self, args) -> CompletedProcess:
        # TODO pass extra args to gup instead of forcing _build/all.

        return run(['gup', '-j', '4', '_build/all'])

        '''
        if not exists('gup'):
            gup_dir = f'{self.config_file.top_source_dir}/gup'
            gup_src = f"{environ('GUP', required=True)}/gup"

            if islink(gup_dir):
                remove(gup_dir)

            symlink(gup_src, gup_dir)
        '''

        '''
        sys_path = ':'.join(sys.path)

        python_path = sys_path + ':' + environ('PYTHONPATH')

        print(f'build run {sys.path}\n{python_path}')

        ppp = '/nix/store/pjvysa220hgr6rj76h31x88k1z5rdbz8-python3.11-planer_build-0.1.0/bin:/nix/store/psiil1nphwqprd8fb8842b0hwgpn3bix-wrapped-obs-studio-30.1.2/lib/obs-scripting:/home/boss/src/planer:/nix/store/7hnr99nxrd2aw6lghybqdmkckq60j6l9-python3-3.11.9/lib/python311.zip:/nix/store/7hnr99nxrd2aw6lghybqdmkckq60j6l9-python3-3.11.9/lib/python3.11:/nix/store/7hnr99nxrd2aw6lghybqdmkckq60j6l9-python3-3.11.9/lib/python3.11/lib-dynload:/nix/store/7hnr99nxrd2aw6lghybqdmkckq60j6l9-python3-3.11.9/lib/python3.11/site-packages:/nix/store/pjvysa220hgr6rj76h31x88k1z5rdbz8-python3.11-planer_build-0.1.0/lib/python3.11/site-packages:/nix/store/abnch2ab1jfh3kvlrf1fshnx4i2p7kdf-python3.11-argcomplete-3.3.0/lib/python3.11/site-packages:/nix/store/ld1g0lm87dq2jfg427b2jbxb4brrdh5y-python3.11-mk_build-0.1.0/lib/python3.11/site-packages:/nix/store/59clyj18mvjxbkig5z76m0b40pxkxkfq-python3.11-pytest-8.1.1/lib/python3.11/site-packages:/nix/store/ihj3vxwv7wn7lgpja37gjvqb55x0kx90-python3.11-iniconfig-2.0.0/lib/python3.11/site-packages:/nix/store/lwjnn5iyh8jzzhbvlqw31498mhhkmhcx-python3.11-packaging-24.0/lib/python3.11/site-packages:/nix/store/bc5iy2ky85k1v46hfs4myhd0c35i2rmi-python3.11-pluggy-1.4.0/lib/python3.11/site-packages:/nix/store/w1ar41xsp31nris574c2gl0c1vsl7hcn-python3.11-tomlkit-0.12.4/lib/python3.11/site-packages:/nix/store/g4h9138sa5wh6kkfwc7f49q169wcs8s9-python3.11-setuptools-69.5.1/lib/python3.11/site-packages:/nix/store/psiil1nphwqprd8fb8842b0hwgpn3bix-wrapped-obs-studio-30.1.2/lib/obs-scripting:/nix/store/psiil1nphwqprd8fb8842b0hwgpn3bix-wrapped-obs-studio-30.1.2/lib/obs-scripting'  # noqa

        env = {
            'PYTHONPATH': ppp
        }

        return run(['gup', '-j', '4', '_build/all'], env=env)
        '''

    def clean(self, args) -> None:
        """ Clean the build directory. """

        build_dir = self._ensure_build_dir()

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

    def _validate_dirs(self) -> Tuple[Path, Path]:
        top_build_dir = self.config_file.top_build_dir
        top_build_dir = ensure_type(top_build_dir, Path)

        top_source_dir = self.config_file.top_source_dir
        top_source_dir = ensure_type(top_source_dir, Path)

        if top_build_dir == top_source_dir:
            raise ValueError(build_dir_bad_location)

        return (top_source_dir, top_build_dir)

    def _ensure_build_dir(self) -> Path:
        top_build_dir = self.config_file.top_build_dir
        return ensure_type(top_build_dir, Path)


class Parser:
    def __init__(self, cli) -> None:
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

        argcomplete.autocomplete(self.parser)

        parsed = self.parser.parse_args(sys.argv[1:])

        func = parsed.func
        # args = vars(parsed)
        # del args['func']
        args = parsed

        if args.log_level == 0:
            log.set_level('WARNING')
        if args.log_level == 1:
            log.set_level('INFO')
        elif args.log_level == 2:
            log.set_level('DEBUG')

        if args.log_level >= 1:
            log.set_detail(1)

        cli.init(**vars(args))

        del args.func

        func(args)

    def _init_build(self, cli) -> None:
        subparser = self.subparsers.add_parser('build')
        subparser.set_defaults(func=cli.build)

    def _init_clean(self, cli) -> None:
        subparser = self.subparsers.add_parser('clean')
        subparser.set_defaults(func=cli.clean)

    def _init_configure(self, cli) -> None:
        subparser = self.subparsers.add_parser('configure')
        subparser.set_defaults(func=cli.configure)

    def _init_init_env(self, cli) -> None:
        subparser = self.subparsers.add_parser('init')
        subparser.add_argument('--shell', action='store_true')
        subparser.add_argument('--arduino-ide', action='store_true')
        subparser.add_argument('--arduino-core', action='store_true')
        subparser.set_defaults(func=cli.init_env)

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
    except ValueError as e:
        eprint(e)
        sys.exit(1)
    except FatalError:
        sys.exit(1)


if __name__ == '__main__':
    main()
