"""ROS independent watchdog and activation checks for the policy runner."""

from enum import Enum


class StopReason(str, Enum):
    """Why the runner published a zero Twist and deactivated."""

    STALE_OBSERVATION = 'stale observation'
    INFERENCE_ERROR = 'inference error'
    SOFTWARE_STOP_ASSERTED = 'software stop asserted'
    SOFTWARE_STOP_UNAVAILABLE = 'software stop topic unavailable'


class ObservationWatchdog:
    """Tracks observation freshness while the runner is active."""

    def __init__(self, timeout_s):
        if timeout_s <= 0.0:
            raise ValueError(f'observation_timeout_s must be positive, got {timeout_s}')
        self.timeout_s = timeout_s
        self._reference_s = None

    def arm(self, now_s):
        """Start watching. Until the first observation, staleness counts from activation."""
        self._reference_s = now_s

    def disarm(self):
        """Stop watching."""
        self._reference_s = None

    def observe(self, now_s):
        """Record the receipt time of an observation."""
        if self._reference_s is not None:
            self._reference_s = now_s

    def is_stale(self, now_s):
        """Return True when armed and no observation arrived within the timeout."""
        if self._reference_s is None:
            return False
        return (now_s - self._reference_s) > self.timeout_s


def motion_activation_errors(
        software_stop_topic, software_stop_type, software_stop_asserted_field,
        observation_topic, observation_type):
    """Return the reasons the runner must refuse motion activation based on parameters alone."""
    errors = []
    if not software_stop_topic:
        errors.append('software_stop_topic is not set')
    if not software_stop_type:
        errors.append('software_stop_type is not set')
    if not software_stop_asserted_field:
        errors.append('software_stop_asserted_field is not set')
    if not observation_topic:
        errors.append('observation_topic is not set')
    if not observation_type:
        errors.append('observation_type is not set')
    return errors
