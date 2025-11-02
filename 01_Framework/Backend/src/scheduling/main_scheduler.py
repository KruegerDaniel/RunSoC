"""General main scheduling algorithm with FCFS/PAS ordering and static/dynamic
core allocation, following the provided pseudocode.

Data model assumptions for `tasks` input:
- Dict[str, Dict]: each task has keys:
  - 'type': 'periodic' or 'event'
  - 'execution_time': int (t_i)
  - 'period': int (T_i) for periodic only (optional for event)
  - 'deps': List[str] (predecessor task names), optional
  - 'priority': int used as priority p_i for PAS (default 0)

This scheduler treats a single instance of each task per iteration, i.e., a
finite DAG-style schedule. Periodic tasks behave as sources with eta_i = 0.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from math import ceil, inf
from typing import Dict, List, Optional, Tuple

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt


@dataclass
class ScheduleEntry:
    task: str
    start_time: int
    finish_time: int
    core: int
    eligible_time: int


def topology(tasks: Dict[str, Dict]) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    successors: Dict[str, List[str]] = {name: [] for name in tasks}
    predecessors: Dict[str, List[str]] = {name: [] for name in tasks}
    for name, props in tasks.items():
        for dep in props.get("deps", []) or []:
            if dep in tasks:
                successors[dep].append(name)
                predecessors[name].append(dep)
    return successors, predecessors


def order_eligible(eligible: List[str], tasks: Dict[str, Dict], eta: Dict[str, int], policy: str) -> List[str]:
    policy = policy.lower()
    if policy == "pas":
        def key_fn(name: str):
            p_i = int(tasks[name].get("priority", 0))
            return (-p_i, int(eta.get(name, 0)), name)
        return sorted(eligible, key=key_fn)
    # fcfs
    return sorted(eligible, key=lambda n: (int(eta.get(n, 0)), n))


def static_allocation(num_cores: int, p_max: int, n_min: int) -> List[int]:
    c_alloc = max(1, min(num_cores, p_max, n_min))
    return list(range(c_alloc))  # lowest indices


def dynamic_allocation(idle_cores: List[int], eligible: List[str]) -> Tuple[int, List[int]]:
    c_alloc = min(len(idle_cores), len(eligible))
    return idle_cores[:c_alloc]


def compute_total_work(tasks: Dict[str, Dict]) -> int:
    return sum(int(props.get("execution_time", 0))
               for props in tasks.values())


def compute_parallelism_bounds(tasks: Dict[str, Dict], num_cores: int) -> Tuple[int, int]:
    """Compute (W, T_CP, P_max_approx). Uses a relaxed approximation for P_max: number of sources."""
    successors, predecessors = topology(tasks)
    # Total work W (one instance per node baseline)
    W = compute_total_work(tasks)
    # Critical path via longest path DP on DAG of single-shot graph
    # (For periodic Tasks, treat as sources with EST=0)
    task_path_length: Dict[str, int] = {}
    remaining_tasks = set(tasks.keys())
    while remaining_tasks:
        progressed = False
        for name in list(remaining_tasks):
            if all(p in task_path_length for p in predecessors[name]):
                task_path_length[name] = max((task_path_length[p] + int(tasks[p]["execution_time"])
                                                  for p in predecessors[name]), default=0)
                remaining_tasks.remove(name)
                progressed = True
        if not progressed:
            # Cycles (shouldn't happen in a DAG); break conservatively
            break
    T_CP = max((task_path_length[n] + int(tasks[n]["execution_time"])
               for n in task_path_length), default=0)
    # Approx P_max: max number of simultaneously ready sources after releases -> count of nodes with no preds

    def calculate_max_parallelism() -> int:
        """Calculate P_max by finding the maximum number of eligible tasks at any time."""
        max_parallelism = 0
        completed = set()
        eligible = set()

        # Initially eligible: Tasks with no dependencies or periodic sources
        for name, props in tasks.items():
            deps = props.get("deps", []) or []
            if props.get("type") == "periodic" or len(deps) == 0:
                eligible.add(name)

        max_parallelism = max(max_parallelism, len(eligible))

        while eligible:
            # Execute all eligible Tasks simultaneously (unlimited cores)
            Tasks_to_execute = list(eligible)
            eligible.clear()
            completed.update(Tasks_to_execute)

            # Find new eligible Tasks
            newly_eligible = set()
            for Task in Tasks_to_execute:
                for succ in successors.get(Task, []):
                    if succ in completed or succ in newly_eligible:
                        continue
                    preds = tasks.get(succ, {}).get("deps", []) or []
                    if all(p in completed for p in preds):
                        newly_eligible.add(succ)

            eligible.update(newly_eligible)
            max_parallelism = max(max_parallelism, len(eligible))

        return max(max_parallelism, 1)

    p_max = calculate_max_parallelism()

    def calculate_min_core_count(
        num_cores: int,
        total_work: int,
        critical_path: int,
        epsilon: float = 0.9,
    ) -> int:
        """Compute N_min = ceil( (epsilon * p) / (s * (1 - epsilon)) ) per DAG-aware Amdahl's law.

        Handles edge cases: if W == 0 -> allocate 1; if s == 0 -> N_min treated as num_cores.
        """
        # Guard: no work
        if total_work <= 0:
            return 1

        # Compute serial/parallel fractions
        s_fraction = critical_path / total_work
        s_fraction = max(0.0, min(1.0, s_fraction))
        p_fraction = max(0.0, 1.0 - s_fraction)

        # Compute N_min; handle s == 0 (perfect parallelism) by allowing up to available cores
        if s_fraction == 0.0:
            minimal_core_count = num_cores
        else:
            # Avoid division by zero for epsilon extremes
            eps = min(max(epsilon, 1e-9), 1 - 1e-9)
            minimal_core_count = ceil(
                (eps * p_fraction) / (s_fraction * (1.0 - eps)))
            minimal_core_count = max(1, minimal_core_count)

        return minimal_core_count

    n_min = calculate_min_core_count(num_cores, W, T_CP)

    return p_max, n_min

# Patch: ensure next_rel considers only releases strictly after current tau to avoid stalling
# Re-run the two scenarios

# (Reusing the functions and data already defined above)


def run_main_scheduler(
    tasks: Dict[str, Dict],
    num_cores: int,
    scheduling_policy: str = "fcfs",
    allocation_policy: str = "dynamic",
    I: Optional[int] = None,
) -> Tuple[List[ScheduleEntry], int, int]:
    """Execute the main scheduling algorithm for a finite DAG per iteration.

    Returns a tuple (all_schedules, makespans):
    - all_schedules: list per iteration of ScheduleEntry list
    - makespans: list of iteration total times
    """

    successors, predecessors = topology(tasks)

    total_work = compute_total_work(tasks)
    if I is None:
        T_end = 2 * total_work
    else:
        T_end = I * total_work

    p_max, n_min = compute_parallelism_bounds(tasks, num_cores)

    if allocation_policy.lower() == "static":
        available_cores = static_allocation(num_cores, p_max, n_min)
    else:
        available_cores = list(range(num_cores))

    idle_cores = list(range(num_cores))

    tau = 0
    phi: Dict[str, int] = {}
    next_active = 0
    eta: Dict[str, int] = {}
    start: Dict[str, int] = {}
    running: Dict[Tuple[str, int], Tuple[int, int]] = {}
    schedule: List[ScheduleEntry] = []
    for name, props in tasks.items():
        if props.get("type") == "periodic" and int(props.get("period", 0)) > 0:
            phi[name] = 0
        else:
            eta[name] = 0
            start[name] = 0

    tokens: Dict[Tuple[str, str], int] = {
        (p, n): 0 for n in tasks for p in predecessors[n]}

    def get_periodic_at_tau(t: int) -> List[str]:
        return sorted([n for n in phi if phi[n] == t])

    def get_event_at_tau(t: int) -> List[str]:
        return [n for n, props in tasks.items() if props.get("type") != "periodic"
                and all(tokens[(p, n)] > 0 for p in predecessors[n])
                and start[n] <= t]

    def run_periodic_now(t: int, periodic: List[str], available_cores: List[int]) -> None:
        nonlocal total_delay
        if not periodic:
            return
        for n in periodic:
            if not available_cores:
                if running:
                    tx = min(finish for finish, _ in running.values()) - t
                else:
                    tx = 0
                total_delay += tx
                start = t + tx
                phi[n] = start
                continue
            assigned_core = min(available_cores)
            available_cores.remove(assigned_core)
            idle_cores.remove(assigned_core)
            t_i = int(tasks[n]["execution_time"])
            start = t
            finish = t + t_i
            running[(n, t)] = (finish, assigned_core)
            schedule.append(ScheduleEntry(
                n, start, finish, assigned_core, eligible_time=t))
            # print(ScheduleEntry(
            #     n, start, finish, assigned_core, eligible_time=t))
            T_i = int(tasks[n].get("period", 0))
            next_active = t + T_i
            if T_i > 0 and next_active < T_end:
                phi[n] = next_active
            else:
                phi.pop(n, None)

    total_delay = 0
    while tau < T_end:
        # Admit periodic jobs released at tau
        eligible_event = get_event_at_tau(tau)

        if len(eligible_event) == 0 and num_cores <= 1:
            tau = next_active

        periodic_at_tau = get_periodic_at_tau(tau)

        ordered_eligible_periodic = order_eligible(periodic_at_tau, tasks, {
            e: tau for e in periodic_at_tau}, scheduling_policy)

        ordered_eligible_event = order_eligible(eligible_event, tasks, {
            e: eta[e] for e in eligible_event}, scheduling_policy)

        eligible = ordered_eligible_periodic + ordered_eligible_event

        if allocation_policy.lower() == 'dynamic':
            available_cores = dynamic_allocation(idle_cores, eligible)

        run_periodic_now(tau, ordered_eligible_periodic, available_cores)

        sorted_available_cores = list(sorted(available_cores))
        for name in ordered_eligible_event:
            start[name] = tau
            if not sorted_available_cores:
                break

            t_i = int(tasks[name]["execution_time"])

            if tau + t_i > T_end:
                break

            if phi and start[name] + t_i > next_active and start[name] <= tau:
                first_phi_key = min(phi.keys())
                delayed_start_time = next_active + \
                    tasks[first_phi_key]["execution_time"]
                total_delay += delayed_start_time - start[name]
                start[name] = delayed_start_time
            else:
                core = sorted_available_cores.pop(0)
                if core in available_cores:
                    available_cores.remove(core)
                    idle_cores.remove(core)
                running[(name, tau)] = (tau + t_i, core)
                schedule.append(ScheduleEntry(
                    name, tau, tau + t_i, core, eligible_time=tau))
                # print(ScheduleEntry(
                #     name, tau, tau + t_i, core, eligible_time=tau))
                for p in predecessors[name]:
                    tokens[(p, name)] -= 1

        next_fin = min((fin for (fin, _) in running.values()), default=None)
        # strictly greater than tau
        next_active = min((t for t in phi.values() if t > tau), default=inf)
        next_decision_point = [t for t in [
            next_fin, next_active] if t is not None]
        if not next_decision_point:
            break
        tau_next = min(next_decision_point)

        # Complete any at tau_next
        for (name, eligible_time), (finish_time, core) in list(running.items()):
            if finish_time == tau_next:
                running.pop((name, eligible_time))
                if core not in idle_cores:
                    idle_cores.append(core)
                    idle_cores.sort()
                if allocation_policy.lower() == "static":
                    available_cores.append(core)
                    available_cores.sort()
                for s in successors[name]:
                    tokens[(name, s)] = tokens.get((name, s), 0) + 1
                    start[s] = finish_time
                    eta[s] = finish_time

        tau = tau_next

    finish_time = max((e.finish_time for e in schedule), default=0)
    return schedule, finish_time, total_delay


def plot_schedule(log_data, title, ax, color_mapping=None, total_cores=None):
    base_Tasks = sorted(set(Task for _, _, Task, _, _ in log_data))

    if color_mapping is None:
        color_palette = plt.cm.get_cmap("tab20", len(base_Tasks))
        color_mapping = {base_Task: color_palette(
            i) for i, base_Task in enumerate(base_Tasks)}

    # Always include all cores if total_cores provided; otherwise, only used cores
    cores = list(range(total_cores)) if total_cores is not None else \
        list(sorted(set(core for _, _, _, _, core in log_data)))

    y_positions = {core: i for i, core in enumerate(cores)}

    for start, end, Task, release, core in log_data:
        ax.barh(y_positions[core], end - start, left=start,
                color=color_mapping[Task], edgecolor="black")

    ax.set_yticks(range(len(cores)))
    ax.set_yticklabels([f"Core {core}" for core in cores], fontsize=14)
    ax.set_ylim(-0.5, len(cores) - 0.5)
    ax.set_xlabel("Time (ms)", fontsize=14)
    ax.set_title(title, fontsize=18)
    ax.tick_params(axis='both', labelsize=14)
    ax.grid(True, axis='x', linestyle='--', alpha=0.5)

    def transform_label(label):
        if label.startswith('Task'):
            try:
                number = int(label[4:])
                return f"task {number}"
            except:
                return label
        return label

    def get_task_number(task):
        if task.startswith('Task'):
            try:
                return int(task[4:])
            except:
                return float('inf')
        return float('inf')

    sorted_tasks = sorted(base_Tasks, key=get_task_number)
    handles = [mpatches.Patch(color=color_mapping[task], label=transform_label(task))
               for task in sorted_tasks]
    ax.legend(handles=handles, bbox_to_anchor=(1.05, 1),
              loc='upper left', title="Tasks", fontsize=14, title_fontsize=18)

    return color_mapping


# Example tasks
tasks = {
    'RadarCapture': {
        'priority': 1,
        'period': 75,
        'execution_time': 2,
        'type': 'periodic',
        'deps': []
    },
    'CameraCapture': {
        'priority': 0,
        'period': 50,
        'execution_time': 7,
        'type': 'periodic',
        'deps': []
    },
    'SensorFusion': {
        'priority': 1,
        'execution_time': 6,
        'type': 'event',
        'deps': ['RadarCapture', 'CameraCapture'],
    },
    'ObjectDetection': {
        'priority': 1,
        'execution_time': 15,
        'type': 'event',
        'deps': ['SensorFusion'],
    },
    'TrajectoryPrediction': {
        'priority': 1,
        'execution_time': 8,
        'type': 'event',
        'deps': ['ObjectDetection'],
    },
    'CollisionRiskAssessment': {
        'priority': 2,
        'execution_time': 3,
        'type': 'event',
        'deps': ['TrajectoryPrediction'],
    },
    'EmergencyBrakeDecision': {
        'priority': 2,
        'execution_time': 2,
        'type': 'event',
        'deps': ['CollisionRiskAssessment'],
    },
    'ActuatorControl': {
        'priority': 2,
        'execution_time': 1,
        'type': 'event',
        'deps': ['EmergencyBrakeDecision'],
    },
    'LaneMarkingDetection': {
        'priority': 1,
        'execution_time': 6,
        'type': 'event',
        'deps': ['CameraCapture'],
    },
    'VehiclePositionEstimation': {
        'priority': 1,
        'execution_time': 4,
        'type': 'event',
        'deps': ['LaneMarkingDetection'],
    },
    'LaneDepartureWarning': {
        'priority': 1,
        'execution_time': 2,
        'type': 'event',
        'deps': ['VehiclePositionEstimation'],
    },
    'SteeringAngleCalculation': {
        'priority': 1,
        'execution_time': 2,
        'type': 'event',
        'deps': ['VehiclePositionEstimation'],
    },
    'SteeringActuatorControl': {
        'priority': 2,
        'execution_time': 1,
        'type': 'event',
        'deps': ['LaneDepartureWarning', 'SteeringAngleCalculation'],
    },

    # 'DistanceEstimation': {
    #     'priority': 1,
    #     'execution_time': 5,
    #     'type': 'event',
    #     'deps': ['ObjectDetection'],
    # },
    # 'RelativeSpeedEstimation': {
    #     'priority': 1,
    #     'execution_time': 4,
    #     'type': 'event',
    #     'deps': ['ObjectDetection'],
    # },
    # 'AdaptiveCruiseControlDecision': {
    #     'priority': 2,
    #     'execution_time': 6,
    #     'type': 'event',
    #     'deps': ['DistanceEstimation', 'RelativeSpeedEstimation'],
    # },
    # 'ThrottleControl': {
    #     'priority': 2,
    #     'execution_time': 2,
    #     'type': 'event',
    #     'deps': ['AdaptiveCruiseControlDecision'],
    # },
    # 'BrakeControl': {
    #     'priority': 2,
    #     'execution_time': 2,
    #     'type': 'event',
    #     'deps': ['AdaptiveCruiseControlDecision'],
    # },
}

tasks_long_path = {
    'Task1':  {'priority': 1, 'execution_time': 15, 'type': 'periodic', 'period': 100, 'deps': []},
    'Task2':  {'priority': 2, 'execution_time': 20, 'type': 'periodic', 'period': 180, 'deps': []},

    'Task3':  {'priority': 1, 'execution_time': 25, 'type': 'event', 'deps': ['Task1']},
    'Task4':  {'priority': 4, 'execution_time': 30, 'type': 'event', 'deps': ['Task3']},
    'Task5':  {'priority': 3, 'execution_time': 20, 'type': 'event', 'deps': ['Task4']},
    'Task6':  {'priority': 1, 'execution_time': 35, 'type': 'event', 'deps': ['Task5']},

    'Task7':  {'priority': 2, 'execution_time': 40, 'type': 'event', 'deps': ['Task6']},
    'Task8':  {'priority': 1, 'execution_time': 25, 'type': 'event', 'deps': ['Task7']},
    'Task9':  {'priority': 0, 'execution_time': 30, 'type': 'event', 'deps': ['Task8']},
    'Task10': {'priority': 4, 'execution_time': 20, 'type': 'event', 'deps': ['Task9']},

    'Task11': {'priority': 2, 'execution_time': 45, 'type': 'event', 'deps': ['Task10']},
    'Task12': {'priority': 0, 'execution_time': 30, 'type': 'event', 'deps': ['Task11']},
    'Task13': {'priority': 3, 'execution_time': 35, 'type': 'event', 'deps': ['Task12']},

    'Task14': {'priority': 1, 'execution_time': 25, 'type': 'event', 'deps': ['Task13']},
    'Task15': {'priority': 3, 'execution_time': 40, 'type': 'event', 'deps': ['Task14']},
    'Task16': {'priority': 3, 'execution_time': 20, 'type': 'event', 'deps': ['Task15']},

    'Task17': {'priority': 4, 'execution_time': 50, 'type': 'event', 'deps': ['Task16']},
    'Task18': {'priority': 1, 'execution_time': 25, 'type': 'event', 'deps': ['Task17']},

    'Task19': {'priority': 4, 'execution_time': 35, 'type': 'event', 'deps': ['Task18']},
    'Task20': {'priority': 2, 'execution_time': 30, 'type': 'event', 'deps': ['Task19']},
}

tasks_balanced = {
    'Task1':  {'priority': 1, 'execution_time': 15, 'type': 'periodic', 'period': 100, 'deps': []},
    'Task2':  {'priority': 2, 'execution_time': 20, 'type': 'periodic', 'period': 180, 'deps': []},

    'Task3':  {'priority': 1, 'execution_time': 25, 'type': 'event', 'deps': ['Task1']},
    'Task4':  {'priority': 4, 'execution_time': 30, 'type': 'event', 'deps': ['Task1']},
    'Task5':  {'priority': 3, 'execution_time': 20, 'type': 'event', 'deps': ['Task2']},
    'Task6':  {'priority': 1, 'execution_time': 35, 'type': 'event', 'deps': ['Task2']},

    'Task7':  {'priority': 2, 'execution_time': 40, 'type': 'event', 'deps': ['Task3', 'Task4']},
    'Task8':  {'priority': 1, 'execution_time': 25, 'type': 'event', 'deps': ['Task5', 'Task6']},
    'Task9':  {'priority': 0, 'execution_time': 30, 'type': 'event', 'deps': ['Task3']},
    'Task10': {'priority': 4, 'execution_time': 20, 'type': 'event', 'deps': ['Task4']},

    'Task11': {'priority': 2, 'execution_time': 45, 'type': 'event', 'deps': ['Task7']},
    'Task12': {'priority': 0, 'execution_time': 30, 'type': 'event', 'deps': ['Task8']},
    'Task13': {'priority': 3, 'execution_time': 35, 'type': 'event', 'deps': ['Task9', 'Task10']},

    'Task14': {'priority': 1, 'execution_time': 25, 'type': 'event', 'deps': ['Task11']},
    'Task15': {'priority': 3, 'execution_time': 40, 'type': 'event', 'deps': ['Task12']},
    'Task16': {'priority': 3, 'execution_time': 20, 'type': 'event', 'deps': ['Task13']},

    'Task17': {'priority': 4, 'execution_time': 50, 'type': 'event', 'deps': ['Task14', 'Task15']},
    'Task18': {'priority': 1, 'execution_time': 25, 'type': 'event', 'deps': ['Task16']},

    'Task19': {'priority': 4, 'execution_time': 35, 'type': 'event', 'deps': ['Task17', 'Task18']},
    'Task20': {'priority': 2, 'execution_time': 30, 'type': 'event', 'deps': ['Task19']},
}

testing_tasks = tasks_balanced

# Re-run (disabled to only show sweep plots later)
schedule_dyn, finish_dyn, wait_extra_dyn = run_main_scheduler(
    testing_tasks, num_cores=6, scheduling_policy="fcfs", allocation_policy="dynamic", I=3)
schedule_static, finish_static, wait_extra_static = run_main_scheduler(
    testing_tasks, num_cores=6, scheduling_policy="fcfs", allocation_policy="static", I=3)


def schedule_to_log_data(schedule: List[ScheduleEntry]):
    return [(e.start_time, e.finish_time, e.task, e.eligible_time, e.core) for e in schedule]


# Create consistent color mapping
all_tasks = set()
for task in tasks_long_path.keys():
    all_tasks.add(task)
all_tasks = sorted(all_tasks, key=lambda x: int(
    x[4:]) if x.startswith('Task') else float('inf'))

color_palette = plt.cm.get_cmap("tab20", len(all_tasks))
consistent_color_mapping = {task: color_palette(
    i) for i, task in enumerate(all_tasks)}

# Plot dynamic schedule (disabled; we will show only sweep plots)
fig_dyn, ax_dyn = plt.subplots(1, 1, figsize=(19.20, 10.80), sharex=True)
plot_schedule(schedule_to_log_data(schedule_dyn),
              f"Dynamic Allocation (PAS), finish @ {finish_dyn} ms",
              ax_dyn, consistent_color_mapping, total_cores=6)
fig_dyn.subplots_adjust(left=0.08, right=0.78, top=0.90, bottom=0.12)
plt.show()

# Plot static schedule (disabled; we will show only sweep plots)
fig_static, ax_static = plt.subplots(
    1, 1, figsize=(19.20, 10.80), sharex=True)
plot_schedule(schedule_to_log_data(schedule_static),
              f"Static Allocation (PAS), finish @ {finish_static} ms",
              ax_static, consistent_color_mapping, total_cores=6)
fig_static.subplots_adjust(left=0.08, right=0.78, top=0.90, bottom=0.12)
plt.show()

# Count total tasks executed


def count_executed_tasks(schedule):
    return len(schedule)  # Each entry in schedule is one execution

    # After your scheduling calls
total_dyn = count_executed_tasks(schedule_dyn)
total_static = count_executed_tasks(schedule_static)

print(f"Total task executions (Dynamic): {total_dyn}")
print(f"Total task executions (Static): {total_static}")


def print_core_utilization(schedule: List[ScheduleEntry], finish_time: int, total_cores: int):
    exec_time = {c: 0 for c in range(total_cores)}
    for e in schedule:
        exec_time[e.core] += (e.finish_time - e.start_time)

    for c in range(total_cores):
        util = (exec_time[c] / finish_time * 100) if finish_time > 0 else 0.0
        print(
            f"Core {c}: total execution time = {exec_time[c]} ms, utilization = {util:.2f}%")

    avg_exec = sum(exec_time.values()) / total_cores
    avg_util = (avg_exec / finish_time * 100) if finish_time > 0 else 0.0
    print(f"Average execution time per core = {avg_exec:.2f} ms")
    print(f"Average utilization = {avg_util:.2f}%")

    print("\nDynamic run core utilization:")
    print_core_utilization(schedule_dyn, finish_dyn, total_cores=6)
    print("\nStatic run core utilization:")
    print_core_utilization(schedule_static, finish_static, total_cores=6)


def total_wait_time(schedule: List[ScheduleEntry]) -> int:
    # Sum waiting over all executions (repetitions included)
    return sum(max(0, e.start_time - e.eligible_time) for e in schedule)


def average_wait_per_execution(schedule: List[ScheduleEntry], extra_wait: int = 0) -> float:
    total_execs = len(schedule)
    total_wait = total_wait_time(schedule) + extra_wait
    return (total_wait / total_execs) if total_execs > 0 else 0.0

    # After computing schedules and getting wait_extra_dyn/static
avg_wait_dyn = average_wait_per_execution(schedule_dyn, wait_extra_dyn)
avg_wait_static = average_wait_per_execution(
    schedule_static, wait_extra_static)

print(
    f"Average waiting time per execution (Dynamic): {avg_wait_dyn:.2f} ms")
print(
    f"Average waiting time per execution (Static): {avg_wait_static:.2f} ms")

print(
    f"Total waiting time (Dynamic): {total_wait_time(schedule_dyn) + wait_extra_dyn} ms")
print(
    f"Total waiting time (Static): {total_wait_time(schedule_static) + wait_extra_static} ms")


def average_execution_time(schedule: List[ScheduleEntry]) -> float:
    if not schedule:
        return 0.0
    total_exec_time = sum(e.finish_time - e.start_time for e in schedule)
    return total_exec_time / len(schedule)


    # After computing schedules
avg_exec_dyn = average_execution_time(schedule_dyn)
avg_exec_static = average_execution_time(schedule_static)

print(
    f"Average execution time per task (Dynamic): {avg_exec_dyn:.2f} ms")
print(
    f"Average execution time per task (Static): {avg_exec_static:.2f} ms")


# Ensure output directory exists (match existing pattern ../../Images/backend/)
output_dir = os.path.normpath(os.path.join(
    os.path.dirname(__file__), '../../Images/backend'))
os.makedirs(output_dir, exist_ok=True)
