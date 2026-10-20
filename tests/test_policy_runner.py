"""Policy runner safety behavior: activation refusal and fail-safe stops."""

import time

from geometry_msgs.msg import Twist
from openamrobot_policy_runner.policy_runner_node import PolicyRunnerNode
from openamrobot_policy_runner.watchdog import ObservationWatchdog, StopReason
import pytest
from rclpy.executors import SingleThreadedExecutor
from rclpy.lifecycle import TransitionCallbackReturn
from rclpy.node import Node
from rclpy.parameter import Parameter
from std_msgs.msg import Bool, Header

CMD_VEL = '/test/policy_cmd_vel'
STOP_TOPIC = '/test/software_stop'
OBS_TOPIC = '/test/observation'

STOP_PARAMS = {
    'software_stop_topic': STOP_TOPIC,
    'software_stop_type': 'std_msgs/msg/Bool',
    'software_stop_asserted_field': 'data',
}
OBS_PARAMS = {
    'observation_topic': OBS_TOPIC,
    'observation_type': 'std_msgs/msg/Header',
}


class Harness:
    """Runner plus a helper node that publishes the test stop topic and records Twist output."""

    def __init__(self, context, params, publish_stop=True):
        overrides = [Parameter(name, value=value) for name, value in params.items()]
        self.runner = PolicyRunnerNode(context=context, parameter_overrides=overrides)
        self.helper = Node('policy_runner_test_helper', context=context)
        self.twists = []
        self.helper.create_subscription(Twist, CMD_VEL, self.twists.append, 10)
        self.stop_pub = self.helper.create_publisher(Bool, STOP_TOPIC, 10) if publish_stop \
            else None
        self.obs_pub = self.helper.create_publisher(Header, OBS_TOPIC, 10)
        self.stop_asserted = False
        if self.stop_pub is not None:
            self.helper.create_timer(0.05, self._publish_stop)
        self.executor = SingleThreadedExecutor(context=context)
        self.executor.add_node(self.runner)
        self.executor.add_node(self.helper)

    def _publish_stop(self):
        self.stop_pub.publish(Bool(data=self.stop_asserted))

    def spin_for(self, seconds):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self.executor.spin_once(timeout_sec=0.01)

    def spin_until(self, predicate, timeout=10.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return True
            self.executor.spin_once(timeout_sec=0.01)
        return predicate()

    def configure_and_activate(self):
        assert self.runner.trigger_configure() == TransitionCallbackReturn.SUCCESS
        assert self.spin_until(
            lambda: self.runner.count_publishers(STOP_TOPIC) > 0
            and self.helper.count_subscribers(CMD_VEL) > 0)
        # Let a few stop messages arrive so the runner sees the stop released.
        self.spin_for(0.2)
        return self.runner.trigger_activate()

    def close(self):
        self.executor.shutdown()
        self.runner.destroy_node()
        self.helper.destroy_node()


@pytest.fixture
def make_harness(context):
    harnesses = []

    def factory(params, publish_stop=True):
        harness = Harness(context, params, publish_stop)
        harnesses.append(harness)
        return harness

    yield factory
    for harness in harnesses:
        harness.close()


def is_zero(twist):
    return all(v == 0.0 for v in (
        twist.linear.x, twist.linear.y, twist.linear.z,
        twist.angular.x, twist.angular.y, twist.angular.z))


def test_configure_refuses_without_cmd_vel_topic(make_harness):
    harness = make_harness({**STOP_PARAMS, **OBS_PARAMS})
    assert harness.runner.trigger_configure() == TransitionCallbackReturn.FAILURE


def test_configure_refuses_arm_output(make_harness):
    harness = make_harness(
        {'cmd_vel_topic': CMD_VEL, 'arm_output_enabled': True, **STOP_PARAMS, **OBS_PARAMS})
    assert harness.runner.trigger_configure() == TransitionCallbackReturn.FAILURE


def test_refuses_activation_without_stop_configuration(make_harness):
    harness = make_harness({'cmd_vel_topic': CMD_VEL, **OBS_PARAMS})
    assert harness.configure_and_activate() == TransitionCallbackReturn.FAILURE
    assert harness.runner.motion_active is False
    assert harness.twists == []


def test_refuses_activation_when_stop_topic_unavailable(make_harness):
    harness = make_harness({'cmd_vel_topic': CMD_VEL, **STOP_PARAMS, **OBS_PARAMS},
                           publish_stop=False)
    assert harness.runner.trigger_configure() == TransitionCallbackReturn.SUCCESS
    harness.spin_for(0.5)
    assert harness.runner.trigger_activate() == TransitionCallbackReturn.FAILURE
    assert harness.runner.motion_active is False


def test_refuses_activation_while_stop_asserted(make_harness):
    harness = make_harness({'cmd_vel_topic': CMD_VEL, **STOP_PARAMS, **OBS_PARAMS})
    harness.stop_asserted = True
    assert harness.configure_and_activate() == TransitionCallbackReturn.FAILURE
    assert harness.runner.motion_active is False


def test_publishes_zero_twist_and_deactivates_on_stale_observation(make_harness):
    harness = make_harness({'cmd_vel_topic': CMD_VEL, **STOP_PARAMS, **OBS_PARAMS})
    assert harness.configure_and_activate() == TransitionCallbackReturn.SUCCESS
    assert harness.runner.motion_active is True
    assert harness.spin_until(lambda: not harness.runner.motion_active, timeout=2.0)
    assert harness.runner.last_stop_reason == StopReason.STALE_OBSERVATION
    assert harness.spin_until(lambda: len(harness.twists) > 0, timeout=2.0)
    assert all(is_zero(t) for t in harness.twists)


def test_publishes_zero_twist_and_deactivates_on_inference_error(make_harness):
    harness = make_harness(
        {'cmd_vel_topic': CMD_VEL, 'observation_timeout_s': 5.0, **STOP_PARAMS, **OBS_PARAMS})
    assert harness.configure_and_activate() == TransitionCallbackReturn.SUCCESS
    harness.obs_pub.publish(Header())
    assert harness.spin_until(lambda: not harness.runner.motion_active, timeout=2.0)
    assert harness.runner.last_stop_reason == StopReason.INFERENCE_ERROR
    assert harness.spin_until(lambda: len(harness.twists) > 0, timeout=2.0)
    assert all(is_zero(t) for t in harness.twists)


def test_publishes_zero_twist_and_deactivates_on_software_stop(make_harness):
    harness = make_harness(
        {'cmd_vel_topic': CMD_VEL, 'observation_timeout_s': 5.0, **STOP_PARAMS, **OBS_PARAMS})
    assert harness.configure_and_activate() == TransitionCallbackReturn.SUCCESS
    harness.stop_asserted = True
    assert harness.spin_until(lambda: not harness.runner.motion_active, timeout=2.0)
    assert harness.runner.last_stop_reason == StopReason.SOFTWARE_STOP_ASSERTED
    assert harness.spin_until(lambda: len(harness.twists) > 0, timeout=2.0)
    assert all(is_zero(t) for t in harness.twists)


def test_watchdog_staleness():
    watchdog = ObservationWatchdog(0.2)
    assert watchdog.is_stale(100.0) is False
    watchdog.arm(10.0)
    assert watchdog.is_stale(10.1) is False
    assert watchdog.is_stale(10.3) is True
    watchdog.observe(10.25)
    assert watchdog.is_stale(10.3) is False
    watchdog.disarm()
    assert watchdog.is_stale(20.0) is False


def test_watchdog_rejects_non_positive_timeout():
    with pytest.raises(ValueError):
        ObservationWatchdog(0.0)
