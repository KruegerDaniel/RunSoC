import logging
from timeit import default_timer as timer

from ortools.sat.python import cp_model

from schemas.schemas import ProblemInstance
from .effective_periods import calculate_effective_periods
from .feasability_model import build_feasibility_model, UTILIZATION_SCALE

logger = logging.getLogger(__name__)


class FeasibilitySolverService:
    def __init__(self, time_limit_seconds: int = 10, threads: int = 4):
        self.time_limit_seconds = time_limit_seconds
        self.threads = threads

    def check_feasibility(self, problem: ProblemInstance) -> dict:
        start = timer()

        effective_periods = calculate_effective_periods(problem)

        model, y, max_util = build_feasibility_model(problem, effective_periods)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.time_limit_seconds
        solver.parameters.num_search_workers = self.threads
        solver.parameters.log_search_progress = False

        logger.info("CP-SAT solve started | time_limit=%s | threads=%s", self.time_limit_seconds, self.threads)

        status_code = solver.Solve(model)
        runtime_seconds = timer() - start

        status = solver.StatusName(status_code)
        feasible = status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        logger.info("Feasibility Check | status=%s | runtime=%.4fs", status, runtime_seconds)

        if not feasible:
            return {
                "feasible": False,
                "reason": "Hardware cannot support task set (Utilization > 100%) or timeout",
                "runtime_seconds": runtime_seconds
            }

        # Extract successful task mapping
        task_assignment = {}
        for t in problem.tasks:
            assigned_core = next(
                (c.id for c in problem.cores if solver.BooleanValue(y[t.id, c.id])),
                None
            )
            task_assignment[t.id] = assigned_core

        float_max_utilization = solver.Value(max_util) / UTILIZATION_SCALE

        return {
            "feasible": True,
            "max_core_utilization": float_max_utilization,
            "task_assignment": task_assignment,
            "runtime_seconds": runtime_seconds
        }