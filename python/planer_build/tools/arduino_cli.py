from dataclasses import asdict
from operator import itemgetter

from mk_build import CompletedProcess, environ, run
import mk_build.config as config_
import planer_build.configure as planer_config_

config = config_.get()
planer_config = planer_config_.get()

_arduino_cli = environ('ARDUINO_CLI', 'arduino-cli')


def compile(
    ino_path,
    build_path,
    libraries
) -> CompletedProcess:
    args = [
        'arduino-cli', 'compile', ino_path,
        '--optimize-for-debug',
        '--build-path', build_path,
        '--warnings', 'all',
        '-b', _arduino_fqbn(),
        '--libraries', libraries
    ]

    if config.verbose > 0:
        args.append('-v')

    return run(args)


def core_install(core: str) -> CompletedProcess:
    return run([_arduino_cli, 'core', 'install', core])


def _arduino_fqbn() -> str:
    core, board = itemgetter('core', 'board')(asdict(planer_config.arduino))

    return f'{core}:{board}'
