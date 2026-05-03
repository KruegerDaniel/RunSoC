import logging
from timeit import default_timer as timer

from scheduling.base_solver import BaseSolver
from scheduling.extractor import build_solution_response
from scheduling.ga.ga_model import GaModel
from schemas.schemas import ProblemInstance
from schemas.solver_result import SolverResult

logger = logging.getLogger(__name__)


class GASolverService(BaseSolver):
    name = "GA"

    def __init__(self, ga_properties: dict | None = None, time_limit_seconds: int = 5000):
        self.ga_properties = ga_properties or self._default_ga_properties()
        self.time_limit_seconds = time_limit_seconds

    @staticmethod
    def _default_ga_properties() -> dict:
        return {
            "num_generations": 1000,
            "num_parents_mating": 20,
            "sol_per_pop": 80,
            "parent_selection_type": "tournament",
            "keep_parents": 1,
            "crossover_type": "single_point",
            "K_tournament": 3,
            "mutation_type": "random",
            "mutation_percent_genes": 10,
        }

    def solve(self, problem: ProblemInstance):
        model = GaModel(problem, time_limit_seconds=self.time_limit_seconds)

        logger.info(
            "GA solve started | jobs=%s | job_dependencies=%s | cores=%s | clusters=%s | time_limit=%s",
            len(problem.jobs),
            len(problem.job_dependencies),
            len(problem.cores),
            len(problem.clusters),
            self.time_limit_seconds,
        )

        start = timer()
        decoded = model.solve(self.ga_properties)
        runtime_seconds = timer() - start
        decoded["runtime_seconds"] = runtime_seconds

        status = "FEASIBLE"
        feasible = True

        if decoded.get("constraint_violation", 0) > 0:
            status = "FEASIBLE_WITH_CONSTRAINT_VIOLATIONS"

        logger.info(
            "GA solve finished | status=%s | runtime_seconds=%.4f | gens=%d | strict_chain_violation=%s",
            status,
            runtime_seconds,
            self.ga_properties["num_generations"],
            decoded.get("strict_chain_violation", 0),
        )

        normalized_result = self._to_normalized_result(
            problem_instance=problem,
            decoded=decoded,
            status=status,
            feasible=feasible,
        )

        return build_solution_response(problem, normalized_result)

    @staticmethod
    def _to_normalized_result(
        problem_instance: ProblemInstance,
        decoded: dict,
        status: str,
        feasible: bool,
    ) -> SolverResult:
        job_assignment = decoded["job_assignment"]
        starts = decoded["starts"]
        finishes = decoded["finishes"]

        return SolverResult(
            solver="GA",
            status=status,
            feasible=feasible,
            objective=decoded["total_cost"],
            makespan=decoded["cmax"],
            job_assignment=job_assignment,
            starts=starts,
            finishes=finishes,
            core_overflows=decoded["core_overflows"],
            cluster_overflows=decoded["cluster_overflows"],
            raw_status=1,
            runtime_seconds=decoded["runtime_seconds"],
            metadata={
                "fitness": decoded.get("fitness"),
                "comm_cost": decoded.get("comm_cost"),
                "priority_order": decoded.get("priority_order"),
                "strict_chain_violation": decoded.get("strict_chain_violation", 0),
                "precedence_violation": decoded.get("precedence_violation", 0),
                "core_overlap_violation": decoded.get("core_overlap_violation", 0),
                "constraint_violation": decoded.get("constraint_violation", 0),
                "constraint_violation_cost": decoded.get("constraint_violation_cost", 0),
                "ga_metadata": decoded.get("ga_metadata", {}),
                **decoded.get("metadata", {}),
            },
        )