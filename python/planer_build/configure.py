#!/usr/bin/env python

from dataclasses import dataclass, field
import string
from os.path import exists
from typing import Any, Optional, Sequence

from mk_build import log, environ, eprint, path, Path, PathInput
from mk_build.config import BaseConfig, Config as BuildConfig
from mk_build.validate import ensure_type
from tomlkit.items import Table

from .error import FatalError
from .message import arduino_ide_error_not_found, platform_build_extra_flags
from .util import win_from_wsl


def envrc_write(build: PathInput) -> None:
    out_line = f'export top_build_dir="{build}"\n'
    envrc = '.envrc'

    try:
        with open(envrc, 'r') as fi:
            lines = fi.readlines()

        with open(envrc, 'w') as fi:
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
    except FileNotFoundError:
        with open(envrc, 'w') as fi:
            fi.write(out_line)


def shell_configure() -> None:
    rc = Path(ensure_type(environ('HOME'), str), '.bashrc')
    out_line = 'eval "$(direnv hook bash)"'

    found = False

    try:
        with open(rc, 'r') as fi:
            lines = fi.readlines()

        for it in lines:
            if it.startswith(out_line):
                found = True
                break
    except FileNotFoundError:
        # The file doesn't exist, so create it and add our content.
        pass

    if not found:
        with open(rc, 'a') as fi:
            fi.write(f'{out_line}\n')


def arduino_ide_configure(
    config: 'Config',
    build_config: BuildConfig,
    source: Path,
    build: Path
) -> None:
    _ensure_arduino_ide(config)

    _arduino_ide_cli_configure(config, source, build)
    _arduino_ide_platform_configure(config, build_config, source, build)


def _ensure_arduino_ide(config: 'Config') -> None:
    data = config.environment['arduino_ide_data']

    if not exists(data):
        raise FatalError(str.format(arduino_ide_error_not_found, data))


def _arduino_ide_cli_configure(
    config: 'Config',
    source: Path,
    build: Path
) -> None:
    data = config.environment['arduino_ide_data']
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


# TODO correctly write windows path for sketchbook location.

def _arduino_ide_platform_configure(
    config: 'Config',
    build_config: BuildConfig,
    source: Path,
    build: Path
) -> None:
    platform_path = path(_arduino_core_path(config), 'platform.local.txt')

    if build_config.system.build.system == 'wsl':
        build = Path(win_from_wsl(build))

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


def _arduino_core_path(config: 'Config') -> Path:
    arch = _arduino_arch(ensure_type(config.arduino.core, str))
    version = config.arduino.version

    return Path(f"{config.environment['arduino']}/hardware/{arch}/{version}")


def _arduino_arch(core: str) -> str:
    return core[core.find(':') + 1:]


@dataclass
class Config(BaseConfig):
    @dataclass
    class Arduino:
        core: Optional[str] = None
        version: Optional[str] = None
        board: Optional[str] = None
        port: Optional[str] = None

    log_level: str = 'WARNING'

    arduino: Arduino = field(default_factory=Arduino)
    environment: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: str) -> 'Config':
        """ Parse the configuration from an existing file. """

        ctx = cls()
        ctx._init_from_file(path)

        log.debug(f'config {ctx.config}')

        ctx.log_level = ensure_type(ctx.config.get('log_level'), str)

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

        log_level_item = f"LOG_{ensure_type(toml['log_level'], str)}"

        log = string.Template(_config['log']).substitute(
            {'log_level': log_level_item})

        t = ensure_type(toml['keypad'], Table)

        subs: dict[str, str | int] = {
            'row_pins': Config._initializer(ensure_type(t['row_pins'], list)),
            'col_pins': Config._initializer(ensure_type(t['column_pins'],
                                            list))
        }

        keypad = string.Template(_config['keypad']).substitute(subs)

        t = ensure_type(toml['motor'], Table)

        driver = ensure_type(t['driver'], str)

        if driver == "driver":
            driver = "motor::Driver"
        elif driver == "full4wire":
            driver = "motor::Full4Wire"

        subs = {
            'driver': driver,
            'steps_per_revolution': ensure_type(
                t['steps_per_revolution'],
                int
            ),
            'pins': Config._initializer(ensure_type(t['pins'], list))
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
            log=log,
            keypad=keypad,
            motor=motor,
            display=display
        )

        with open(path, 'w') as fi:
            fi.write(template)

    def write_toml(self, path: str, mode: str = 'w') -> None:
        self.write(path, mode)

    @staticmethod
    def _initializer(list_: Sequence[int]) -> str:
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
    'log': """
__attribute__((unused))
static struct LogConfig logConfig = {
    .level = ${log_level}
};
    """,
    'keypad': """
__attribute__((unused))
static struct KeypadConfig keypadConfig = {
    .rowPins = ${row_pins},
    .colPins = ${col_pins}
};
    """,
    'motor': """
__attribute__((unused))
static struct MotorConfig motorConfig = {
    .driver = ${driver},
    .stepsPerRevolution = ${steps_per_revolution},
    .pins = ${pins}
};
    """,
    'display': """
__attribute__((unused))
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
#include "util.h"

/// Log
${log}
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


def _create(*args: Any, **kwargs: Any) -> Config:
    config_path = f'{environ("top_build_dir")}/config.toml'

    if exists(config_path):
        config = Config.from_file(config_path)
    else:
        config = Config(*args, **kwargs)

    return config


config = _create()


def get() -> Config:
    return config
