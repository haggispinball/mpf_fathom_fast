"""Arduino serial communicator"""
import asyncio
import logging
from typing import Dict, Set
import PyCmdMessenger

from mpf.core.platform import DriverPlatform, DriverConfig

from mpf.core.platform import BasePlatform
from mpf.platforms.base_serial_communicator import BaseSerialCommunicator

class ArduinoHardwarePlatform(BasePlatform):
    def __init__(self, machine):
        super().__init__(machine)
        self.log = logging.getLogger("Arduino")
        self.log.debug("Configuring Arduino hardware.")

        self.dmd_connection = None
        self.net_connection = None
        self.rgb_connection = None
        self.serial_connections = set()         # type: Set[ArduinoSerialCommunicator]
        self.fast_leds = {}
        self.flag_led_tick_registered = False
        self.config = None
        self.machine_type = None
        self.hw_switch_data = None


    @asyncio.coroutine
    def initialize(self):
        """Initialise platform."""
        self.config = self.machine.config['arduino']
        self.machine.config_validator.validate_config("arduino", self.config)

        if self.config['debug']:
            self.debug = True

        self.machine_type = (
            self.machine.config['hardware']['driverboards'].lower())

        yield from self._connect_to_hardware()

        self.machine.events.add_handler(
            event="arduino_test",
            handler=self._send_something,
            priority=1)

        # self.machine.clock.schedule_interval(self._update_watchdog, self.config['watchdog'] / 2000)

    def stop(self):
        """Stop platform and close connections."""
        for connection in self.serial_connections:
            # connection.writer.write(b'BL:AA55\r')   # reset CPU using bootloader
            connection.stop()

        self.serial_connections = set()

    def _send_something(self, **kwargs):
        self.log.info("GONNA SEND SOMETHING!!! {}".format(self.serial_connections))
        for comm in self.serial_connections:
            comm.send("BUTTFACE")


    def configure_driver(self, config: DriverConfig, number: str, platform_settings: dict):
        pass

    def configure_switch(self, config: DriverConfig, number: str, platform_settings: dict):
        pass


    def validate_coil_section(self, driver, config):
        return config

    def __repr__(self):
        """Return str representation."""
        return '<Platform.Arduino>'

    @asyncio.coroutine
    def _connect_to_hardware(self):
        """Connect to each port from the config.

        This process will cause the connection threads to figure out which processor they've connected to
        and to register themselves.
        """
        for port in self.config['ports']:
            comm = ArduinoSerialCommunicator(platform=self, port=port,
                                          baud=self.config['baud'])
            yield from comm.connect()
            self.serial_connections.add(comm)

class ArduinoSerialCommunicator(BaseSerialCommunicator):

    def __init__(self, platform, port, baud):

        # port = "/dev/cu.usbmodem1421"
        commands = [
            ["draw_text", "s"],
            ["error", "s"]
        ]

        self.remote_processor = None
        self.remote_model = None
        self.remote_firmware = 0.0
        self.max_messages_in_flight = 10
        self.messages_in_flight = 0
        self.ignored_messages_in_flight = {b'-N', b'/N', b'/L', b'-L'}

        self.send_ready = asyncio.Event(loop=platform.machine.clock.loop)
        self.send_ready.set()
        self.write_task = None

        self.received_msg = b''

        self.send_queue = asyncio.Queue(loop=platform.machine.clock.loop)

        super().__init__(platform, port, baud)

        arduino = PyCmdMessenger.ArduinoBoard(port, baud_rate=baud)
        self._c = PyCmdMessenger.CmdMessenger(arduino, commands)
        self.platform.log.info("Connected to Arduino!")

    def stop(self):
        """Stop and shut down this serial connection."""
        if self.write_task:
            self.write_task.cancel()
        super().stop()


    def send(self, msg):
        """Send a message to the remote processor over the serial connection.

        Args:
            msg: String of the message you want to send. THe <CR> character will
                be added automatically.

        """
        self.platform.log.info(" - SerialCommunicator is ready to send '{}'".format(msg))
        self._c.send("draw_text", msg)
        # self.send_queue.put_nowait(msg)

    def _send(self, msg):
        debug = self.platform.config['debug']
        if self.dmd:
            self.writer.write(b'BM:' + msg)
            if debug:
                self.platform.log.debug("Send: %s", "".join(" 0x%02x" % b for b in msg))

        else:
            self.messages_in_flight += 1
            if self.messages_in_flight > self.max_messages_in_flight:
                self.send_ready.clear()

                self.log.debug("Enabling Flow Control for %s connection. "
                               "Messages in flight: %s, Max setting: %s",
                               self.remote_processor,
                               self.messages_in_flight,
                               self.max_messages_in_flight)

            self.writer.write(msg.encode() + b'\r')
            if debug and msg[0:2] != "WD":
                self.platform.log.debug("Send: %s", msg)


    @asyncio.coroutine
    def _identify_connection(self):
        self.platform.log.warn("Need to implement connection for _identify_connection")

    @asyncio.coroutine
    def _socket_writer(self):
        while True:
            msg = yield from self.send_queue.get()
            try:
                yield from asyncio.wait_for(self.send_ready.wait(), 1.0, loop=self.machine.clock.loop)
            except asyncio.TimeoutError:
                self.log.warning("Port %s was blocked for more than 1s. Reseting send queue! If this happens "
                                 "frequently report a bug!", self.port)
                self.messages_in_flight = 0

            self._send(msg)
