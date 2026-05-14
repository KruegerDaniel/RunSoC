import datetime
import os
import sys
from typing import List

import matplotlib.patches as mpatches
from matplotlib import pyplot as plt

current_dir = os.path.dirname(os.path.abspath(__file__))  # Points to /experiments
backend_dir = os.path.dirname(current_dir)                # Points to /Backend
src_dir = os.path.join(backend_dir, "src")                # Points to /Backend/src

if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from scheduling.main_scheduler import run_main_scheduler, ScheduleEntry
from example_tasks import tasks_long_path, tasks_balanced

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
    ax.set_yticklabels([f"Core {core}" for core in cores], fontsize=28)
    ax.set_ylim(-0.5, len(cores) - 0.5)
    ax.set_xlabel("Time (ms)", fontsize=28)
    #ax.set_title(title, fontsize=18)
    ax.tick_params(axis='x', labelsize=22)
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
    ax.legend(handles=handles, bbox_to_anchor=(1.01, 1.02),
              loc='upper left', title="Tasks", fontsize=26, title_fontsize=30)

    return color_mapping


# Ensure output directory exists
output_dir = os.path.normpath(os.path.join(
    os.path.dirname(__file__), '../../Images/backend'))
os.makedirs(output_dir, exist_ok=True)


plt.rcParams["font.family"] = "sans-serif"
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


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
              "",
              ax_dyn, consistent_color_mapping, total_cores=6)
fig_dyn.subplots_adjust(left=0.08, right=0.82, top=0.93, bottom=0.10)

#save
dyn_filepath = os.path.join(output_dir, f"schedule_dyn_{timestamp}.pdf")
fig_dyn.savefig(dyn_filepath, format='pdf', bbox_inches='tight')
plt.show()

# Plot static schedule (disabled; we will show only sweep plots)
fig_static, ax_static = plt.subplots(
    1, 1, figsize=(19.20, 10.80), sharex=True)
plot_schedule(schedule_to_log_data(schedule_static),
              "",
              ax_static, consistent_color_mapping, total_cores=6)
fig_static.subplots_adjust(left=0.08, right=0.78, top=0.93, bottom=0.12)
#save
static_filepath = os.path.join(output_dir, f"schedule_static_{timestamp}.pdf")
fig_static.savefig(static_filepath, format='pdf', bbox_inches='tight')
plt.show()


total_dyn = len(schedule_dyn)
total_static = len(schedule_static)

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

