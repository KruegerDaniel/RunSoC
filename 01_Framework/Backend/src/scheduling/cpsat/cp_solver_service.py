from ortools.sat.python import cp_model

from schemas.schemas import ProblemInstance
from .model_builder import build_model_cpsat
from ..base_solver import BaseSolver


class CpSolverService(BaseSolver):
    name = "CPSAT"

    def __init__(self, time_limit_seconds: float = 5000.0, num_workers: int = 8):
        self.time_limit_seconds = time_limit_seconds
        self.num_workers = num_workers

    def solve(self, problem: ProblemInstance) -> dict:
        model, vars_dict = build_model_cpsat(problem)
        solver = cp_model.CpSolver()

        solver.parameters.max_time_in_seconds = self.time_limit_seconds
        solver.parameters.num_search_workers = self.num_workers

        # solver.parameters.log_search_progress = True

        status = solver.Solve(model)

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return self._extract_solution(solver, status, vars_dict, problem)
        elif status == cp_model.INFEASIBLE:
            return {"status": "INFEASIBLE", "message": "The problem has no mathematical solution."}
        else:
            return {"status": "UNKNOWN",
                    "message": "Solver timed out before finding a feasible solution."}

    def _extract_solution(self, solver: cp_model.CpSolver, status: int, vars_dict: dict,
                          problem: "ProblemInstance") -> dict:
        x = vars_dict["x"]
        s = vars_dict["s"]
        f = vars_dict["f"]
        cmax = vars_dict["cmax"]
        core_overflows = vars_dict["core_overflows"]
        cluster_overflows = vars_dict["cluster_overflows"]

        schedule = []
        for t in problem.tasks:
            task_id = t.id
            assigned_core = None

            for c in t.eligible_cores:
                if solver.BooleanValue(x[task_id, c]):
                    assigned_core = c
                    break

            start_time = solver.Value(s[task_id])
            finish_time = solver.Value(f[task_id])

            schedule.append({
                "task_id": task_id,
                "core_id": assigned_core,
                "start_time": start_time,
                "finish_time": finish_time,
                "duration": finish_time - start_time
            })

        core_overflows = {}
        for idx, core in enumerate(problem.cores):
            core_overflows[core.id] = solver.Value(core_overflows[idx])

        return {
            "status": solver.StatusName(status),  # "OPTIMAL" or "FEASIBLE"
            "objective_value": solver.ObjectiveValue(),
            "makespan": solver.Value(cmax),
            "core_overflows": core_overflows,
            "tasks": sorted(schedule, key=lambda i: i["start_time"])
            # Sort by start time for readability
        }
