from collections import defaultdict
from typing import Dict, List, Tuple

import pygad

from schemas.schemas import ProblemInstance


class GaModel:

    def __init__(self, problem_instance: ProblemInstance):
        self.problem_instance = problem_instance
        self.tasks = {t.id: t for t in problem_instance.tasks}
        self.task_ids = [t.id for t in problem_instance.tasks]

        self.cores = {c.id: c for c in problem_instance.cores}
        self.core_ids = [c.id for c in problem_instance.cores]
        self.task_index: Dict[str, int] = {tid: i for i, tid in enumerate(self.task_ids)}

        self.clusters = {cl.id: cl for cl in problem_instance.clusters}
        self.cluster_ids = [cl.id for cl in problem_instance.clusters]

        self.eligible_core_list: List[List[str]] = [
            self.tasks[tid].eligible_cores[:] for tid in self.task_ids
        ]

        self.predecessors: Dict[str, List[str]] = defaultdict(list)
        self.successors: Dict[str, List[str]] = defaultdict(list)
        for dep in problem_instance.dependencies:
            self.predecessors[dep.successor].append(dep.predecessor)
            self.successors[dep.predecessor].append(dep.successor)

        self.communications_path = problem_instance.communication_paths

        self.num_genes = 2 * len(self.tasks)
        # Defining gene space
        # Limiting values for PyGAD
        self.gene_space = []
        # Limit first T genes to eligible core range
        for eligible in self.eligible_core_list:
            self.gene_space.append(list(range(len(eligible))))
        # Limit last T genes to priority [0.0, 1.0)
        for _ in self.task_ids:
            self.gene_space.append({"low": 0.0, "high": 1.0})

    def solve(self, ga_properties):
        ga = pygad.GA(
            **ga_properties,
            num_genes=self.num_genes,
            gene_space=self.gene_space,
            gene_type=self._gene_types(),
            fitness_func=self.fitness_func,
            on_generation=self.on_generation,
        )

        ga.run()

        best_solution, best_fitness, _ = ga.best_solution()
        decoded = self.decode_solution(best_solution)
        decoded["fitness"] = best_fitness
        decoded["ga_metadata"] = {
            "generations_completed": ga.generations_completed,

        }
        return decoded

    def decode_solution(self, solution):
        assignment_list = self._decode_assignment(solution)
        priority_list = self._decode_priority_order(solution)

        starts, finishes = self._build_schedule(assignment_list, priority_list)

        c_max = max(finishes.values()) if finishes else 0
        core_overflows, cluster_overflows = self._calculate_mem(assignment_list)
        comm_cost = self._calculate_comm_cost(assignment_list)

        weight_scalars = self.problem_instance.memory_penalty_scale
        total_cost = (
                c_max
                + weight_scalars.get("core_overflow_scale", 1) * sum(core_overflows.values())
                + weight_scalars.get("cluster_overflow_scale", 1) * sum(cluster_overflows.values())
                + comm_cost
        )

        return {
            "assignment": assignment_list,
            "priority_order": priority_list,
            "starts": starts,
            "finishes": finishes,
            "cmax": c_max,
            "core_overflows": core_overflows,
            "cluster_overflows": cluster_overflows,
            "comm_cost": comm_cost,
            "total_cost": total_cost,
        }

    # PyGAD
    ######################################################################
    def fitness_func(self, ga_instance, solution, solution_idx):
        decoded = self.decode_solution(solution)
        cost = decoded["total_cost"]
        return 1.0 / (1.0 + cost)

    @staticmethod
    def on_generation(ga_instance: pygad.GA):
        """
        Log every 25 generations
        """
        if ga_instance.generations_completed % 25 == 0:
            best_solution, best_fitness, _ = ga_instance.best_solution()
            best_cost = (1.0 / best_fitness) - 1.0
            print(
                f"Generation {ga_instance.generations_completed:4d}"
                f"| best fitness = {best_fitness:.8f}"
                f"| approx best cost = {best_cost:.4f}"
            )

    def _gene_types(self):
        types = []
        for _ in range(len(self.tasks)):
            types.append(int)
        for _ in range(len(self.tasks)):
            types.append(float)
        return types

    # DECODING METHODS
    #######################################################################
    def _decode_assignment(self, solution) -> Dict[str, str]:
        """
        First T genes are assignment choice indices of each task eligible core list
        """
        assignment: Dict[str, str] = {}

        for idx, tid in enumerate(self.task_ids):
            eligible_cores = self.eligible_core_list[idx]

            # Convert choice to int and limit to [0, len(eligible)]
            choice_idx = int(round(solution[idx]))
            choice_idx = max(0, min(choice_idx, len(eligible_cores) - 1))

            assignment[tid] = eligible_cores[choice_idx]
        return assignment

    def _decode_priority_order(self, solution) -> List[str]:
        """
        Last T genes are priority (float) values. Higher value => higher priority
        """
        prio_values = []
        offset = len(self.task_ids)

        for idx, tid in enumerate(self.task_ids):
            prio_value = float(solution[idx + offset])
            prio_values.append((tid, prio_value))

        # sort by descending priority; task index as tiebreaker
        prio_values.sort(key=lambda x: (-x[1], self.task_index[x[0]]))
        return [tid for tid, _ in prio_values]

    def _build_schedule(
            self,
            assignment: Dict[str, str],
            priority_order: List[str]
    ) -> Tuple[Dict[str, float], Dict[str, float]]:
        """
        Scheduling decoder
        """
        unscheduled = set(self.task_ids)
        starts: Dict[str, int] = {}
        finishes: Dict[str, int] = {}

        core_available: Dict[str, int] = {cid: 0 for cid in self.core_ids}
        priority_rank = {tid: rank for rank, tid in enumerate(priority_order)}

        while unscheduled:
            ready = [
                tid for tid in unscheduled
                if all(pred in finishes for pred in self.predecessors.get(tid, []))
            ]

            if not ready:
                raise RuntimeError("No ready tasks found during decoding")

            ready.sort(key=lambda tid: priority_rank[tid])
            tid = ready[0]

            assigned_core = assignment[tid]
            pred_finish = 0
            if self.predecessors.get(tid):
                pred_finish = max(finishes[p] for p in self.predecessors[tid])
            min_start = getattr(self.tasks[tid], "min_start", 0)
            start = max(core_available[assigned_core], pred_finish, min_start)
            wcet_scale = getattr(self.cores[assigned_core], "wcet_scale", 1.0)
            finish = start + self.tasks[tid].duration * wcet_scale

            starts[tid] = start
            finishes[tid] = finish
            core_available[assigned_core] = finish
            unscheduled.remove(tid)

        return starts, finishes

    # COST METHODS
    ##########################################################################
    def _calculate_mem(self, assignment: Dict[str, str]) -> Tuple[
        Dict[str, float], Dict[str, float]]:
        mem_by_core = {cid: 0 for cid in self.core_ids}
        mem_by_cluster = {clid: 0 for clid in self.cluster_ids}
        for tid, cid in assignment.items():
            mem_by_core[cid] += self.tasks[tid].memory
            clid = self.cores[cid].cluster_id
            mem_by_cluster[clid] += self.tasks[tid].memory

        core_overflow = {}
        cluster_overflow = {}
        for cid in self.core_ids:
            core_overflow[cid] = max(0.0, mem_by_core[cid] - self.cores[cid].memory_budget)

        for clid in self.cluster_ids:
            cluster_overflow[clid] = max(0.0,
                                         mem_by_cluster[clid] - self.clusters[clid].memory_budget)

        return core_overflow, cluster_overflow

    def _calculate_comm_cost(self, assignment: Dict[str, str]) -> float:
        explicit_path_penalty = {
            (comm.source, comm.target): comm.penalty for comm in self.communications_path
        }
        comm_penalty_weight = self.problem_instance.comms_penalty_weight
        intra_core_weight = comm_penalty_weight.get("intra_core_weight", 0)
        inter_core_weight = comm_penalty_weight.get("inter_core_weight", 0)
        inter_cluster_weight = comm_penalty_weight.get("inter_cluster_weight", 0)

        total = 0.0

        for dep in self.problem_instance.dependencies:
            i, j = dep.predecessor, dep.successor
            core_i, core_j = assignment[i], assignment[j]
            if (core_i, core_j) in explicit_path_penalty:
                total += explicit_path_penalty[(core_i, core_j)]
            elif core_i == core_j:
                total += intra_core_weight
            elif self.cores[core_i].cluster_id == self.cores[core_j].cluster_id:
                total += inter_core_weight
            else:
                total += inter_cluster_weight

        return total

#
# if __name__ == "__main__":
#     problem = ProblemInstance(
#         tasks=[
#             Task(id="A", duration=3, memory=4, eligible_cores=["0", "1", "2", "3"]),
#             Task(id="B", duration=2, memory=5, eligible_cores=["0", "1"]),
#             Task(id="C", duration=4, memory=3, eligible_cores=["0", "1", "2", "3"]),
#             Task(id="D", duration=3, memory=4, eligible_cores=["0", "1", "2", "3"]),
#             Task(id="E", duration=2, memory=5, eligible_cores=["0", "1"]),
#             Task(id="F", duration=4, memory=3, eligible_cores=["0", "1", "2", "3"]),
#             Task(id="A2", duration=3, memory=4, eligible_cores=["0", "1", "2", "3"]),
#             Task(id="B2", duration=2, memory=5, eligible_cores=["0", "1"]),
#             Task(id="C2", duration=4, memory=3, eligible_cores=["0", "1", "2", "3"]),
#             Task(id="D2", duration=3, memory=4, eligible_cores=["0", "1", "2", "3"]),
#             Task(id="E2", duration=2, memory=5, eligible_cores=["0", "1"]),
#             Task(id="F2", duration=4, memory=3, eligible_cores=["0", "1", "2", "3"]),
#             Task(id="A3", duration=3, memory=4, eligible_cores=["0", "1", "2", "3"]),
#             Task(id="B3", duration=2, memory=5, eligible_cores=["0", "1"]),
#             Task(id="C3", duration=4, memory=3, eligible_cores=["0", "1", "2", "3"]),
#             Task(id="D3", duration=3, memory=4, eligible_cores=["0", "1", "2", "3"]),
#             Task(id="E3", duration=2, memory=5, eligible_cores=["0", "1"]),
#             Task(id="F3", duration=4, memory=3, eligible_cores=["0", "1", "2", "3"]),
#             Task(id="A4", duration=3, memory=4, eligible_cores=["0", "1", "2", "3"]),
#             Task(id="B4", duration=2, memory=5, eligible_cores=["0", "1"]),
#             Task(id="C4", duration=4, memory=3, eligible_cores=["0", "1", "2", "3"]),
#             Task(id="D4", duration=3, memory=4, eligible_cores=["0", "1", "2", "3"]),
#             Task(id="E4", duration=2, memory=5, eligible_cores=["0", "1"]),
#             Task(id="F4", duration=4, memory=3, eligible_cores=["0", "1", "2", "3"]),
#         ],
#         cores=[
#             Core(id="0", memory_budget=30),
#             Core(id="1", memory_budget=30),
#             Core(id="2", memory_budget=30),
#             Core(id="3", memory_budget=30),
#         ],
#         dependencies=[
#             Dependency(predecessor="A", successor="C"),
#             Dependency(predecessor="A", successor="B"),
#             Dependency(predecessor="C", successor="E"),
#             Dependency(predecessor="E", successor="F"),
#             Dependency(predecessor="A2", successor="C2"),
#             Dependency(predecessor="A2", successor="B2"),
#             Dependency(predecessor="C2", successor="E2"),
#             Dependency(predecessor="E2", successor="F2"),
#         ],
#         communications=[
#             CommunicationPath(source="A", target="C", latency=2),
#             CommunicationPath(source="A", target="B", latency=4),
#             CommunicationPath(source="C", target="E", latency=2),
#             CommunicationPath(source="E", target="F", latency=4),
#             CommunicationPath(source="A2", target="C2", latency=2),
#             CommunicationPath(source="A2", target="B2", latency=4),
#             CommunicationPath(source="C2", target="E2", latency=2),
#             CommunicationPath(source="E2", target="F2", latency=4),
#         ],
#         memory_penalty_weight=10.0,
#     )
#
#     start = time.perf_counter()
#     solver = GaModel(problem)
#     result = solver.solve(
#         {
#             "num_generations": 2000,
#             "num_parents_mating": 20,
#             "sol_per_pop": 80,
#             "parent_selection_type": "tournament",
#             "keep_parents": 1,
#             "crossover_type": "single_point",
#             "K_tournament": 3,
#             "mutation_type": "random",
#             "mutation_percent_genes": 10,
#             "random_seed": 42
#         }
#
#     )
#
#     finish = time.perf_counter()
#
#     print(f"\n Completed in {finish - start:0.4f} seconds")
#     print("Best schedule:")
#     print("Assignment:", result["assignment"])
#     print("Priority order:", result["priority_order"])
#     print("Starts:", result["starts"])
#     print("Finishes:", result["finishes"])
#     print("Makespan:", result["cmax"])
#     print("Overflow:", result["mem_overflow"])
#     print("Comm cost:", result["comm_cost"])
#     print("Total cost:", result["total_cost"])
