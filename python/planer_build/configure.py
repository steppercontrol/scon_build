#!/usr/bin/env python

from dataclasses import dataclass, field
import string
from os.path import exists
from typing import Optional

from mk_build import log, environ, eprint, path, Path, PathInput
from mk_build.config import BaseConfig
from mk_build.validate import ensure_type
from tomlkit.items import Table

from .message import platform_build_extra_flags


def envrc_write(build: PathInput) -> None:
    with open('.envrc', 'r') as fi:
        lines = fi.readlines()

    with open('.envrc', 'w') as fi:
        out_line = f'export top_build_dir="{build}"\n'
        replaced = False

        for it in lines:
            if not it.startswith('export top_build_dir'):
                fi.write(it)
            else:
                fi.write(out_line)
                eprint(f'.envrc: replace top build dir with {build}')
                replaced = True

        if not replaced:
            fi.write(out_line)


def arduino_ide_configure(
    config: 'Config',
    source: Path,
    build: Path
) -> None:
    _arduino_ide_cli_configure(config, source, build)
    _arduino_ide_platform_configure(config, source, build)


def _arduino_ide_cli_configure(
    config: 'Config',
    source: Path,
    build: Path
) -> None:
    data = environ('ARDUINO_IDE_DATA', required=True)
    path = f'{data}/arduino-cli.yaml'

    with open(path, 'r') as fi:
        lines = fi.readlines()

    with open(path, 'w') as fi:
        out_line = f'user: {source}'
        replaced = False

        for it in lines:
            idx = it.find('user:')

            if idx == -1:
                fi.write(it)
            elif out_line == it.strip():
                fi.write(it)
                replaced = True
            else:
                fi.write(f'{it[:idx + len("user:")]} {source}\n')

                eprint(
                    f'arduino-cli.yaml: replace user directory with "{source}"'
                )
                replaced = True

        if not replaced:
            raise Exception(
                'arduino-cli.yaml: user directory entry not found'
            )


def _arduino_ide_platform_configure(
    config: 'Config',
    source: Path,
    build: Path
) -> None:
    platform_path = path(_arduino_core_path(config), 'platform.local.txt')

    # flags for master branch
    flags = f'-I{build} -DU8G2_USE_DYNAMIC_ALLOC'
    out_line = f'build.extra_flags={flags}\n'

    try:
        with open(platform_path, 'r') as fi:
            lines = fi.readlines()

        with open(platform_path, 'w') as fi:
            replaced = False

            for it in lines:
                if not it.startswith('build.extra_flags='):
                    fi.write(it)
                else:
                    fi.write(out_line)
                    eprint(str.format(platform_build_extra_flags, flags))
                    replaced = True

            if not replaced:
                fi.write(out_line)
    except FileNotFoundError:
        # The file doesn't exist, so create it and add our content.

        with open(platform_path, 'w') as fi:
            fi.write(out_line)


def _arduino_core_path(config) -> Path:
    arch = _arduino_arch(config.arduino.core)
    version = config.arduino.version

    return Path(f"{config.environment['arduino']}/hardware/{arch}/{version}")


def _arduino_arch(core) -> str:
    return core[core.find(':') + 1:]


@dataclass
class Config(BaseConfig):
    @dataclass
    class Arduino:
        core: Optional[str] = None
        version: Optional[str] = None
        board: Optional[str] = None
        port: Optional[str] = None

    arduino: Arduino = field(default_factory=Arduino)
    environment: dict = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: str) -> 'Config':
        """ Parse the configuration from an existing file. """

        ctx = cls()
        ctx._init_from_file(path)

        log.debug(f'config {ctx.config}')

        arduino = ensure_type(ctx.config.get('arduino'), Table)

        ctx.arduino = cls.Arduino(
            ensure_type(arduino.get('core'), str),
            ensure_type(arduino.get('version'), str),
            ensure_type(arduino.get('board'), str),
            ensure_type(arduino.get('port'), str)
        )

        return ctx

    def write_config_h(self, path: str) -> None:
        toml = self.config
        t = ensure_type(toml['keypad'], Table)

        subs: dict[str, str | int] = {
            'row_pins': Config._initializer(t['row_pins']),
            'col_pins': Config._initializer(t['column_pins']),
        }

        keypad = string.Template(_config['keypad']).substitute(subs)

        t = ensure_type(toml['motor'], Table)

        subs = {
            'steps_per_revolution': ensure_type(
                t['steps_per_revolution'],
                int
            ),
            'pins': Config._initializer(t['pins'])
        }

        motor = string.Template(_config['motor']).substitute(subs)

        t = ensure_type(toml['display'], Table)

        subs = {
            'controller': ensure_type(t['controller'], str),
            'buffer_mode': Config._buffer_mode(
                ensure_type(t['buffer_mode'], str)
            ),
            'clock': ensure_type(t['clock'], int),
            'data': ensure_type(t['data'], int),
            'cs': ensure_type(t['cs'], int),
            'dc': ensure_type(t['dc'], int),
            'reset': ensure_type(t['reset'], int),
            'backlight': ensure_type(t['backlight'], int)
        }

        display = string.Template(_config['display']).substitute(subs)

        template = string.Template(_config['full']).substitute(
            keypad=keypad,
            motor=motor,
            display=display
        )

        with open(path, 'w') as fi:
            fi.write(template)

    def write_toml(self, path: str, mode='w') -> None:
        self.write(path, mode)

    @staticmethod
    def _initializer(list_) -> str:
        array = str(list_)
        return '{' + array[1:-1] + '}'

    @staticmethod
    def _buffer_mode(val: str) -> str:
        if val == '1Page':
            result = '_1Page'
        elif val == '2Page':
            result = '_2Page'
        elif val == 'Full':
            result = 'Full'
        else:
            raise ValueError()

        return result


_config = {
    'keypad': """
static struct KeypadConfig keypadConfig = {
    .rowPins = ${row_pins},
    .colPins = ${col_pins}
};
    """,
    'motor': """
static struct MotorConfig motorConfig = {
    .stepsPerRevolution = ${steps_per_revolution},
    .pins = ${pins}
};
    """,
    'display': """
static struct DisplayConfig displayConfig = {
    .controller = ${controller},
    .bufferMode = ${buffer_mode},
    .clock = ${clock},
    .data = ${data},
    .cs = ${cs},
    .dc = ${dc},
    .reset = ${reset},
    .backlight = ${backlight}
};
    """,
    'full': """#ifndef Planer__config_h_INCLUDED
#define Planer__config_h_INCLUDED

#include "input.h"
#include "motor.h"
#include "display.h"

/// Input
${keypad}
/// Motor
${motor}
/// Display

/// Display controller
/// Only one out of the following list may be defined.

/// Display buffer type
/// 1: 1 page buffer, 2: 2 page buffer, else full buffering
${display}
#endif // Planer__config_h_INCLUDED"""}


def _create(*args, **kwargs) -> Config:
    config_path = f'{environ("top_build_dir")}/config.toml'

    if exists(config_path):
        config = Config.from_file(config_path)
    else:
        config = Config(*args, **kwargs)

    return config


config = _create()


def get():
    return config
