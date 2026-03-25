from dataclasses import asdict, dataclass
import pulp

from schemas.schedule_entry import ScheduleEntry


def extract_solution(problem, model, variables, status):
    if pulp.LpStatus[status] not in ("Optimal", "Feasible"):
        return {
            "status": pulp.LpStatus[status],
            "objective": None,
            "schedule": [],
        }

    x = variables["x"]
    s = variables["s"]
    f = variables["f"]
    cmax = variables["cmax"]

    pred_map = {}
    for dep in problem.dependencies:
        pred_map.setdefault(dep.successor, []).append(dep.predecessor)

    schedule = []
    for task in problem.tasks:
        assigned_core = None
        for core in task.eligible_cores:
            if pulp.value(x[task.id][core]) > 0.5:
                assigned_core = core
                break

        eligible_time = 0
        preds = pred_map.get(task.id, [])
        if preds:
            eligible_time = max(int(round(pulp.value(f[p]))) for p in preds)

        schedule.append(
            asdict(ScheduleEntry(
                task=task.id,
                start_time=int(round(pulp.value(s[task.id]))),
                finish_time=int(round(pulp.value(f[task.id]))),
                core=assigned_core,
                eligible_time=eligible_time,
            ))
        )

    schedule.sort(key=lambda e: (e["start_time"], e["core"], e["task"]))

    return {
        "status": pulp.LpStatus[status],
        "objective": pulp.value(model.objective),
        "makespan": int(round(pulp.value(cmax))),
        "schedule": schedule,
    }