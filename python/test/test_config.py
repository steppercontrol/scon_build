from planer_build.configure import ConfigH

from . import data_dir


class TestConfig:
    def setup_method(self) -> None:
        self.config = ConfigH.from_file(f'{data_dir}/config.toml')

    def test_config(self):
        config = self.config
        arduino = config.arduino

        assert arduino.core == "arduino:renesas_uno"
        assert arduino.version == "1.2.0"
        assert arduino.board == "minima"
        assert arduino.port == "/dev/ttyACM0"

    def test_config_str(self):
        config = self.config

        toml_ref = (
            '''[arduino]
core = "arduino:renesas_uno"
version = "1.2.0"
board = "minima"
port = "/dev/ttyACM0"

[keypad]
row_pins = [3, 2, 14, 15]
column_pins = [16, 17, 18, 19]
# TODO not yet implemented
driver = "digital"  # "digital" | "analog"

[motor]
steps_per_revolution = 2048
pins = [8, 10, 9, 12]

[display]
controller = "PCD8544"  # "PCD8544" | "SSD1306"
buffer_mode = "1Page"  # "1Page" | "2Page" | "Full"
clock = 13
data = 11
cs = 6
dc = 4
reset = 5
backlight = 7
'''
        )

        # print(config.toml().as_string())

        assert config.toml().as_string() == toml_ref
