"""Gantt chart for a 3-core system: Core 0, Core 1a, Core 1b"""

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt

from affinity.tri_core_affinity import execution_log_core

# Filter only first 150ms
filtered_logs = []
for label, entries in execution_log_core.items():
    for start, end, task, instance in entries:
        if end <= 150:
            filtered_logs.append((start, end, task, instance, f"Core {label}"))

# Unique task list for coloring
unique_tasks = sorted(set(task for _, _, task, _, _ in filtered_logs))
color_palette = plt.cm.get_cmap("tab20", len(unique_tasks))
task_colors = {task: color_palette(i) for i, task in enumerate(unique_tasks)}

# Gantt plot
fig, ax = plt.subplots(figsize=(14, 6))

# Y-axis mapping
y_positions = {"Core 0": 2, "Core 1a": 1, "Core 1b": 0}

# Draw bars
for start, end, task, instance, core in filtered_logs:
    ax.barh(y_positions[core], end - start, left=start,
            color=task_colors[task], edgecolor="black")
    ax.text(start + (end - start) / 2, y_positions[core], f"{task} ({instance})",
            ha='center', va='center', fontsize=7, color='white', clip_on=True)

ax.set_yticks([0, 1, 2])
ax.set_yticklabels(["Core 1b", "Core 1a", "Core 0"])
ax.set_xlabel("Time (ms)")
ax.set_title("Gantt Chart of Runnable Execution Schedule (First 150ms)")
ax.grid(True, axis='x', linestyle='--', alpha=0.5)

# Legend
handles = [mpatches.Patch(color=color, label=task)
           for task, color in task_colors.items()]
ax.legend(handles=handles, bbox_to_anchor=(
    1.05, 1), loc='upper left', title="Tasks")

plt.tight_layout()
plt.show()
