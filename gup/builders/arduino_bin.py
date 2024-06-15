#!/usr/bin/env python

from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from mk_build import *
from mk_build.config import config


@dataclass
class ArduinoBin(Target):
    """ Builds .elf and associated files using arduino-cli compile. """

    libraries: Path = field(default_factory=Path)

    def update(self):
        super().update()

        build_path = build_dir()

        board = 'arduino:avr:mega'

        args = [
            'arduino-cli', 'compile', self.sources[0],
            '--optimize-for-debug',
            '--build-path', build_path,
            '--warnings', 'all',
            '-b', board,
            '--libraries', self.libraries
        ]

        if config.verbose > 0:
            args.append('-v')

        return run(args)


if __name__ == '__main__':
    libraries = path(top_source_dir(), 'libraries')

    builder = ArduinoBin(name=target, libraries=libraries)

    build_dir_ = cast(Path, build_dir())

    source = source_dir([path(target).relative_to(build_dir_).with_suffix('')])

    source = cast(list[Path], source)

    builder.add_source(source[0])

    result = builder.update()

    exit(result)
