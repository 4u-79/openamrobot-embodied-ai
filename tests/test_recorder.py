"""The recorder starts, reports its provenance pins and writes no data."""

import os
import signal
import subprocess
import sys
import time

from ament_index_python.packages import get_package_prefix, get_package_share_directory
from openamrobot_ai_recorder.recorder_node import (
    PENDING_MESSAGE, RecorderNode, RECORDING_ENABLED, validate_config)
from rclpy.executors import SingleThreadedExecutor
from rclpy.parameter import Parameter

SHA = '87ab8a936c97ab55ee74b8988ca3d7659160ea6a'
SCHEMA_REF = (
    f'openAMRobot/openamrobot-interfaces/schemas/json/c9-lerobot-dataset.schema.json@{SHA}')
DEFAULT_TOPICS = {'/rosout', '/parameter_events'}
# The installed executable, as `ros2 run openamrobot_ai_recorder recorder_node` would start it.
RECORDER_CMD = [sys.executable, os.path.join(
    get_package_prefix('openamrobot_ai_recorder'), 'lib', 'openamrobot_ai_recorder',
    'recorder_node')]


def test_recording_is_disabled():
    assert RECORDING_ENABLED is False


def test_validate_config_accepts_pins_and_empty_capture_topics():
    assert validate_config([], SHA, SCHEMA_REF) == []


def test_validate_config_rejects_bad_pins_and_capture_topics():
    errors = validate_config(['/camera/image'], 'main', 'c9-lerobot-dataset.schema.json')
    assert len(errors) == 3


def test_recorder_node_creates_no_subscriptions_and_writes_nothing(context, tmp_path,
                                                                   monkeypatch):
    monkeypatch.chdir(tmp_path)
    node = _make_recorder(context)
    try:
        assert node.report() is True
        executor = SingleThreadedExecutor(context=context)
        executor.add_node(node)
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            executor.spin_once(timeout_sec=0.05)
        subscribed = {name for name, _ in node.get_subscriber_names_and_types_by_node(
            node.get_name(), node.get_namespace())}
        published = {name for name, _ in node.get_publisher_names_and_types_by_node(
            node.get_name(), node.get_namespace())}
        assert subscribed <= DEFAULT_TOPICS
        assert published <= DEFAULT_TOPICS
        executor.shutdown()
    finally:
        node.destroy_node()
    assert list(tmp_path.iterdir()) == []


def test_recorder_executable_starts_and_writes_nothing(tmp_path):
    params = os.path.join(
        get_package_share_directory('openamrobot_ai_recorder'), 'config', 'recorder.yaml')
    proc = subprocess.Popen(
        [*RECORDER_CMD, '--ros-args', '--params-file', params],
        cwd=tmp_path, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        env={**os.environ, 'ROS_LOG_DIR': str(tmp_path.parent / 'ros_log')})
    time.sleep(3.0)
    assert proc.poll() is None, 'recorder exited early'
    proc.send_signal(signal.SIGINT)
    output, _ = proc.communicate(timeout=10)
    assert PENDING_MESSAGE in output
    assert SHA in output
    assert SCHEMA_REF in output
    assert list(tmp_path.iterdir()) == []


def test_recorder_executable_rejects_missing_pins(tmp_path):
    result = subprocess.run(
        RECORDER_CMD,
        cwd=tmp_path, capture_output=True, text=True, timeout=30,
        env={**os.environ, 'ROS_LOG_DIR': str(tmp_path.parent / 'ros_log')})
    assert result.returncode != 0
    assert 'invalid configuration' in result.stdout + result.stderr
    assert list(tmp_path.iterdir()) == []


def _make_recorder(context):
    return RecorderNode(context=context, parameter_overrides=[
        Parameter('interfaces_commit', value=SHA),
        Parameter('c9_schema_ref', value=SCHEMA_REF),
    ])
