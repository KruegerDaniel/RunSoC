import pulp

from scheduling.base_solver import BaseSolver
from scheduling.ilp.model_builder import build_model
from schemas.schemas import ProblemInstance


class IlpSolverService(BaseSolver):
    name = "ILP"

    def __init__(self):
        self.time_limit_seconds = 100  # add config class
        self.keepFiles = False

    def solve(self, problem: ProblemInstance) -> dict:
        model, variables = build_model(problem)

        solver = pulp.PULP_CBC_CMD(msg=True, keepFiles=self.keepFiles, logPath="cbc.log",
                                   timeLimit=self.time_limit_seconds)
        status = model.solve(solver)

        return self._extract_solution(problem, model, variables, status)

    def _extract_solution(self, problem, model, variables, status):
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

            schedule.append({
                "task": task.id,
                "start_time": int(round(pulp.value(s[task.id]))),
                "finish_time": int(round(pulp.value(f[task.id]))),
                "core": assigned_core,
                "eligible_time": eligible_time,
            })

        schedule.sort(key=lambda e: (e["start_time"], e["core"], e["task"]))

        return {
            "status": pulp.LpStatus[status],
            "objective": pulp.value(model.objective),
            "makespan": int(round(pulp.value(cmax))),
            "schedule": schedule,
        }
