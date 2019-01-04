"""Class to hold all media player accessories."""
import logging

from pyhap.const import CATEGORY_SWITCH

from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_SUPPORTED_FEATURES,
    SERVICE_MEDIA_PAUSE, SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_STOP, SERVICE_TURN_OFF, SERVICE_TURN_ON, SERVICE_VOLUME_MUTE,
    STATE_OFF, STATE_PLAYING, STATE_UNKNOWN)
from homeassistant.components.vacuum import (
    DOMAIN,
    ATTR_BATTERY_ICON,
    ATTR_CLEANED_AREA,
    ATTR_FAN_SPEED,
    ATTR_FAN_SPEED_LIST,
    ATTR_PARAMS,
    ATTR_STATUS,

    SERVICE_CLEAN_SPOT,
    SERVICE_LOCATE,
    SERVICE_RETURN_TO_BASE,
    SERVICE_SEND_COMMAND,
    SERVICE_SET_FAN_SPEED,
    SERVICE_START_PAUSE,
    SERVICE_START,
    SERVICE_PAUSE,
    SERVICE_STOP,
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_RETURNING,
    STATE_ERROR,
    
    SUPPORT_BATTERY, SUPPORT_PAUSE, SUPPORT_RETURN_HOME,
    SUPPORT_STATE, SUPPORT_STOP, SUPPORT_START, SUPPORT_MAP, 
    SUPPORT_LOCATE, SUPPORT_CLEAN_SPOT, SUPPORT_SEND_COMMAND,
    
    )

from . import TYPES
from .accessories import HomeAccessory
from .const import (
    CHAR_NAME, CHAR_ON, FEATURE_CLEAN_RETURN, FEATURE_TOGGLE_TIMER, SERV_SWITCH)

_LOGGER = logging.getLogger(__name__)

MODE_FRIENDLY_NAME = {FEATURE_CLEAN_RETURN: 'Clean',
                      FEATURE_TOGGLE_TIMER: 'Timer',}


@TYPES.register('Vacuum')
class Vacuum(HomeAccessory):
    """Generate a Vacuum accessory."""

    def __init__(self, *args):
        """Initialize a Switch accessory object."""
        super().__init__(*args, category=CATEGORY_SWITCH)
        
        features = self.hass.states.get(self.entity_id) \
            .attributes.get(ATTR_SUPPORTED_FEATURES)
        
        self._flag = {FEATURE_CLEAN_RETURN: False, FEATURE_TOGGLE_TIMER: False}
        self.chars = {FEATURE_CLEAN_RETURN: None, FEATURE_TOGGLE_TIMER: None}

        # todo: find out how to access the device attributes here
        # (maybe via config?)
        
        if features & SUPPORT_RETURN_HOME or features & SUPPORT_CLEAN_SPOT:
            name = self.generate_service_name(FEATURE_CLEAN_RETURN)
            serv_clean_return = self.add_preload_service(SERV_SWITCH, CHAR_NAME)
            serv_clean_return.configure_char(CHAR_NAME, value=name)
            self.chars[FEATURE_CLEAN_RETURN] = serv_clean_return.configure_char(
                CHAR_ON, value=False, setter_callback=self.set_clean_return)

        if features & SUPPORT_START or features & SUPPORT_STOP:
            name = self.generate_service_name(FEATURE_TOGGLE_TIMER)
            serv_toggle_timer = self.add_preload_service(SERV_SWITCH, CHAR_NAME)
            serv_toggle_timer.configure_char(CHAR_NAME, value=name)
            self.chars[FEATURE_TOGGLE_TIMER] = serv_toggle_timer.configure_char(
                CHAR_ON, value=False, setter_callback=self.set_toggle_timer)

    def generate_service_name(self, mode):
        """Generate name for individual service."""
        return '{} {}'.format(self.display_name, MODE_FRIENDLY_NAME[mode])

    def set_clean_return(self, value):
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug('%s: Set switch state for "clean_return" to %s',
                      self.entity_id, value)
        self._flag[FEATURE_CLEAN_RETURN] = True
        service = SERVICE_CLEAN_SPOT if value else SERVICE_RETURN_TO_BASE
        params = {ATTR_ENTITY_ID: self.entity_id}
        self.call_service(DOMAIN, service, params)

    def set_toggle_timer(self, value):
        """Move switch state to value if call came from HomeKit."""
        _LOGGER.debug('%s: Set switch state for "toggle_timer" to %s',
                      self.entity_id, value)
        self._flag[FEATURE_TOGGLE_TIMER] = True
        service = SERVICE_START if value else SERVICE_STOP
        params = {ATTR_ENTITY_ID: self.entity_id}
        self.call_service(DOMAIN, service, params)

    def update_state(self, new_state):
        """Update switch state after state changed."""
        current_state = new_state.state

        if self.chars[FEATURE_CLEAN_RETURN]:
            hk_state = current_state == STATE_CLEANING
            if not self._flag[FEATURE_CLEAN_RETURN]:
                _LOGGER.debug('%s: Set current state for "clean_return" to %s',
                              self.entity_id, hk_state)
                self.chars[FEATURE_CLEAN_RETURN].set_value(hk_state)
            self._flag[FEATURE_CLEAN_RETURN] = False

        if self.chars[FEATURE_TOGGLE_TIMER]:
            specified = current_state in (STATE_CLEANING, STATE_DOCKED, STATE_ERROR, STATE_PAUSED)
            if specified:
                hk_state = current_state != STATE_PAUSED
                if not self._flag[FEATURE_TOGGLE_TIMER]:
                    _LOGGER.debug('%s: Set current state for "toggle_timer" to %s',
                                  self.entity_id, hk_state)
                    self.chars[FEATURE_TOGGLE_TIMER].set_value(hk_state)
                self._flag[FEATURE_TOGGLE_TIMER] = False
