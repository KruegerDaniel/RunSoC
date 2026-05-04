import logging
from timeit import default_timer as timer

import pulp

from schemas.schemas import ProblemInstance
from .effective_periods import calculate_effective_periods
from .feasability_model import build_feasibility_model

logger = logging.getLogger(__name__)


class FeasibilitySolverService:
    def __init__(self, time_limit_seconds: int = 10, threads: int = 4):
        self.time_limit_seconds = time_limit_seconds
        self.threads = threads

    def check_feasibility(self, problem: ProblemInstance) -> dict:
        start = timer()

        effective_periods = calculate_effective_periods(problem)

        model, y, max_util = build_feasibility_model(problem, effective_periods)

        solver = pulp.PULP_CBC_CMD(
            msg=False,
            timeLimit=self.time_limit_seconds,
            threads=self.threads
        )

        status_code = model.solve(solver)
        runtime_seconds = timer() - start

        status = pulp.LpStatus[status_code]
        feasible = status in {"Optimal", "Feasible"}

        logger.info("Feasibility Check | status=%s | runtime=%.4fs", status, runtime_seconds)

        if not feasible:
            return {
                "feasible": False,
                "reason": "Hardware cannot support task set (Utilization > 100% or Memory Exceeded)",
                "runtime_seconds": runtime_seconds
            }

        # Extract successful task mapping
        task_assignment = {}
        for t in problem.tasks:
            assigned_core = next(
                (c.id for c in problem.cores if pulp.value(y[t.id][c.id]) == 1),
                None
            )
            task_assignment[t.id] = assigned_core

        return {
            "feasible": True,
            "max_core_utilization": pulp.value(max_util),
            "task_assignment": task_assignment,
            "runtime_seconds": runtime_seconds
        }
