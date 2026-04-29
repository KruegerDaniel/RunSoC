from schemas.schemas import ProblemInstance
from schemas.solver_result import SolverResult
from utils.numerical_util import clean_num


def build_solution_response(
        problem: ProblemInstance,
        result: SolverResult,
) -> dict:
    tasks_by_id = {t.id: t for t in problem.tasks}
    cores_by_id = {c.id: c for c in problem.cores}

    pred_map: dict[str, list[str]] = {}
    for dep in problem.dependencies:
        pred_map.setdefault(dep.successor, []).append(dep.predecessor)

    if not result.feasible:
        return {
            "solver": result.solver,
            "status": result.status,
            "feasible": False,
            "objective": None,
            "makespan": None,
            "summary": {
                "task_count": len(problem.tasks),
                "scheduled_task_count": 0,
                "dependency_count": len(problem.dependencies),
                "core_count": len(problem.cores),
                "cluster_count": len(problem.clusters),
            },
            "resource_usage": {
                "core_memory": [],
                "cluster_memory": [],
            },
            "schedule": [],
        }

    schedule = []

    for task in problem.tasks:
        assigned_core = result.assignment.get(task.id)
        assigned_cluster = None
        duration_on_core = None

        if assigned_core is not None:
            core = cores_by_id[assigned_core]
            assigned_cluster = core.cluster_id
            duration_on_core = clean_num(task.duration * core.wcet_scale)

        predecessors = pred_map.get(task.id, [])

        pred_finishes = [
            result.finishes.get(pred)
            for pred in predecessors
            if result.finishes.get(pred) is not None
        ]

        eligible_time = max(pred_finishes, default=0)

        schedule.append(
            {
                "task_id": task.id,
                "task_name": task.name,
                "task_type": task.task_type,
                "assigned_core": assigned_core,
                "assigned_cluster": assigned_cluster,
                "min_start": task.min_start,
                "eligible_time": clean_num(eligible_time),
                "start_time": clean_num(result.starts.get(task.id)),
                "finish_time": clean_num(result.finishes.get(task.id)),
                "base_duration": task.duration,
                "scheduled_duration": duration_on_core,
                "memory": task.memory,
                "predecessors": predecessors,
            }
        )

    schedule.sort(
        key=lambda item: (
            item["start_time"] if item["start_time"] is not None else float("inf"),
            item["assigned_core"] or "",
            item["task_id"],
        )
    )

    core_memory = []

    for core in problem.cores:
        assigned_tasks = sorted(
            task_id
            for task_id, core_id in result.assignment.items()
            if core_id == core.id
        )

        used = sum(tasks_by_id[task_id].memory for task_id in assigned_tasks)
        overflow = result.core_overflows.get(core.id, 0)

        core_memory.append(
            {
                "core_id": core.id,
                "core_name": core.name,
                "cluster_id": core.cluster_id,
                "budget": core.memory_budget,
                "used": clean_num(used),
                "overflow": clean_num(overflow),
                "assigned_tasks": assigned_tasks,
            }
        )

    cluster_memory = []

    for cluster in problem.clusters:
        cluster_core_ids = {
            core.id for core in problem.cores if core.cluster_id == cluster.id
        }

        assigned_tasks = sorted(
            task_id
            for task_id, core_id in result.assignment.items()
            if core_id in cluster_core_ids
        )

        used = sum(tasks_by_id[task_id].memory for task_id in assigned_tasks)
        overflow = result.cluster_overflows.get(cluster.id, 0)

        cluster_memory.append(
            {
                "cluster_id": cluster.id,
                "cluster_name": cluster.name,
                "budget": cluster.memory_budget,
                "used": clean_num(used),
                "overflow": clean_num(overflow),
                "assigned_tasks": assigned_tasks,
            }
        )

    return {
        "solver": result.solver,
        "status": result.status,
        "feasible": True,
        "objective": clean_num(result.objective),
        "makespan": clean_num(result.makespan),
        "summary": {
            "task_count": len(problem.tasks),
            "scheduled_task_count": len(schedule),
            "dependency_count": len(problem.dependencies),
            "core_count": len(problem.cores),
            "cluster_count": len(problem.clusters),
        },
        "resource_usage": {
            "core_memory": core_memory,
            "cluster_memory": cluster_memory,
        },
        "schedule": schedule,
        "runtime_seconds": round(result.runtime_seconds, 4),
        "metadata": result.metadata or {},
    }
