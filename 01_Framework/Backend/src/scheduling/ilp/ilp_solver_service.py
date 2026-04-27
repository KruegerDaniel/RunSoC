from timeit import default_timer as timer

import pulp

from scheduling.base_solver import BaseSolver
from scheduling.extractor import build_solution_response
from scheduling.ilp.model_builder import build_model
from schemas.schemas import ProblemInstance
from schemas.solver_result import SolverResult


class IlpSolverService(BaseSolver):
    name = "CBC"

    def __init__(self):
        self.time_limit_seconds = 100
        self.keep_files = False

    def solve(self, problem: ProblemInstance) -> dict:
        model, variables = build_model(problem)

        solver = pulp.PULP_CBC_CMD(
            msg=True,
            keepFiles=self.keep_files,
            logPath="cbc.log",
            timeLimit=self.time_limit_seconds,
        )
        start = timer()
        status = model.solve(solver)
        end = timer()

        normalized_result = self._to_normalized_result(problem, model, variables, status, {
            "runtime_seconds": end - start,
        })

        return build_solution_response(problem, normalized_result)

    @staticmethod
    def _value(value, digits: int = 6):
        raw = pulp.value(value)
        if raw is None:
            return None

        rounded = round(float(raw), digits)

        if abs(rounded - round(rounded)) < 10 ** (-digits):
            return int(round(rounded))

        return rounded

    @classmethod
    def _to_normalized_result(
            cls,
            problem_instance: ProblemInstance,
            model,
            variables: dict,
            status_code: int,
            metadata: dict,
    ) -> SolverResult:
        status = pulp.LpStatus[status_code]
        feasible = status in {"Optimal", "Feasible"}

        if not feasible:
            return SolverResult(
                solver=cls.name,
                status=status,
                feasible=False,
                objective=None,
                makespan=None,
                assignment={},
                starts={},
                finishes={},
                core_overflows={},
                cluster_overflows={},
                raw_status=status_code,
                runtime_seconds=metadata.get("runtime_seconds"),
            )
        x = variables["x"]

        assignment = {}
        for task in problem_instance.tasks:
            assigned_core = next(
                (core_id
                 for core_id in task.eligible_cores
                 if cls._value(x[task.id][core_id]) == 1
                 ),
                None,
            )
            assignment[task.id] = assigned_core

        starts = {
            task.id: cls._value(variables["s"][task.id]) for task in problem_instance.tasks
        }
        finishes = {
            task.id: cls._value(variables["f"][task.id]) for task in problem_instance.tasks
        }

        core_overflow = {

            core.id: cls._value(variables["core_overflow"][core.id]) or 0
            for core in problem_instance.cores
        }

        cluster_overflow = {
            cluster.id: cls._value(variables["cluster_overflow"][cluster.id]) or 0
            for cluster in problem_instance.clusters
        }

        return SolverResult(
            solver=cls.name,
            status=status,
            feasible=True,
            objective=cls._value(model.objective),
            makespan=cls._value(variables["cmax"]),

            assignment=assignment,
            starts=starts,
            finishes=finishes,
            core_overflows=core_overflow,
            cluster_overflows=cluster_overflow,
            raw_status=status_code,
            runtime_seconds=metadata.get("runtime_seconds"),
        )
