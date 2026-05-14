"""Task scheduling simulation with 3 logical CPUs: CPU 0, CPU 1a, CPU 1b."""

import heapq
from collections import defaultdict

from driving_mock import runnables

SIMULATION_TIME_MS = 400

event_queue = []
heapq.heapify(event_queue)

core_time = {
    0: 0,
    '1a': 0,
    '1b': 0
}

execution_log_core = {
    0: [],
    '1a': [],
    '1b': []
}

completed_instances = defaultdict(int)
event_task_instance_counter = defaultdict(int)


def schedule_periodic_runnables():
    """Schedule all periodic runnables up to the simulation time limit."""
    for name, props in runnables.items():
        if props["type"] == "periodic":
            time = 0
            counter = 0
            while time < SIMULATION_TIME_MS:
                heapq.heappush(event_queue, (time, -props["criticality"], name,
                               props["execution_time"], counter))
                time += props["period"]
                counter += 1


def schedule_event_runnables(triggered_tasks, current_time):
    """Schedule event-driven runnables triggered by `triggered_tasks`."""
    for name, props in runnables.items():
        if props["type"] != "event":
            continue

        if not set(props["deps"]) & set(triggered_tasks):
            continue

        if all(completed_instances[dep] > event_task_instance_counter[name]
               for dep in props["deps"]):
            current_instance = event_task_instance_counter[name]
            heapq.heappush(event_queue, (current_time, -props["criticality"],
                                         name, props["execution_time"], current_instance))
            event_task_instance_counter[name] += 1


def assign_core_and_run(planned_time, runnable, runnable_execution_time, current_instance):
    """Determine core and run task."""
    affinity = runnables[runnable]["affinity"]

    if affinity == 0:
        actual_start = max(core_time[0], planned_time)
        finished_time = actual_start + runnable_execution_time
        core_time[0] = finished_time
        execution_log_core[0].append(
            (actual_start, finished_time, runnable, current_instance))
        completed_instances[runnable] = current_instance + 1
        return finished_time

    else:
        cpu_label = '1a' if core_time['1a'] <= core_time['1b'] else '1b'
        actual_start = max(core_time[cpu_label], planned_time)
        finished_time = actual_start + runnable_execution_time
        core_time[cpu_label] = finished_time
        execution_log_core[cpu_label].append(
            (actual_start, finished_time, runnable, current_instance))
        completed_instances[runnable] = current_instance + 1
        return finished_time


schedule_periodic_runnables()

while event_queue:
    scheduled_time, neg_crit, task, execution_time, instance = heapq.heappop(
        event_queue)
    finish_time = assign_core_and_run(
        scheduled_time, task, execution_time, instance)
    schedule_event_runnables([task], finish_time)

print("\nCore 0 Schedule:")
for start, end, task, inst in execution_log_core[0]:
    print(f"[{start:4} → {end:4}] ms : {task} (instance {inst})")

print("\nCore 1a Schedule:")
for start, end, task, inst in execution_log_core['1a']:
    print(f"[{start:4} → {end:4}] ms : {task} (instance {inst})")

print("\nCore 1b Schedule:")
for start, end, task, inst in execution_log_core['1b']:
    print(f"[{start:4} → {end:4}] ms : {task} (instance {inst})")

print(f"\nTotal Execution Time: {max(core_time.values())} ms")
