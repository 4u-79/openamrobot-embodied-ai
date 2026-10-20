from glob import glob

from setuptools import find_packages, setup

package_name = 'openamrobot_ai_recorder'

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
    description='Episode recorder skeleton; recording disabled until C9 topics are approved.',
    license='MIT',
    entry_points={
        'console_scripts': [
            'recorder_node = openamrobot_ai_recorder.recorder_node:main',
        ],
    },
)
