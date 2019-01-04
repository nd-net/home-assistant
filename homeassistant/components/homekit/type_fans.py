"""Class to hold all light accessories."""
import logging

from pyhap.const import CATEGORY_FAN

from homeassistant.components.fan import (
    ATTR_DIRECTION, ATTR_OSCILLATING, ATTR_SPEED, ATTR_SPEED_LIST,
    DIRECTION_FORWARD, DIRECTION_REVERSE,
    DOMAIN, SERVICE_OSCILLATE, SERVICE_SET_DIRECTION, SERVICE_SET_SPEED,
    SUPPORT_DIRECTION, SUPPORT_OSCILLATE, SUPPORT_SET_SPEED)
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_SUPPORTED_FEATURES, SERVICE_TURN_OFF,
    SERVICE_TURN_ON, STATE_OFF, STATE_ON)

from . import TYPES
from .accessories import HomeAccessory
from .const import (
    CHAR_ACTIVE, CHAR_ROTATION_DIRECTION, CHAR_ROTATION_SPEED, CHAR_SWING_MODE, SERV_FANV2)

_LOGGER = logging.getLogger(__name__)


@TYPES.register('Fan')
class Fan(HomeAccessory):
    """Generate a Fan accessory for a fan entity.

    Currently supports: state, speed, oscillate, direction.
    """

    def __init__(self, *args):
        """Initialize a new Light accessory object."""
        super().__init__(*args, category=CATEGORY_FAN)
        self._flag = {CHAR_ACTIVE: False,
                      CHAR_ROTATION_DIRECTION: False,
                      CHAR_ROTATION_SPEED: False,
                      CHAR_SWING_MODE: False}
        self._state = 0

        chars = []
        features = self.hass.states.get(self.entity_id) \
            .attributes.get(ATTR_SUPPORTED_FEATURES)
        if features & SUPPORT_DIRECTION:
            chars.append(CHAR_ROTATION_DIRECTION)
        if features & SUPPORT_OSCILLATE:
            chars.append(CHAR_SWING_MODE)
        if features & SUPPORT_SET_SPEED:
            chars.append(CHAR_ROTATION_SPEED)

        serv_fan = self.add_preload_service(SERV_FANV2, chars)
        self.char_active = serv_fan.configure_char(
            CHAR_ACTIVE, value=0, setter_callback=self.set_state)

        self.char_direction = None
        self.char_speed = None
        self.char_swing = None

        if CHAR_ROTATION_DIRECTION in chars:
            self.char_direction = serv_fan.configure_char(
                CHAR_ROTATION_DIRECTION, value=0,
                setter_callback=self.set_direction)

        if CHAR_ROTATION_SPEED in chars:
            self.char_speed = serv_fan.configure_char(
                CHAR_ROTATION_SPEED, value=0, setter_callback=self.set_speed)

        if CHAR_SWING_MODE in chars:
            self.char_swing = serv_fan.configure_char(
                CHAR_SWING_MODE, value=0, setter_callback=self.set_oscillating)

    def set_state(self, value):
        """Set state if call came from HomeKit."""
        _LOGGER.debug('%s: Set state to %d', self.entity_id, value)
        self._flag[CHAR_ACTIVE] = True
        service = SERVICE_TURN_ON if value == 1 else SERVICE_TURN_OFF
        params = {ATTR_ENTITY_ID: self.entity_id}
        self.call_service(DOMAIN, service, params)

    def set_direction(self, value):
        """Set state if call came from HomeKit."""
        _LOGGER.debug('%s: Set direction to %d', self.entity_id, value)
        self._flag[CHAR_ROTATION_DIRECTION] = True
        direction = DIRECTION_REVERSE if value == 1 else DIRECTION_FORWARD
        params = {ATTR_ENTITY_ID: self.entity_id, ATTR_DIRECTION: direction}
        self.call_service(DOMAIN, SERVICE_SET_DIRECTION, params, direction)

    def set_oscillating(self, value):
        """Set state if call came from HomeKit."""
        _LOGGER.debug('%s: Set oscillating to %d', self.entity_id, value)
        self._flag[CHAR_SWING_MODE] = True
        oscillating = value == 1
        params = {ATTR_ENTITY_ID: self.entity_id,
                  ATTR_OSCILLATING: oscillating}
        self.call_service(DOMAIN, SERVICE_OSCILLATE, params, oscillating)

    def speed_from_percentage(self, percentage):
        """Convert a value from 0-100 to a value in the speed list."""
        speed_list = self.hass.states.get(self.entity_id) \
            .attributes.get(ATTR_SPEED_LIST)
        if not speed_list:
            return None
        if percentage >= 100:
            return speed_list[-1]
        if percentage <= 0:
            return speed_list[0]
        index = int(percentage / 100 * len(speed_list))
        return speed_list[index]

    def percentage_from_speed(self, speed):
        speed_list = self.hass.states.get(self.entity_id) \
            .attributes.get(ATTR_SPEED_LIST)
        if not speed_list:
            return None
        try:
            index = speed_list.index(speed)
            # By dividing by len(speed_list) the following
            # desired attributes hold true:
            # 0% is equal to "off"
            # * index = 0 => first step above 0%
            # * index = len(speed_list) - 1 => 100 %
            # * all other indices are equally distributed
            return (index + 1) * 100 / len(speed_list)
        except ValueError:
            # speed_list does not contain the speed
            return None

    def set_speed(self, value):
        """Set state if call came from HomeKit."""
        _LOGGER.debug('%s: Set speed to %d', self.entity_id, value)
        # special case for 0: 
        if value <= 0:
            self.set_state(0)
            return
        
        self._flag[CHAR_ROTATION_SPEED] = True
        speed = self.speed_from_percentage(value)
        params = {ATTR_ENTITY_ID: self.entity_id,
                  ATTR_SPEED: speed}
        self.call_service(DOMAIN, SERVICE_SET_SPEED, params, speed)

    def update_state(self, new_state):
        """Update fan after state change."""
        # Handle State
        state = new_state.state
        if state in (STATE_ON, STATE_OFF):
            self._state = 1 if state == STATE_ON else 0
            if not self._flag[CHAR_ACTIVE] and \
                    self.char_active.value != self._state:
                self.char_active.set_value(self._state)
            self._flag[CHAR_ACTIVE] = False

        # Handle Direction
        if self.char_direction is not None:
            direction = new_state.attributes.get(ATTR_DIRECTION)
            if not self._flag[CHAR_ROTATION_DIRECTION] and \
                    direction in (DIRECTION_FORWARD, DIRECTION_REVERSE):
                hk_direction = 1 if direction == DIRECTION_REVERSE else 0
                if self.char_direction.value != hk_direction:
                    self.char_direction.set_value(hk_direction)
            self._flag[CHAR_ROTATION_DIRECTION] = False

        # Handle Speed
        if self.char_speed is not None:
            speed = new_state.attributes.get(ATTR_SPEED)
            hk_speed_value = self.percentage_from_speed(speed) \
                    if state == STATE_ON else 0
            # update the speed even if it had been set via HomeKit
            # so that it snaps to the correct percentage
            if hk_speed_value is not None and \
                    self.char_speed.value != hk_speed_value:
                self.char_speed.set_value(hk_speed_value)
            self._flag[CHAR_ROTATION_SPEED] = False

        # Handle Oscillating
        if self.char_swing is not None:
            oscillating = new_state.attributes.get(ATTR_OSCILLATING)
            if not self._flag[CHAR_SWING_MODE] and \
                    oscillating in (True, False):
                hk_oscillating = 1 if oscillating else 0
                if self.char_swing.value != hk_oscillating:
                    self.char_swing.set_value(hk_oscillating)
            self._flag[CHAR_SWING_MODE] = False

