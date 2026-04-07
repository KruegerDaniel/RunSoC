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
