"""Shared fixtures for the ROS 2 node tests. Run after sourcing the colcon install space."""

import os
import random

import pytest
import rclpy
from rclpy.context import Context

# Keep test traffic away from other ROS 2 graphs on the same host.
os.environ.setdefault('ROS_DOMAIN_ID', str(random.randint(100, 200)))
os.environ.setdefault('ROS_AUTOMATIC_DISCOVERY_RANGE', 'LOCALHOST')


@pytest.fixture
def context():
    ctx = Context()
    rclpy.init(context=ctx)
    yield ctx
    rclpy.try_shutdown(context=ctx)
