import pulp

from scheduling.base_solver import BaseSolver
from scheduling.ilp.model_builder import build_model
from schemas.schemas import ProblemInstance


class IlpSolverService(BaseSolver):
    name = "ILP"

    def __init__(self):
        self.time_limit_seconds = 100
        self.keepFiles = False

    def solve(self, problem: ProblemInstance) -> dict:
        model, variables = build_model(problem)

        solver = pulp.PULP_CBC_CMD(
            msg=True,
            keepFiles=self.keepFiles,
            logPath="cbc.log",
            timeLimit=self.time_limit_seconds,
        )
        status = model.solve(solver)

        return self._extract_solution(problem, model, variables, status)

    @staticmethod
    def _extract_solution(problem: ProblemInstance, model, variables, status) -> dict:
        status_str = pulp.LpStatus.get(status, str(status))

        def num(value, digits: int = 6):
            raw = pulp.value(value)
            if raw is None:
                return None
            rounded = round(float(raw), digits)
            if abs(rounded - round(rounded)) < 10 ** (-digits):
                return int(round(rounded))
            return rounded

        if status_str not in {"Optimal", "Feasible"}:
            return {
                "solver": "CBC",
                "status": status_str,
                "feasible": False,
                "objective": None,
                "makespan": None,
                "summary": {
                    "task_count": len(problem.tasks),
                    "scheduled_task_count": 0,
                    "dependency_count": len(problem.dependencies),
                },
                "resource_usage": {
                    "core_memory": [],
                    "cluster_memory": [],
                },
                "schedule": [],
            }

        x = variables["x"]
        s = variables["s"]
        f = variables["f"]
        cmax = variables["cmax"]
        core_overflow = variables["core_overflow"]
        cluster_overflow = variables["cluster_overflow"]

        tasks_by_id = {t.id: t for t in problem.tasks}
        cores_by_id = {c.id: c for c in problem.cores}

        pred_map = {}
        for dep in problem.dependencies:
            pred_map.setdefault(dep.successor, []).append(dep.predecessor)

        schedule = []
        for task in problem.tasks:
            assigned_core = next(
                (core_id for core_id in task.eligible_cores if num(x[task.id][core_id]) == 1),
                None,
            )

            start_time = num(s[task.id])
            finish_time = num(f[task.id])

            predecessors = pred_map.get(task.id, [])
            eligible_time = 0
            if predecessors:
                pred_finishes = [num(f[p]) for p in predecessors]
                pred_finishes = [v for v in pred_finishes if v is not None]
                eligible_time = max(pred_finishes, default=0)

            duration_on_core = None
            assigned_cluster = None
            if assigned_core is not None:
                assigned_cluster = cores_by_id[assigned_core].cluster_id
                duration_on_core = num(
                    task.duration * cores_by_id[assigned_core].wcet_scale
                )

            schedule.append(
                {
                    "task_id": task.id,
                    "task_name": task.name,
                    "task_type": task.task_type,
                    "assigned_core": assigned_core,
                    "assigned_cluster": assigned_cluster,
                    "min_start": task.min_start,
                    "eligible_time": eligible_time,
                    "start_time": start_time,
                    "finish_time": finish_time,
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
            assigned_tasks = [
                task.id for task in problem.tasks if num(x[task.id][core.id]) == 1
            ]
            used = sum(tasks_by_id[task_id].memory for task_id in assigned_tasks)
            overflow_value = num(core_overflow[core.id]) or 0

            core_memory.append(
                {
                    "core_id": core.id,
                    "core_name": core.name,
                    "cluster_id": core.cluster_id,
                    "budget": core.memory_budget,
                    "used": used,
                    "overflow": overflow_value,
                    "assigned_tasks": assigned_tasks,
                }
            )

        cluster_memory = []
        for cluster in problem.clusters:
            cluster_core_ids = [c.id for c in problem.cores if c.cluster_id == cluster.id]
            assigned_tasks = sorted(
                {
                    task.id
                    for task in problem.tasks
                    for core_id in cluster_core_ids
                    if num(x[task.id][core_id]) == 1
                }
            )
            used = sum(tasks_by_id[task_id].memory for task_id in assigned_tasks)
            overflow_value = num(cluster_overflow[cluster.id]) or 0

            cluster_memory.append(
                {
                    "cluster_id": cluster.id,
                    "cluster_name": cluster.name,
                    "budget": cluster.memory_budget,
                    "used": used,
                    "overflow": overflow_value,
                    "assigned_tasks": assigned_tasks,
                }
            )

        return {
            "solver": "CBC",
            "status": status_str,
            "feasible": True,
            "objective": num(model.objective),
            "makespan": num(cmax),
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
        }