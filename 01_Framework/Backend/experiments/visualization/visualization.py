"""Visualization of the first 150ms of execution log from driving_mock."""

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt

from driving_mock import execution_log

filtered_log = [
    (start, end, task, instance)
    for start, end, task, instance, _ in execution_log.get_log()
    if end <= 150
]

task_colors = {}
color_palette = plt.cm.get_cmap("tab20", len(
    set(task for _, _, task, _ in filtered_log)))
for i, task in enumerate(sorted(set(task for _, _, task, _ in filtered_log))):
    task_colors[task] = color_palette(i)

fig, ax = plt.subplots(figsize=(12, 6))

for i, (start, end, task, instance) in enumerate(filtered_log):
    ax.barh(task, end - start, left=start, color=task_colors[task])

ax.set_xlabel("Time (ms)")
ax.set_title("Gantt Chart of Runnable Execution Schedule")
ax.grid(True)

handles = [mpatches.Patch(color=color, label=task)
           for task, color in task_colors.items()]
ax.legend(handles=handles, bbox_to_anchor=(
    1.05, 1), loc='upper left', title="Tasks")

plt.tight_layout()
plt.show()
