import logging
from timeit import default_timer as timer

from ortools.sat.python import cp_model

from schemas.schemas import ProblemInstance
from schemas.solver_result import SolverResult
from .model_builder import build_model_cpsat
from ..base_solver import BaseSolver
from ..extractor import build_solution_response

logger = logging.getLogger(__name__)


class CpSolverService(BaseSolver):
    name = "CPSAT"

    def __init__(self, time_limit_seconds: int = 5000, num_workers: int = 8):
        self.time_limit_seconds = time_limit_seconds
        self.num_workers = num_workers

    def solve(self, problem: ProblemInstance) -> dict:
        model, vars_dict = build_model_cpsat(problem)
        solver = cp_model.CpSolver()

        solver.parameters.max_time_in_seconds = self.time_limit_seconds
        solver.parameters.num_search_workers = self.num_workers

        logger.info(
            "CP-SAT solve started | jobs=%s | job_dependencies=%s | cores=%s | clusters=%s | time_limit=%s",
            len(problem.jobs),
            len(problem.job_dependencies),
            len(problem.cores),
            len(problem.clusters),
            self.time_limit_seconds,
        )

        # solver.parameters.log_search_progress = True

        start = timer()
        status_code = solver.Solve(model)
        runtime_seconds = timer() - start

        status = solver.status_name(status_code)

        logger.info(
            "CP-SAT solve finished | status=%s | raw_status=%s | runtime_seconds=%.4f",
            status,
            status_code,
            runtime_seconds,
        )

        normalized_result = self._to_normalized_result(
            solver=solver,
            status_code=status_code,
            vars_dict=vars_dict,
            problem_instance=problem,
            metadata={"runtime_seconds": runtime_seconds},
        )

        return build_solution_response(problem, normalized_result)

    @classmethod
    def _to_normalized_result(
            cls,
            solver: cp_model.CpSolver,
            status_code,
            vars_dict: dict,
            problem_instance: ProblemInstance,
            metadata: dict = None,
    ) -> SolverResult:
        if metadata is None:
            metadata = {}

        status = solver.status_name(status_code)
        feasible = status_code in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        time_scale = vars_dict["time_scale"]

        if not feasible:
            return SolverResult(
                solver=cls.name,
                status=status,
                feasible=False,
                objective=None,
                makespan=None,
                job_assignment={},
                starts={},
                finishes={},
                core_overflows={},
                cluster_overflows={},
                raw_status=status_code,
                runtime_seconds=metadata.get("runtime_seconds", 0),
                metadata={
                    "time_scale": time_scale,
                },
            )

        x = vars_dict["x"]
        s = vars_dict["s"]
        f = vars_dict["f"]

        job_assignment = {}

        for job in problem_instance.jobs:
            assigned_core = next(
                (
                    core_id
                    for core_id in job.eligible_cores
                    if (job.id, core_id) in x
                       and solver.BooleanValue(x[job.id, core_id])
                ),
                None,
            )

            job_assignment[job.id] = assigned_core

        starts = {
            job.id: solver.Value(s[job.id]) / time_scale
            for job in problem_instance.jobs
        }

        finishes = {
            job.id: solver.Value(f[job.id]) / time_scale
            for job in problem_instance.jobs
        }

        core_overflows = {
            core.id: solver.Value(vars_dict["core_overflows"][core.id])
            for core in problem_instance.cores
        }

        cluster_overflows = {
            cluster.id: solver.Value(vars_dict["cluster_overflows"][cluster.id])
            for cluster in problem_instance.clusters
        }

        makespan = solver.Value(vars_dict["cmax"]) / time_scale

        return SolverResult(
            solver=cls.name,
            status=status,
            feasible=True,
            objective=solver.ObjectiveValue(),
            makespan=makespan,
            job_assignment=job_assignment,
            starts=starts,
            finishes=finishes,
            core_overflows=core_overflows,
            cluster_overflows=cluster_overflows,
            raw_status=status_code,
            runtime_seconds=metadata.get("runtime_seconds", 0),
            metadata={
                "time_scale": time_scale,
                "best_objective_bound": solver.BestObjectiveBound(),
                "wall_time": solver.WallTime(),
                "num_conflicts": solver.NumConflicts(),
                "num_branches": solver.NumBranches(),
            },
        )
