from timeit import default_timer as timer

from scheduling.base_solver import BaseSolver
from scheduling.extractor import build_solution_response
from scheduling.ga.ga_model import GaModel
from schemas.schemas import ProblemInstance
from schemas.solver_result import SolverResult


class GASolverService(BaseSolver):
    name = "GA"

    def __init__(self, ga_properties: dict | None = None):
        self.ga_properties = ga_properties or self._default_ga_properties()

    @staticmethod
    def _default_ga_properties() -> dict:
        return {
            "num_generations": 500,
            "num_parents_mating": 20,
            "sol_per_pop": 80,
            "parent_selection_type": "tournament",
            "keep_parents": 1,
            "crossover_type": "single_point",
            "K_tournament": 3,
            "mutation_type": "random",
            "mutation_percent_genes": 10,
            # "random_seed": 42,
        }

    def solve(self, problem: ProblemInstance):
        model = GaModel(problem)

        start = timer()
        decoded = model.solve(self.ga_properties)
        end = timer()
        decoded["runtime_seconds"] = end - start
        normalized_result = self._to_normalized_result(problem, decoded)

        return build_solution_response(problem, normalized_result)

    @staticmethod
    def _to_normalized_result(
            problem_instance: ProblemInstance,
            decoded: dict,
    ) -> SolverResult:
        assignment = decoded["assignment"]
        starts = decoded["starts"]
        finishes = decoded["finishes"]

        return SolverResult(
            solver="GA",
            status="FEASIBLE",
            feasible=True,
            objective=decoded["total_cost"],
            makespan=decoded["cmax"],
            assignment=assignment,
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
                **decoded.get("metadata", {}),
            }
        )
