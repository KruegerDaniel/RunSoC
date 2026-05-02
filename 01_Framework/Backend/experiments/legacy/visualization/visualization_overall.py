"""Visualization of core behavior for different scheduling methods."""

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from criticality.criticality import run_criticality
from criticality.tri_core_criticality import \
    execution_log_core as tri_core_criticality_log
from driving_mock import execution_log as driving_mock_log
from driving_mock import runnables as driving_runnables
from fcfs.fcfs import run_fcfs_affinity
from fcfs.tri_core_fcfs import execution_log_core as tri_core_affinity_log


def get_finish_time(log):
    """Return the finish time of SteeringActuatorControl instance 2."""
    if isinstance(log, dict):
        entries = [entry + (core,) for core, core_log in log.items()
                   for entry in core_log]
    else:
        entries = [entry for entry in log.get_log()]
    for start, end, task, instance, *rest in sorted(entries, key=lambda x: (x[2], x[3], x[0])):
        if task == "SteeringActuatorControl" and instance == 2:
            return end
    return None


def filter_log_until(log, end_time, force_single_core=False):
    """Filter log to include only entries ending before or at end_time.
       If force_single_core is True, all entries are assigned to Core 0."""
    filtered = []
    if isinstance(log, dict):
        for core, core_log in log.items():
            for start, end, task, instance in core_log:
                if end > end_time:
                    continue
                filtered.append((start, end, task, instance,
                                0 if force_single_core else core))
    else:
        for start, end, task, instance, core in log.get_log():
            if end > end_time:
                continue
            filtered.append((start, end, task, instance,
                            0 if force_single_core else core))
    return filtered


def plot_schedule(log_data, title, ax):
    tasks = sorted(set(task for _, _, task, _, _ in log_data))
    color_palette = plt.cm.get_cmap("tab20", len(tasks))
    task_colors = {task: color_palette(i) for i, task in enumerate(tasks)}
    cores = list(sorted(set(core for _, _, _, _, core in log_data), key=str))
    y_positions = {core: i for i, core in enumerate(cores)}
    for start, end, task, instance, core in log_data:
        ax.barh(y_positions[core], end - start, left=start,
                color=task_colors[task], edgecolor="black")
    ax.set_yticks(range(len(cores)))
    ax.set_yticklabels([f"Core {core}" for core in cores])
    ax.set_xlabel("Time (ms)")
    ax.set_title(title)
    ax.grid(True, axis='x', linestyle='--', alpha=0.5)
    handles = [mpatches.Patch(color=color, label=task)
               for task, color in task_colors.items()]
    ax.legend(handles=handles, bbox_to_anchor=(1.05, 1),
              loc='upper left', title="Runnables")


# Prepare logs and core counts for each method
affinity_log, _ = run_fcfs_affinity(driving_runnables, num_cores=2)
criticality_log, _ = run_criticality(driving_runnables, num_cores=2)
methods = [
    ("Driving Mock", driving_mock_log, 1),
    ("Affinity", affinity_log, 2),
    ("Criticality", criticality_log, 2),
    ("Tri-Core Affinity", tri_core_affinity_log, 3),
    ("Tri-Core Criticality", tri_core_criticality_log, 3)
]

execution_times = []

for method, log, n_cores in methods:
    finish_time = get_finish_time(log)
    execution_times.append((method, finish_time))
    log_data = filter_log_until(
        log, finish_time, force_single_core=method == "Driving Mock")
    plt.figure(figsize=(14, 6))
    ax = plt.gca()
    plot_schedule(
        log_data,
        f"Gantt Chart of Runnable Execution Schedule - {method} (Execution Time: {finish_time} ms)",
        ax
    )
    plt.tight_layout()
    plt.show()

# Plot execution time comparison
plt.figure(figsize=(10, 5))
methods_names = [m for m, _ in execution_times]
finish_times = [t for _, t in execution_times]
plt.bar(methods_names, finish_times, color='skyblue', edgecolor='black')
plt.ylabel('Execution Time (ms)')
plt.title('Execution Time Comparison (Finish of SteeringActuatorControl instance 2)')
plt.grid(axis='y', linestyle='--', alpha=0.5)
plt.tight_layout()
plt.show()
