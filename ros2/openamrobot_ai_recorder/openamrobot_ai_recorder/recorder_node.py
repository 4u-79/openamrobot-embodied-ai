"""
Episode recorder skeleton.

The capture topic contract (C9) is proposed in openamrobot-interfaces and not yet approved, so
this node only validates and reports its configuration. It creates no subscriptions and writes
no data. Recording stays disabled until the capture topic contract is approved.
"""

import re
import sys

from rcl_interfaces.msg import ParameterDescriptor
import rclpy
from rclpy.exceptions import ParameterUninitializedException
from rclpy.node import Node
from rclpy.parameter import Parameter

RECORDING_ENABLED = False

COMMIT_SHA_RE = re.compile(r'^[0-9a-f]{40}$')
# <owner>/<repository>/<path>@<40 hex commit SHA>
SCHEMA_REF_RE = re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/[^@\s]+@[0-9a-f]{40}$')

PENDING_MESSAGE = 'capture topic wiring pending interface approval'


def validate_config(capture_topics, interfaces_commit, c9_schema_ref):
    """Return a list of configuration errors; an empty list means the configuration is valid."""
    errors = []
    if not COMMIT_SHA_RE.match(interfaces_commit):
        errors.append(
            'interfaces_commit must be a 40 character lowercase hex commit SHA of '
            f'openamrobot-interfaces, got {interfaces_commit!r}')
    if not SCHEMA_REF_RE.match(c9_schema_ref):
        errors.append(
            'c9_schema_ref must have the form <owner>/<repository>/<path>@<commit SHA>, '
            f'got {c9_schema_ref!r}')
    if capture_topics:
        errors.append(
            'capture_topics must stay empty until the C9 capture topic contract is approved, '
            f'got {list(capture_topics)!r}')
    return errors


class RecorderNode(Node):
    """Validates configuration, reports provenance and records nothing."""

    def __init__(self, **kwargs):
        super().__init__('openamrobot_ai_recorder', **kwargs)
        read_only = ParameterDescriptor(read_only=True)
        self.declare_parameter('capture_topics', Parameter.Type.STRING_ARRAY, read_only)
        self.declare_parameter('interfaces_commit', '', read_only)
        self.declare_parameter('c9_schema_ref', '', read_only)

        try:
            capture_topics = self.get_parameter('capture_topics').value or []
        except ParameterUninitializedException:
            # An unset string array is the default: an empty list of capture topics.
            capture_topics = []
        self.interfaces_commit = self.get_parameter('interfaces_commit').value
        self.c9_schema_ref = self.get_parameter('c9_schema_ref').value
        self.capture_topics = list(capture_topics)

        self.config_errors = validate_config(
            self.capture_topics, self.interfaces_commit, self.c9_schema_ref)

    def report(self):
        """Log configuration status. Return True when the configuration is valid."""
        logger = self.get_logger()
        if self.config_errors:
            for error in self.config_errors:
                logger.error(f'invalid configuration: {error}')
            return False
        logger.info(f'interfaces commit: {self.interfaces_commit}')
        logger.info(f'C9 schema reference: {self.c9_schema_ref}')
        logger.info(PENDING_MESSAGE)
        logger.info('recording disabled; no data will be written')
        return True


def main(args=None):
    rclpy.init(args=args)
    node = RecorderNode()
    exit_code = 0
    try:
        if node.report():
            rclpy.spin(node)
        else:
            exit_code = 1
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
