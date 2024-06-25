#!/usr/bin/env python

from dataclasses import dataclass
import string
import sys
import tomllib

from mk_build import log
import tomlkit


@dataclass
class ConfigH:
    board: str
    port: str

    @classmethod
    def from_file(cls, path):
        with open(path, 'rb') as f:
            toml = tomllib.load(f)

        log.debug(f'config {toml}')

        ctx = cls(board=toml['board'], port=toml['port'])

        t = toml['keypad']

        subs = {
            'row_pins': ConfigH._initializer(t['row_pins']),
            'col_pins': ConfigH._initializer(t['column_pins']),
        }

        keypad = string.Template(_config['keypad']).substitute(subs)

        t = toml['motor']

        subs = {
            'steps_per_revolution': t['steps_per_revolution'],
            'pins': ConfigH._initializer(t['pins'])
        }

        motor = string.Template(_config['motor']).substitute(subs)

        t = toml['display']

        subs = {
            'controller': t['controller'],
            'buffer_mode': ConfigH._buffer_mode(t['buffer_mode']),
            'clock': t['clock'],
            'data': t['data'],
            'cs': t['cs'],
            'dc': t['dc'],
            'reset': t['reset'],
            'backlight': t['backlight']
        }

        display = string.Template(_config['display']).substitute(subs)

        template = string.Template(_config['full']).substitute(keypad=keypad,
            motor=motor, display=display)

        print(template)
        ctx.toml = tomlkit.dumps(toml)

        return ctx

    @staticmethod
    def _initializer(list_):
        array = str(list_)
        return '{' + array[1:-1] + '}'

    @staticmethod
    def _buffer_mode(val):
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


def main():
    path = sys.argv[1]

    ConfigH.from_file(path)


if __name__ == '__main__':
    main()
