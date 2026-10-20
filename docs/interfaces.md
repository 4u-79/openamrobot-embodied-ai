# Interfaces

This repository defines no messages, services, actions or interface schemas. It consumes them
from other OpenAMRobot repositories and references them by repository, path and commit SHA.

## Consumed

| What | From | How it is referenced |
| --- | --- | --- |
| ROS 2 interface packages built in CI | `openAMRobot/openamrobot-interfaces` | Checked out in the `ros2` CI job at commit `87ab8a936c97ab55ee74b8988ca3d7659160ea6a`, never its moving `main` branch. It currently provides `openamr_nav_msgs` and `openamr_ui_msgs`; the skeletons in this repository use neither yet, so no package here declares a dependency on them. |
| C9 LeRobotDataset contract (proposed) | `openAMRobot/openamrobot-interfaces` | `schemas/json/c9-lerobot-dataset.schema.json` and `docs/c9-lerobot-dataset-contract.md` at commit `87ab8a936c97ab55ee74b8988ca3d7659160ea6a`. The recorder logs this reference through its `c9_schema_ref` parameter and registry entries record it in `c9_schema_ref`. The schema is not copied here. |
| `geometry_msgs/Twist` | ROS 2 Jazzy | Base command output of the policy runner, published on `cmd_vel_topic` as a `twist_mux` input. |
| Base command arbitration | `openAMRobot/openamr-platform-sw` (`twist_mux`) | The policy runner publishes to an approved `twist_mux` input only. It performs no arbitration itself. |

## Pending

### C9 capture topics

C9 is a proposed schema in `openamrobot-interfaces`, not an approved set of capture topics. No
capture topic names or message types are defined or assumed here. The recorder keeps
`capture_topics` empty, logs "capture topic wiring pending interface approval" and writes no
data. Recording stays disabled until the capture topic contract is approved.

### Software stop (openamr-platform-sw PR #35)

The software stop interface is being defined in `openamr-platform-sw` PR #35. This repository
does not define a replacement. The policy runner takes the stop topic
(`software_stop_topic`), message type (`software_stop_type`) and the boolean field that means
"stop asserted" (`software_stop_asserted_field`) as parameters with no default. It refuses motion
activation when any of them is unset, when the type cannot be resolved, or when the topic has
no publisher of that type. While active, it publishes a zero Twist and deactivates when the stop
is asserted or its publisher disappears.

### Arm command arbitration (openamrobot-manipulation)

How arm commands from a policy are arbitrated is not defined yet; it belongs to
`openamrobot-manipulation`. The policy runner has no arm output. `arm_output_enabled` defaults
to `false` and the runner refuses to configure when it is `true`.

### Observation topics

The policy runner observation input (`observation_topic`, `observation_type`) has no default.
It will follow the C9 capture topics once they are approved.
