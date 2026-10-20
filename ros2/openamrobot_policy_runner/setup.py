from glob import glob

from setuptools import find_packages, setup

package_name = 'openamrobot_policy_runner'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    tests_require=['pytest'],
    maintainer='Botshare LTD',
    maintainer_email='info@botshare.ai',
    description='Policy runner lifecycle node skeleton with a fail-safe watchdog.',
    license='MIT',
    entry_points={
        'console_scripts': [
            'policy_runner_node = openamrobot_policy_runner.policy_runner_node:main',
        ],
    },
)
