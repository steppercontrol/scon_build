#!/usr/bin/env python

from dataclasses import dataclass, field

from mk_build import *
import mk_build.config as config_

config = config_.get()


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

    sources = top_source_dir_add([path(config.target).with_suffix('')])

    builder = ArduinoBin(libraries=libraries, sources=sources)

    result = builder.update()

    exit(result)
