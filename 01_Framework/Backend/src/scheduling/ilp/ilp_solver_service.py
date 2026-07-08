import logging
from timeit import default_timer as timer

import pulp

from scheduling.base_solver import BaseSolver
from scheduling.extractor import build_solution_response
from scheduling.ilp.ilp_model_builder import build_model
from scheduling.metrics import (
    compute_deadline_violation,
    compute_communication_penalty,
    compute_memory_penalty,
)
from schemas.schemas import ProblemInstance
from schemas.solver_result import SolverResult, ObjectiveBreakdown
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
            "CBC model building started | jobs=%s | job_dependencies=%s | cores=%s | clusters=%s | total_time_limit=%s",
            len(problem.jobs),
            len(problem.job_dependencies),
            len(problem.cores),
            len(problem.clusters),
            self.time_limit_seconds,
        )

        start_time = timer()
        model, variables = build_model(problem)
        runtime_model_building_seconds = timer() - start_time

        remaining_time = self.time_limit_seconds - runtime_model_building_seconds

        if remaining_time <= 0:
            runtime_seconds = timer() - start_time
            logger.warning(
                "CBC model build exhausted time limit | model_building_seconds=%.4f | time_limit=%s",
                runtime_model_building_seconds,
                self.time_limit_seconds,
            )
            normalized_result = self._unsolved_result(
                problem_instance=problem,
                status="MODEL_BUILD_TIMEOUT",
                raw_status=None,
                runtime_seconds=runtime_seconds,
                metadata={
                    "runtime_seconds": runtime_seconds,
                    "model_building_seconds": runtime_model_building_seconds,
                    "solve_time": 0.0,
                    "timeout_seconds": self.time_limit_seconds,
                    "remaining_solver_time": 0.0,
                    "reason": "Model construction exceeded the total CBC time limit.",
                },
            )
            return build_solution_response(problem, normalized_result)

        # Reserve a small serialization/return buffer inside the CBC time budget.
        # CBC may overrun its own timeLimit during cleanup, so the outer runner
        # should still enforce the hard wall-clock limit.
        cbc_time_limit = max(1, int(remaining_time))

        logger.info(
            "CBC solve started | jobs=%s | job_dependencies=%s | cores=%s | clusters=%s | "
            "total_time_limit=%s | cbc_time_limit=%s | threads=%s",
            len(problem.jobs),
            len(problem.job_dependencies),
            len(problem.cores),
            len(problem.clusters),
            self.time_limit_seconds,
            cbc_time_limit,
            self.threads,
        )

        solver_kwargs = {
            "msg": False,
            "keepFiles": self.keep_files,
            "logPath": "cbc.log" if self.keep_files else None,
            "timeLimit": cbc_time_limit,
            "threads": self.threads,
        }

        try:
            solver = pulp.PULP_CBC_CMD(**solver_kwargs, timeMode="elapsed")
        except TypeError:
            solver = pulp.PULP_CBC_CMD(**solver_kwargs)

        start_solve = timer()
        status_code = model.solve(solver)
        runtime_seconds = timer() - start_time
        solve_time = timer() - start_solve

        status = pulp.LpStatus[status_code]

        logger.info(
            "CBC solve finished | status=%s | raw_status=%s | runtime_seconds=%.4f | solve_time=%.4f",
            status,
            status_code,
            runtime_seconds,
            solve_time,
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
                "timeout_seconds": self.time_limit_seconds,
                "remaining_solver_time": remaining_time,
                "cbc_time_limit": cbc_time_limit,
            },
        )

        return build_solution_response(problem, normalized_result)

    @classmethod
    def _unsolved_result(
        cls,
        problem_instance: ProblemInstance,
        status: str,
        raw_status,
        runtime_seconds: float,
        metadata=None,
    ) -> SolverResult:
        """Create a schema-complete unsolved result.

        The current SolverResult schema requires task_assignment. Unsolved CBC
        results do not have an assignment, so both task_assignment and
        job_assignment are returned as empty dictionaries.
        """
        return SolverResult(
            solver=cls.name,
            status=status,
            feasible=False,
            objective=None,
            objective_breakdown=ObjectiveBreakdown(
                memory_penalty=None,
                communication_penalty=None,
                deadline_penalty=None,
            ),
            makespan=None,
            task_assignment={},
            job_assignment={},
            starts={},
            finishes={},
            core_overflows={},
            cluster_overflows={},
            raw_status=raw_status,
            runtime_seconds=runtime_seconds,
            metadata=metadata or {},
        )

    @classmethod
    def _extract_task_assignment(
        cls,
        vars_dict: dict,
        problem_instance: ProblemInstance,
        job_assignment: dict,
    ) -> dict:
        """Extract task-level assignment for the normalized SolverResult.

        Prefer the task allocation variables if the model builder returns them.
        Fall back to the first scheduled job assignment per task.
        """
        y_alloc = vars_dict.get("y_alloc")
        task_assignment = {}

        if y_alloc is not None:
            for task in problem_instance.tasks:
                assigned_core = next(
                    (
                        core_id
                        for core_id in task.eligible_cores
                        if cls._solved_binary(y_alloc[task.id][core_id])
                    ),
                    None,
                )
                task_assignment[task.id] = assigned_core

            return task_assignment

        for job in problem_instance.jobs:
            if job.task_id not in task_assignment:
                task_assignment[job.task_id] = job_assignment.get(job.id)

        for task in problem_instance.tasks:
            task_assignment.setdefault(task.id, None)

        return task_assignment

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
            return cls._unsolved_result(
                problem_instance=problem_instance,
                status=status,
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

        task_assignment = cls._extract_task_assignment(
            vars_dict=vars_dict,
            problem_instance=problem_instance,
            job_assignment=job_assignment,
        )

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

        memory_penalty = compute_memory_penalty(
            problem_instance,
            core_overflows,
            cluster_overflows,
        )

        communication_penalty = compute_communication_penalty(
            problem_instance,
            job_assignment,
        )

        deadline_penalty = compute_deadline_violation(
            problem_instance,
            finishes,
        )

        return SolverResult(
            solver=cls.name,
            status=status,
            feasible=True,
            objective=cls._solved_number(model.objective),
            objective_breakdown=ObjectiveBreakdown(
                memory_penalty=memory_penalty,
                communication_penalty=communication_penalty,
                deadline_penalty=deadline_penalty,
            ),
            makespan=makespan,
            task_assignment=task_assignment,
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
