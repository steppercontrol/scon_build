#!/usr/bin/env python

from dataclasses import dataclass, field

from mk_build import *
import mk_build.config as config_
import planer_build.configure as planer_config_
from planer_build.tools import arduino_cli

config = config_.get()
planer_config = planer_config_.get()


@dataclass
class ArduinoBin(Target):
    """ Builds .elf and associated files using arduino-cli compile. """

    libraries: Path = field(default_factory=Path)

    def update(self) -> CompletedProcess[bytes]:
        super().update()

        Path(self.sources[0]).touch()

        return arduino_cli.compile(
            self.sources[0],
            build_dir(),
            self.libraries
        )


if __name__ == '__main__':
    libraries = path(top_source_dir(), 'libraries')

    sources = top_source_dir_add(
        [path(ensure_type(config.target, Path)).with_suffix('')]
    )

    builder = ArduinoBin(libraries=libraries, sources=sources)

    builder.update()
