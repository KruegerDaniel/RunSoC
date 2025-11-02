"""Task scheduling simulation with CPU affinity and criticality awareness."""
import heapq
from collections import defaultdict

#from driving_mock import runnables


class ExecutionLog:
    def __init__(self):
        self.log = []

    def append(self, entry):
        self.log.append(entry)

    def get_log(self):
        return self.log


def run_criticality(runnables, num_cores=2, simulation_time=400):
    print(runnables)
    id_to_name = {props['id']: name for name,
                  props in runnables.items() if 'id' in props}
    name_to_id = {name: props['id']
                  for name, props in runnables.items() if 'id' in props}

    event_queue = []
    heapq.heapify(event_queue)
    core_time = [0 for _ in range(num_cores)]
    execution_log_core = {i: [] for i in range(num_cores)}
    completed_instances = defaultdict(int)
    event_task_instance_counter = defaultdict(int)

    def schedule_periodic_runnables():
        """Schedule all periodic runnables up to the simulation time limit,
        ensuring sequential execution."""
        for name, props in runnables.items():
            if props["type"] == "periodic":
                time = 0
                counter = 0
                while time < simulation_time:
                    heapq.heappush(event_queue, (time, -props["criticality"], name,
                                                 props["execution_time"], counter))
                    time += props["period"]
                    counter += 1

    def are_tasks_independent(task1, task2):
        """Check if two tasks are independent by verifying they don't share dependencies."""
        id1 = name_to_id.get(task1, task1)
        id2 = name_to_id.get(task2, task2)
        deps1 = set(runnables[task1].get("deps", []))
        deps2 = set(runnables[task2].get("deps", []))
        return not (deps1 & {id2} or deps2 & {id1} or deps1 & deps2)

    def schedule_event_runnables(triggered_tasks, current_time):
        """Schedule event-based tasks that are triggered by completed dependencies."""
        for name, props in runnables.items():
            if props["type"] != "event":
                continue
            triggered_ids = [name_to_id.get(t, t) for t in triggered_tasks]
            if not set(props["deps"]) & set(triggered_ids):
                continue
            if all(
                completed_instances[id_to_name.get(dep, dep)]
                > event_task_instance_counter[name]
                for dep in props["deps"]
            ):
                current_instance = event_task_instance_counter[name]
                new_task_tuple = (
                    current_time, -props["criticality"], name,
                    props["execution_time"], current_instance)

                inserted = False
                for idx, (sched_time, neg_crit, task_name, exec_time, inst) in enumerate(event_queue):
                    if (sched_time < current_time and
                        -neg_crit < props["criticality"] and
                        are_tasks_independent(name, task_name) and
                            runnables[name]["affinity"] == runnables[task_name]["affinity"]):
                        event_queue.pop(idx)
                        heapq.heappush(event_queue, new_task_tuple)
                        heapq.heappush(event_queue, (current_time,
                                       neg_crit, task_name, exec_time, inst))
                        inserted = True
                        break

                if not inserted:
                    heapq.heappush(event_queue, new_task_tuple)

                event_task_instance_counter[name] += 1

    schedule_periodic_runnables()

    while event_queue:
        scheduled_time, negative_criticality, task, execution_time, instance = heapq.heappop(
            event_queue)
        affinity = runnables[task]["affinity"]
        actual_start = max(core_time[affinity], scheduled_time)
        finish_time = actual_start + execution_time
        core_time[affinity] = finish_time
        execution_log_core[affinity].append(
            (actual_start, finish_time, task, instance, affinity))
        completed_instances[task] = instance + 1
        schedule_event_runnables([task], finish_time)

    merged_log = []
    for entries in execution_log_core.values():
        merged_log.extend(entries)
    merged_log.sort(key=lambda x: x[0])
    log = ExecutionLog()
    for entry in merged_log:
        log.append(entry)
    total_execution_time = max(core_time)
    return log, total_execution_time
