"""Segment display on the FAST platform."""

from typing import List

from mpf.core.utility_functions import Util
from mpf.core.rgb_color import RGBColor
from mpf.devices.segment_display.segment_display_text import ColoredSegmentDisplayText

from mpf.platforms.interfaces.segment_display_platform_interface \
    import SegmentDisplayPlatformInterface, FlashingType


class FASTSegmentDisplay(SegmentDisplayPlatformInterface):

    """FAST segment display."""

    __slots__ = ["serial", "hex_id"]

    def __init__(self, index, communicator):
        """Initialise alpha numeric display."""
        super().__init__(index)
        self.serial = communicator
        self.hex_id = Util.int_to_hex_string(index * 7)

    def set_text(self, text: ColoredSegmentDisplayText, flashing: FlashingType, flash_mask: str) -> None:
        """Set digits to display."""
        del flashing
        del flash_mask
        colors = text.get_colors()
        self.serial.send(('PA:{},{}').format(
            self.hex_id, text[0:7]))
        if colors:
            self._set_color(colors)

    def _set_color(self, colors: List[RGBColor]) -> None:
        """Set display color."""
        self.serial.platform.info_log("Color: {}".format(colors))
        if len(colors) == 1:
            colors = (RGBColor(colors[0]).hex + ',') * 7
        else:
            colors = ','.join([RGBColor(color).hex for color in colors])
        self.serial.send(('PC:{},{}').format(
            self.hex_id, colors))
