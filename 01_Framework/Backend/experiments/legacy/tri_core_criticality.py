"""Task scheduling simulation with 3 logical CPUs and criticality awareness."""
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
    for name, props in runnables.items():
        if props["type"] != "event":
            continue
        if not set(props["deps"]) & set(triggered_tasks):
            continue
        if all(completed_instances[dep] > event_task_instance_counter[name]
               for dep in props["deps"]):
            instance = event_task_instance_counter[name]
            heapq.heappush(event_queue, (current_time, -props["criticality"],
                                         name, props["execution_time"], instance))
            event_task_instance_counter[name] += 1


def assign_core_and_run(sched_time, task, exec_time, inst):
    affinity = runnables[task]["affinity"]
    if affinity == 0:
        actual_start = max(core_time[0], sched_time)
        finish_time = actual_start + exec_time
        core_time[0] = finish_time
        execution_log_core[0].append((actual_start, finish_time, task, inst))
        completed_instances[task] = inst + 1
        return finish_time
    else:
        # Choose earlier available between 1a and 1b
        chosen_core = '1a' if core_time['1a'] <= core_time['1b'] else '1b'
        actual_start = max(core_time[chosen_core], sched_time)
        finish_time = actual_start + exec_time
        core_time[chosen_core] = finish_time
        execution_log_core[chosen_core].append(
            (actual_start, finish_time, task, inst))
        completed_instances[task] = inst + 1
        return finish_time


# Main simulation
schedule_periodic_runnables()

while event_queue:
    sched_time, neg_crit, task, exec_time, inst = heapq.heappop(event_queue)
    finish_time = assign_core_and_run(sched_time, task, exec_time, inst)
    schedule_event_runnables([task], finish_time)

# Output
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
