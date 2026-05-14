"""Simulation of a real-time automotive system with periodic and event-driven tasks."""

import heapq
from collections import defaultdict

from shared_log import SharedExecutionLog

SIMULATION_TIME_MS = 400

runnables = {
    'RadarCapture': {
        'criticality': 1,
        'affinity': 0,
        'period': 75,
        'execution_time': 2,
        'type': 'periodic',
        'deps': []
    },
    'CameraCapture': {
        'criticality': 0,
        'affinity': 0,
        'period': 50,
        'execution_time': 7,
        'type': 'periodic',
        'deps': []
    },
    'SensorFusion': {
        'criticality': 1,
        'affinity': 1,
        'execution_time': 6,
        'type': 'event',
        'deps': ['RadarCapture', 'CameraCapture'],
    },
    'ObjectDetection': {
        'criticality': 1,
        'affinity': 1,
        'execution_time': 15,
        'type': 'event',
        'deps': ['SensorFusion'],
    },
    'TrajectoryPrediction': {
        'criticality': 1,
        'affinity': 1,
        'execution_time': 8,
        'type': 'event',
        'deps': ['ObjectDetection'],
    },
    'CollisionRiskAssessment': {
        'criticality': 2,
        'affinity': 1,
        'execution_time': 3,
        'type': 'event',
        'deps': ['TrajectoryPrediction'],
    },
    'EmergencyBrakeDecision': {
        'criticality': 2,
        'affinity': 1,
        'execution_time': 2,
        'type': 'event',
        'deps': ['CollisionRiskAssessment'],
    },
    'ActuatorControl': {
        'criticality': 2,
        'affinity': 0,
        'execution_time': 1,
        'type': 'event',
        'deps': ['EmergencyBrakeDecision'],
    },
    'LaneMarkingDetection': {
        'criticality': 1,
        'affinity': 1,
        'execution_time': 6,
        'type': 'event',
        'deps': ['CameraCapture'],
    },
    'VehiclePositionEstimation': {
        'criticality': 1,
        'affinity': 1,
        'execution_time': 4,
        'type': 'event',
        'deps': ['LaneMarkingDetection'],
    },
    'LaneDepartureWarning': {
        'criticality': 1,
        'affinity': 1,
        'execution_time': 2,
        'type': 'event',
        'deps': ['VehiclePositionEstimation'],
    },
    'SteeringAngleCalculation': {
        'criticality': 1,
        'affinity': 1,
        'execution_time': 2,
        'type': 'event',
        'deps': ['VehiclePositionEstimation'],
    },
    'SteeringActuatorControl': {
        'criticality': 2,
        'affinity': 0,
        'execution_time': 1,
        'type': 'event',
        'deps': ['LaneDepartureWarning', 'SteeringAngleCalculation'],
    },
}

event_queue = []
heapq.heapify(event_queue)

last_output = defaultdict(lambda: (-1, -1))
execution_log = SharedExecutionLog()
task_instance_counter = defaultdict(int)
dependency_instance = defaultdict(lambda: defaultdict(int))
completed_instances = defaultdict(int)
event_task_instance_counter = defaultdict(int)

CPU_FREE_TIME = 0


def schedule_periodic_runnables():
    """Schedule all periodic runnables up to the simulation time limit,
    ensuring sequential execution."""
    for name, props in runnables.items():
        if props['type'] == 'periodic':
            time = 0
            counter = 0
            while time <= SIMULATION_TIME_MS:
                heapq.heappush(event_queue, (time,  name,
                               props['execution_time'], counter))
                time += props['period']
                counter += 1


def is_dependencies_ready(runnable, current_instance):
    """Check if all dependencies of a runnable have completed by the current time."""
    deps = runnables[runnable].get('deps', [])
    return all(completed_instances[dep] > current_instance for dep in deps)


def schedule_event_runnables(triggered, current_time):
    """Schedule all event-based tasks that are triggered by the given events."""
    for name, props in runnables.items():
        if props['type'] != 'event':
            continue

        if not set(props.get('deps', [])) & set(triggered):
            continue

        available_instances = [completed_instances[dep] for dep in props['deps']
                               ]

        min_completed = min(available_instances)

        current_count = event_task_instance_counter[name]

        if min_completed > current_count:
            current_instance = current_count

            total_delay = sum(exec_time for sched_time, _, exec_time, _ in event_queue
                              if sched_time < current_time)
            heapq.heappush(event_queue, (current_time + total_delay, name,
                                         props['execution_time'], current_instance))

            event_task_instance_counter[name] += 1

            for dep in props['deps']:
                dependency_instance[name][dep] = completed_instances[dep] - 1


schedule_periodic_runnables()

while event_queue and CPU_FREE_TIME < SIMULATION_TIME_MS:
    scheduled_time,  task, execution_time, instance = heapq.heappop(
        event_queue)

    actual_start_time = max(CPU_FREE_TIME, scheduled_time)
    finish_time = actual_start_time + execution_time
    CPU_FREE_TIME = finish_time

    last_output[task] = (finish_time, instance)
    completed_instances[task] = instance + 1
    execution_log.append((actual_start_time, finish_time,
                          task, instance, runnables[task]['affinity']))

    schedule_event_runnables([task], finish_time)

print('Execution Log (start → end ms):')
for start, end, task, instance, _ in execution_log.get_log():
    print(f'[{start:4} → {end:4}] ms : {task} (Instance {instance})')
