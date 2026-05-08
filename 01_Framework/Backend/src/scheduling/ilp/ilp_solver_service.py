import logging
from timeit import default_timer as timer

import pulp

from scheduling.base_solver import BaseSolver
from scheduling.extractor import build_solution_response
from scheduling.ilp.ilp_model_builder import build_model
from schemas.schemas import ProblemInstance
from schemas.solver_result import SolverResult
from utils.numerical_util import clean_num

logger = logging.getLogger(__name__)


class IlpSolverService(BaseSolver):
    name = "CBC"

    def __init__(self, time_limit_seconds: int = 30, keep_files: bool = False, threads: int = 8):
        self.time_limit_seconds = time_limit_seconds
        self.keep_files = keep_files
        self.threads = threads

    def solve(self, problem: ProblemInstance, hints: dict = None) -> dict:
        logger.info(
            "CBC model building started | jobs=%s | job_dependencies=%s | cores=%s | clusters=%s",
            len(problem.jobs),
            len(problem.job_dependencies),
            len(problem.cores),
            len(problem.clusters),
        )
        startTime = timer()
        model, variables = build_model(problem)
        runtime_model_building_seconds = timer() - startTime

        logger.info(
            "CBC solve started | jobs=%s | job_dependencies=%s | cores=%s | clusters=%s | time_limit=%s | threads=%s",
            len(problem.jobs),
            len(problem.job_dependencies),
            len(problem.cores),
            len(problem.clusters),
            self.time_limit_seconds,
            self.threads,
        )

        solver = pulp.PULP_CBC_CMD(
            msg=True,
            keepFiles=self.keep_files,
            logPath="cbc.log" if self.keep_files else None,
            timeLimit=self.time_limit_seconds,
            threads=self.threads,
        )

        start_solve = timer()
        status_code = model.solve(solver)
        runtime_seconds = timer() - startTime
        solve_time = timer() - start_solve

        status = pulp.LpStatus[status_code]

        logger.info(
            "CBC solve finished | status=%s | raw_status=%s | runtime_seconds=%.4f",
            status,
            status_code,
            runtime_seconds,
        )

        normalized_result = self._to_normalized_result(
            model=model,
            vars_dict=variables,
            status_code=status_code,
            problem_instance=problem,
            metadata={
                "runtime_seconds": runtime_seconds,
                "model_building_seconds": runtime_model_building_seconds,
                "solve_time": solve_time,
            },
        )

        return build_solution_response(problem, normalized_result)

    @classmethod
    def _to_normalized_result(
            cls,
            model,
            status_code: int,
            vars_dict: dict,
            problem_instance: ProblemInstance,
            metadata=None,
    ) -> SolverResult:
        if metadata is None:
            metadata = {}

        status = pulp.LpStatus[status_code]
        feasible = status in {"Optimal", "Feasible"}

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
                metadata=metadata,
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
                    if cls._solved_binary(x[job.id][core_id])
                ),
                None,
            )

            job_assignment[job.id] = assigned_core

        starts = {
            job.id: cls._solved_number(s[job.id])
            for job in problem_instance.jobs
        }

        finishes = {
            job.id: cls._solved_number(f[job.id])
            for job in problem_instance.jobs
        }

        makespan = max(finishes.values()) if finishes else 0

        raw_core_overflows = vars_dict["core_overflow"]
        core_overflows = {
            core.id: cls._solved_number(raw_core_overflows[core.id], default=0)
            for core in problem_instance.cores
        }

        raw_cluster_overflows = vars_dict["cluster_overflow"]
        cluster_overflows = {
            cluster.id: cls._solved_number(
                raw_cluster_overflows[cluster.id],
                default=0,
            )
            for cluster in problem_instance.clusters
        }

        return SolverResult(
            solver=cls.name,
            status=status,
            feasible=True,
            objective=cls._solved_number(model.objective),
            makespan=makespan,
            job_assignment=job_assignment,
            starts=starts,
            finishes=finishes,
            core_overflows=core_overflows,
            cluster_overflows=cluster_overflows,
            raw_status=status_code,
            runtime_seconds=metadata.get("runtime_seconds", 0),
            metadata=metadata,
        )

    @staticmethod
    def _solved_number(expr, digits: int = 6, default=None):
        value = pulp.value(expr)

        if value is None:
            return default

        return clean_num(value, digits)

    @staticmethod
    def _solved_binary(var, tol: float = 1e-6) -> bool:
        value = pulp.value(var)
        return value is not None and value >= 1 - tol
