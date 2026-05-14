"""Dual-core Gantt chart visualization of the first 150ms of execution log."""

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt

from criticality.affinity import execution_log_core

core0_filtered = [
    (start, end, task, instance, "Core 0")
    for start, end, task, instance in execution_log_core[0]
    if end <= 150
]
core1_filtered = [
    (start, end, task, instance, "Core 1")
    for start, end, task, instance in execution_log_core[1]
    if end <= 150
]

combined_log = core0_filtered + core1_filtered

unique_tasks = sorted(set(task for _, _, task, _, _ in combined_log))
color_palette = plt.cm.get_cmap("tab20", len(unique_tasks))
task_colors = {task: color_palette(i) for i, task in enumerate(unique_tasks)}

fig, ax = plt.subplots(figsize=(14, 6))

y_positions = {"Core 0": 1, "Core 1": 0}

for start, end, task, instance, core in combined_log:
    ax.barh(y_positions[core], end - start, left=start,
            color=task_colors[task], edgecolor="black")
    ax.text(start + (end - start) / 2, y_positions[core], f"{task} ({instance})",
            ha='center', va='center', fontsize=7, color='white', clip_on=True)

ax.set_yticks([0, 1])
ax.set_yticklabels(["Core 1", "Core 0"])
ax.set_xlabel("Time (ms)")
ax.set_title("Gantt Chart of Runnable Execution Schedule (First 150ms)")
ax.grid(True, axis='x', linestyle='--', alpha=0.5)

handles = [mpatches.Patch(color=color, label=task)
           for task, color in task_colors.items()]
ax.legend(handles=handles, bbox_to_anchor=(
    1.05, 1), loc='upper left', title="Tasks")

plt.tight_layout()
plt.show()
