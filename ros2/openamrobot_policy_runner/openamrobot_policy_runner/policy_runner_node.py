"""
Policy runner lifecycle node skeleton.

Base output is a geometry_msgs/Twist on ``cmd_vel_topic``, intended as a twist_mux input in
openamr-platform-sw. The topic has no default, so the runner never points at the motor driver
by default. Arm output is not implemented.

The software stop interface is still being defined (openamr-platform-sw PR #35). Its topic, type
and asserted field are parameters with no default; the runner refuses motion activation when
they are unset or the topic has no publisher of that type.

While active, the runner publishes a zero Twist and deactivates on a stale observation, an
inference error, an asserted software stop or a lost software stop publisher. It never
downloads model weights.
"""

import sys

from geometry_msgs.msg import Twist
from openamrobot_policy_runner.policy import NoPolicy
from openamrobot_policy_runner.watchdog import (
    motion_activation_errors, ObservationWatchdog, StopReason)
import rclpy
from rclpy.lifecycle import LifecycleNode, TransitionCallbackReturn
from rosidl_runtime_py.utilities import get_message


class PolicyRunnerNode(LifecycleNode):
    """Lifecycle node that runs a policy and fails safe to a zero Twist."""

    def __init__(self, node_name='policy_runner', policy=None, **kwargs):
        super().__init__(node_name, **kwargs)
        self.declare_parameter('cmd_vel_topic', '')
        self.declare_parameter('arm_output_enabled', False)
        self.declare_parameter('software_stop_topic', '')
        self.declare_parameter('software_stop_type', '')
        self.declare_parameter('software_stop_asserted_field', '')
        self.declare_parameter('observation_topic', '')
        self.declare_parameter('observation_type', '')
        self.declare_parameter('observation_timeout_s', 0.2)
        self.declare_parameter('watchdog_period_s', 0.05)

        self.policy = policy if policy is not None else NoPolicy()
        self.motion_active = False
        self.last_stop_reason = None
        # None until the first stop status arrives: unknown counts as not clear (fail closed).
        self.software_stop_asserted = None

        self._cmd_pub = None
        self._stop_sub = None
        self._stop_type = None
        self._stop_field = None
        self._obs_sub = None
        self._timer = None
        self._watchdog = None

    # Lifecycle transitions

    def on_configure(self, state):
        """Create the base output and input subscriptions; refuse arm output."""
        logger = self.get_logger()
        if self.get_parameter('arm_output_enabled').value:
            logger.error('arm output is not implemented; refusing arm_output_enabled=true')
            return TransitionCallbackReturn.FAILURE
        cmd_vel_topic = self.get_parameter('cmd_vel_topic').value
        if not cmd_vel_topic:
            logger.error('cmd_vel_topic is not set; it must name an approved twist_mux input')
            return TransitionCallbackReturn.FAILURE
        try:
            self._watchdog = ObservationWatchdog(
                self.get_parameter('observation_timeout_s').value)
        except ValueError as error:
            logger.error(str(error))
            return TransitionCallbackReturn.FAILURE

        self._cmd_pub = self.create_publisher(Twist, cmd_vel_topic, 10)
        self._create_software_stop_subscription()
        self._create_observation_subscription()
        self._timer = self.create_timer(
            self.get_parameter('watchdog_period_s').value, self._on_watchdog_timer)
        logger.info(f'configured; base output on {self._cmd_pub.topic_name}')
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state):
        """Refuse motion activation unless the software stop interface is available and clear."""
        errors = self._motion_activation_errors()
        if errors:
            for error in errors:
                self.get_logger().error(f'refusing motion activation: {error}')
            return TransitionCallbackReturn.FAILURE
        self.last_stop_reason = None
        self._watchdog.arm(self._now_s())
        self.motion_active = True
        self.get_logger().info('motion activated')
        return super().on_activate(state)

    def on_deactivate(self, state):
        """Publish a zero Twist and stop motion."""
        self._enter_safe_state()
        self.get_logger().info('motion deactivated')
        return super().on_deactivate(state)

    def on_cleanup(self, state):
        """Release publishers, subscriptions and timers."""
        self._enter_safe_state()
        self._destroy_entities()
        return TransitionCallbackReturn.SUCCESS

    def on_shutdown(self, state):
        """Publish a zero Twist and release entities."""
        self._enter_safe_state()
        self._destroy_entities()
        return TransitionCallbackReturn.SUCCESS

    # Inputs

    def _create_software_stop_subscription(self):
        topic = self.get_parameter('software_stop_topic').value
        type_name = self.get_parameter('software_stop_type').value
        field = self.get_parameter('software_stop_asserted_field').value
        if not (topic and type_name and field):
            return
        try:
            msg_type = get_message(type_name)
        except (AttributeError, ModuleNotFoundError, ValueError) as error:
            self.get_logger().error(f'software_stop_type {type_name!r} not found: {error}')
            return
        if msg_type.get_fields_and_field_types().get(field) != 'boolean':
            self.get_logger().error(
                f'software_stop_type {type_name} has no boolean field {field!r}')
            return
        self._stop_type = type_name
        self._stop_field = field
        self._stop_sub = self.create_subscription(msg_type, topic, self._on_software_stop, 10)

    def _create_observation_subscription(self):
        topic = self.get_parameter('observation_topic').value
        type_name = self.get_parameter('observation_type').value
        if not (topic and type_name):
            return
        try:
            msg_type = get_message(type_name)
        except (AttributeError, ModuleNotFoundError, ValueError) as error:
            self.get_logger().error(f'observation_type {type_name!r} not found: {error}')
            return
        self._obs_sub = self.create_subscription(msg_type, topic, self._on_observation, 10)

    def _on_software_stop(self, msg):
        self.software_stop_asserted = bool(getattr(msg, self._stop_field))
        if self.software_stop_asserted:
            self._halt(StopReason.SOFTWARE_STOP_ASSERTED)

    def _on_observation(self, msg):
        if not self.motion_active:
            return
        self._watchdog.observe(self._now_s())
        try:
            command = self.policy.infer(msg)
            if not isinstance(command, Twist):
                raise TypeError(f'policy returned {type(command).__name__}, expected Twist')
        except Exception as error:  # noqa: B902 any inference failure must stop motion
            self.get_logger().error(f'inference error: {error}')
            self._halt(StopReason.INFERENCE_ERROR)
            return
        self._cmd_pub.publish(command)

    def _on_watchdog_timer(self):
        if not self.motion_active:
            return
        if not self._software_stop_available():
            self._halt(StopReason.SOFTWARE_STOP_UNAVAILABLE)
        elif self._watchdog.is_stale(self._now_s()):
            self._halt(StopReason.STALE_OBSERVATION)

    # Safety helpers

    def _motion_activation_errors(self):
        errors = motion_activation_errors(
            self.get_parameter('software_stop_topic').value,
            self.get_parameter('software_stop_type').value,
            self.get_parameter('software_stop_asserted_field').value,
            self.get_parameter('observation_topic').value,
            self.get_parameter('observation_type').value)
        if errors:
            return errors
        if self._stop_sub is None:
            return ['software stop subscription could not be created']
        if self._obs_sub is None:
            return ['observation subscription could not be created']
        if not self._software_stop_available():
            return [f'software stop topic {self._stop_sub.topic_name} has no '
                    f'{self._stop_type} publisher']
        if self.software_stop_asserted is None:
            return ['no software stop status received yet']
        if self.software_stop_asserted:
            return ['software stop is asserted']
        return []

    def _software_stop_available(self):
        if self._stop_sub is None:
            return False
        publishers = self.get_publishers_info_by_topic(self._stop_sub.topic_name)
        return any(info.topic_type == self._stop_type for info in publishers)

    def _halt(self, reason):
        """Publish a zero Twist and deactivate. No effect when motion is not active."""
        if not self.motion_active:
            return
        self.last_stop_reason = reason
        self.get_logger().error(f'stopping motion: {reason.value}')
        self._enter_safe_state()
        self.trigger_deactivate()

    def _enter_safe_state(self):
        was_active = self.motion_active
        self.motion_active = False
        if self._watchdog is not None:
            self._watchdog.disarm()
        if self._cmd_pub is not None and was_active:
            self._cmd_pub.publish(Twist())

    def _destroy_entities(self):
        for sub in (self._stop_sub, self._obs_sub):
            if sub is not None:
                self.destroy_subscription(sub)
        if self._timer is not None:
            self.destroy_timer(self._timer)
        if self._cmd_pub is not None:
            self.destroy_publisher(self._cmd_pub)
        self._cmd_pub = self._stop_sub = self._obs_sub = self._timer = None
        self.software_stop_asserted = None
        self._stop_type = self._stop_field = None
        self.software_stop_asserted = False

    def _now_s(self):
        return self.get_clock().now().nanoseconds * 1e-9


def main(args=None):
    rclpy.init(args=args)
    node = PolicyRunnerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
    return 0


if __name__ == '__main__':
    sys.exit(main())
