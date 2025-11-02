# gantt.py
import base64
import io

import matplotlib.pyplot as plt


def create_gantt_chart(execution_log, title="Gantt Chart"):
    """
    For logs coming from SharedExecutionLog (fcfs/criticality),
    i.e. iterable of (start, end, task, instance, affinity).
    """
    filtered_log = [
        (start, end, task, instance, affinity)
        for start, end, task, instance, affinity in execution_log.get_log()
    ]

    if not filtered_log:
        return None

    import matplotlib.patches as mpatches

    cores = sorted({aff for *_, aff in filtered_log}, key=str)
    tasks = sorted({task for _, _, task, _, _ in filtered_log})
    cmap = plt.cm.get_cmap("tab20", len(tasks))
    task_colors = {task: cmap(i) for i, task in enumerate(tasks)}
    y_positions = {core: i for i, core in enumerate(cores)}

    fig, ax = plt.subplots(figsize=(12, 6))

    for start, end, task, instance, core in filtered_log:
        ax.barh(
            y_positions[core],
            end - start,
            left=start,
            color=task_colors[task],
            edgecolor="black",
        )
        ax.text(
            start + (end - start) / 2,
            y_positions[core],
            task,
            ha="center",
            va="center",
            color="white",
            fontsize=8,
        )

    ax.set_yticks(range(len(cores)))
    ax.set_yticklabels([f"Core {core}" for core in cores])
    ax.set_xlabel("Time (ms)")
    ax.set_title(title)
    ax.grid(True, axis="x", linestyle="--", alpha=0.5)

    handles = [
        mpatches.Patch(color=color, label=task) for task, color in task_colors.items()
    ]
    ax.legend(handles=handles, bbox_to_anchor=(1.05, 1), loc="upper left")

    plt.tight_layout()
    return _fig_to_base64(fig)


def create_gantt_chart_from_main(schedule_entries, title="Gantt Chart"):
    """
    For logs coming from main_scheduler (list of ScheduleEntry)
    """
    if not schedule_entries:
        return None

    import matplotlib.patches as mpatches

    cores = sorted({e.core for e in schedule_entries})
    tasks = sorted({e.task for e in schedule_entries})
    cmap = plt.cm.get_cmap("tab20", len(tasks))
    task_colors = {task: cmap(i) for i, task in enumerate(tasks)}
    y_positions = {core: i for i, core in enumerate(cores)}

    fig, ax = plt.subplots(figsize=(12, 6))

    for e in schedule_entries:
        ax.barh(
            y_positions[e.core],
            e.finish_time - e.start_time,
            left=e.start_time,
            color=task_colors[e.task],
            edgecolor="black",
        )
        ax.text(
            e.start_time + (e.finish_time - e.start_time) / 2,
            y_positions[e.core],
            e.task,
            ha="center",
            va="center",
            color="white",
            fontsize=8,
        )

    ax.set_yticks(range(len(cores)))
    ax.set_yticklabels([f"Core {core}" for core in cores])
    ax.set_xlabel("Time (ms)")
    ax.set_title(title)
    ax.grid(True, axis="x", linestyle="--", alpha=0.5)

    handles = [
        mpatches.Patch(color=color, label=task) for task, color in task_colors.items()
    ]
    ax.legend(handles=handles, bbox_to_anchor=(1.05, 1), loc="upper left")

    plt.tight_layout()
    return _fig_to_base64(fig)


def _fig_to_base64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=300)
    buf.seek(0)
    encoded = base64.b64encode(buf.getvalue()).decode()
    plt.close(fig)
    return encoded
