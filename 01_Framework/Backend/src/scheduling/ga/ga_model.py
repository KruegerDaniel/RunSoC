import bisect
import heapq
import logging
import time
from collections import defaultdict
from typing import Dict, List, Tuple

import pygad

from schemas.schemas import ProblemInstance

logger = logging.getLogger(__name__)


class GaModel:
    def __init__(self, problem_instance: ProblemInstance, time_limit_seconds: int = 100):
        self.start_time = None
        self.max_generations = None

        self.problem_instance = problem_instance
        self.time_limit_seconds = time_limit_seconds

        self.jitter = getattr(self.problem_instance, "max_chain_jitter", 0)
        self.is_strict_start = (self.jitter == 0)

        # -----------------------------
        # Tasks & Jobs
        # -----------------------------
        self.tasks = {t.id: t for t in problem_instance.tasks}
        self.task_ids = [t.id for t in problem_instance.tasks]
        self.task_index: Dict[str, int] = {
            task_id: i for i, task_id in enumerate(self.task_ids)
        }

        self.jobs = {j.id: j for j in problem_instance.jobs}
        self.job_ids = [j.id for j in problem_instance.jobs]
        self.job_index: Dict[str, int] = {
            job_id: i for i, job_id in enumerate(self.job_ids)
        }

        # -----------------------------
        # Hardware
        # -----------------------------
        self.cores = {c.id: c for c in problem_instance.cores}
        self.core_ids = [c.id for c in problem_instance.cores]

        self.clusters = {cl.id: cl for cl in problem_instance.clusters}
        self.cluster_ids = [cl.id for cl in problem_instance.clusters]
        self.core_to_cluster = {c.id: c.cluster_id for c in problem_instance.cores}

        # -----------------------------
        # Eligible Cores (Task Level)
        # -----------------------------
        self.eligible_core_list_task: List[List[str]] = [
            self.tasks[task_id].eligible_cores[:] for task_id in self.task_ids
        ]

        # -----------------------------
        # Dependencies (Job Level for Scheduler)
        # -----------------------------
        self.predecessors: Dict[str, List[str]] = defaultdict(list)
        self.successors: Dict[str, List[str]] = defaultdict(list)

        for dep in problem_instance.job_dependencies:
            self.predecessors[dep.successor].append(dep.predecessor)
            self.successors[dep.predecessor].append(dep.successor)

        self.communications_path = problem_instance.communication_paths
        self.explicit_path_penalty = {
            (comm.source, comm.target): comm.penalty
            for comm in self.communications_path
        }

        self.terminal_jobs_by_chain_instance = self._find_terminal_jobs_by_chain_instance()
        self.terminal_job_ids = {
            job_id
            for terminal_jobs in self.terminal_jobs_by_chain_instance.values()
            for job_id in terminal_jobs
        }

        self.duration_cache = {}
        for job in problem_instance.jobs:
            self.duration_cache[job.id] = {}
            for core in problem_instance.cores:
                wcet_scale = getattr(core, "wcet_scale", 1.0) or 1.0
                self.duration_cache[job.id][core.id] = float(job.duration) * float(wcet_scale)

        # -----------------------------
        # Gene Space (Task Level Partitioning)
        # -----------------------------
        # Gene structure: First T genes for core choice, Last T genes for priority
        self.num_genes = 2 * len(self.tasks)
        self.gene_space = []

        # First T genes: assignment choice index (per task).
        for eligible in self.eligible_core_list_task:
            self.gene_space.append(list(range(len(eligible))))

        # Last T genes: priority value (per task).
        for _ in self.task_ids:
            self.gene_space.append({"low": 0.0, "high": 1.0})

    def solve(self, ga_properties):
        self.start_time = time.time()
        self.max_generations = ga_properties.get("max_generations", 500)

        ga = pygad.GA(
            **ga_properties,
            num_genes=self.num_genes,
            gene_space=self.gene_space,
            gene_type=self._gene_types(),
            fitness_func=self.fitness_func,
            on_generation=self.on_generation,
            random_mutation_max_val=1.0,
            random_mutation_min_val=0.0,
        )

        ga.run()

        best_solution, best_fitness, _ = ga.best_solution()

        decoded = self.decode_solution(best_solution)
        decoded["fitness"] = best_fitness
        decoded["ga_metadata"] = {
            "generations_completed": ga.generations_completed,
        }

        return decoded

    def decode_solution(self, solution, current_generation=0):
        # 1. Decode Task-Level Traits
        task_assignment = self._decode_task_assignment(solution)
        task_priority = self._decode_task_priority(solution)

        # 2. Inherit Traits to Jobs
        job_assignment = {
            job_id: task_assignment[self.jobs[job_id].task_id]
            for job_id in self.job_ids
        }
        priority_order = self._derive_job_priority_order(task_priority)

        # 3. Simulate Schedule
        starts, finishes = self._build_schedule(job_assignment, priority_order)

        # 4. Task-Level Cost Calculations
        core_overflows, cluster_overflows = self._calculate_mem(task_assignment)
        comm_cost = self._calculate_comm_cost(task_assignment)

        # 5. Job-Level Violations
        precedence_violation = self._calculate_precedence_violation(
            starts=starts,
            finishes=finishes,
        )

        deadline_violation = self._calculate_terminal_deadline_violation(finishes)

        same_core_overlap_violation = self._calculate_same_core_overlap_violation(starts, finishes, job_assignment)

        jitter_violation = self._calculate_jitter_violation(starts)

        violation = (
                precedence_violation
                + deadline_violation
                + same_core_overlap_violation
                + jitter_violation
        )

        # Increase violation cost in later generations
        base_weight = 100
        growth_factor = min(1.0, current_generation / self.max_generations)
        violation_weight = base_weight + (999900 * growth_factor)
        violation_cost = violation_weight * violation

        weight_scalars = self.problem_instance.memory_penalty_scale

        total_cost = (
                weight_scalars.get("core_overflow_scale", 1) * sum(core_overflows.values())
                + weight_scalars.get("cluster_overflow_scale", 1) * sum(cluster_overflows.values())
                + comm_cost
                + violation_cost
        )

        return {
            "job_assignment": job_assignment,
            "priority_order": priority_order,
            "starts": starts,
            "finishes": finishes,
            "core_overflows": core_overflows,
            "cluster_overflows": cluster_overflows,
            "comm_cost": comm_cost,
            "deadline_violation": deadline_violation,
            "precedence_violation": precedence_violation,
            "constraint_violation": violation,
            "constraint_violation_cost": violation_cost,
            "total_cost": total_cost,
        }

    # ------------------------------------------------------------------
    # PyGAD
    # ------------------------------------------------------------------

    def on_generation(self, ga_instance):
        elapsed = time.time() - self.start_time

        if ga_instance.generations_completed % 100 == 0:
            logger.debug(
                "Generation %d | time elapsed: %.2f",
                ga_instance.generations_completed,
                elapsed,
            )

        if elapsed >= self.time_limit_seconds:
            return "stop"

    def fitness_func(self, ga_instance, solution, solution_idx):
        decoded = self.decode_solution(solution, ga_instance.generations_completed)
        cost = decoded["total_cost"]
        return 1.0 / (1.0 + cost)

    def _gene_types(self):
        types = []
        for _ in range(len(self.tasks)):
            types.append(int)
        for _ in range(len(self.tasks)):
            types.append(float)
        return types

    # ------------------------------------------------------------------
    # Decoding (Task Level)
    # ------------------------------------------------------------------

    def _decode_task_assignment(self, solution) -> Dict[str, str]:
        assignment: Dict[str, str] = {}
        for idx, task_id in enumerate(self.task_ids):
            eligible_cores = self.eligible_core_list_task[idx]

            choice_idx = int(round(solution[idx]))
            choice_idx = max(0, min(choice_idx, len(eligible_cores) - 1))

            assignment[task_id] = eligible_cores[choice_idx]
        return assignment

    def _decode_task_priority(self, solution) -> Dict[str, float]:
        task_priority: Dict[str, float] = {}
        offset = len(self.task_ids)
        for idx, task_id in enumerate(self.task_ids):
            task_priority[task_id] = float(solution[idx + offset])
        return task_priority

    def _derive_job_priority_order(self, task_priority: Dict[str, float]) -> List[str]:
        prio_values = []
        for job_id in self.job_ids:
            job = self.jobs[job_id]
            t_prio = task_priority[job.task_id]
            # Fixed priority deterministic sort:
            # 1. Highest Task Priority (-t_prio)
            # 2. Earliest Release Time
            # 3. Job Index (Tie Breaker)
            prio_values.append((job_id, t_prio, float(job.release_time), self.job_index[job_id]))

        prio_values.sort(key=lambda x: (-x[1], x[2], x[3]))
        return [x[0] for x in prio_values]

    # ------------------------------------------------------------------
    # Schedule Builder (Remains Job Level)
    # ------------------------------------------------------------------

    def _build_schedule(
            self,
            assignment: Dict[str, str],
            priority_order: List[str],
    ) -> Tuple[Dict[str, float], Dict[str, float]]:
        starts: Dict[str, float] = {}
        finishes: Dict[str, float] = {}

        intervals_by_core: Dict[str, List[Tuple[float, float, str]]] = {
            core_id: [] for core_id in self.core_ids
        }

        # Forcibly schedule chain root jobs
        anchored_job_ids = set()

        if self.is_strict_start:
            for job_id in self.job_ids:
                job = self.jobs[job_id]

                if job.is_chain_root and job.chain_id is not None:
                    core_id = assignment[job_id]
                    duration = self.duration_cache[job_id][core_id]

                    start = float(job.release_time)
                    finish = start + duration

                    starts[job_id] = start
                    finishes[job_id] = finish
                    anchored_job_ids.add(job_id)

                    intervals_by_core[core_id].append((start, finish, job_id))

        for core_id in self.core_ids:
            intervals_by_core[core_id].sort(key=lambda item: (item[0], item[1], item[2]))

        priority_rank = {
            job_id: rank for rank, job_id in enumerate(priority_order)
        }

        remaining_preds = {
            job_id: len(self.predecessors.get(job_id, []))
            for job_id in self.job_ids
        }

        pred_max_finish = {
            job_id: 0.0 for job_id in self.job_ids
        }

        ready_heap = []

        for job_id in self.job_ids:
            if remaining_preds[job_id] == 0:
                heapq.heappush(
                    ready_heap,
                    (
                        self.jobs[job_id].release_time,
                        priority_rank[job_id],
                        self.job_index[job_id],
                        job_id,
                    ),
                )

        visited = set()

        while ready_heap:
            _, _, _, job_id = heapq.heappop(ready_heap)

            if job_id in visited:
                continue

            visited.add(job_id)

            job = self.jobs[job_id]

            if job_id not in anchored_job_ids:
                core_id = assignment[job_id]
                duration = self.duration_cache[job_id][core_id]

                earliest_start = max(
                    float(job.release_time),
                    pred_max_finish[job_id],
                )

                start = self._find_earliest_gap(
                    intervals=intervals_by_core[core_id],
                    earliest_start=earliest_start,
                    duration=duration,
                )
                finish = start + duration

                starts[job_id] = start
                finishes[job_id] = finish

                new_interval = (start, finish, job_id)
                bisect.insort(intervals_by_core[core_id], new_interval)

            finish = finishes[job_id]

            for successor in self.successors.get(job_id, []):
                if finish > pred_max_finish[successor]:
                    pred_max_finish[successor] = finish

                remaining_preds[successor] -= 1

                if remaining_preds[successor] == 0:
                    heapq.heappush(
                        ready_heap,
                        (
                            max(
                                self.jobs[successor].release_time,
                                pred_max_finish[successor],
                            ),
                            priority_rank[successor],
                            self.job_index[successor],
                            successor,
                        ),
                    )

        if len(visited) != len(self.job_ids):
            raise RuntimeError(
                "Cycle or unschedulable dependency graph during GA decoding"
            )

        return starts, finishes

    def _find_earliest_gap(
            self,
            intervals: List[Tuple[float, float, str]],
            earliest_start: float,
            duration: float,
    ) -> float:
        candidate = earliest_start

        for start, finish, _ in intervals:
            if candidate + duration <= start:
                return candidate

            if candidate < finish:
                candidate = finish

        return candidate

    # ------------------------------------------------------------------
    # Cost methods (Task Level)
    # ------------------------------------------------------------------

    def _calculate_mem(
            self,
            task_assignment: Dict[str, str],
    ) -> Tuple[Dict[str, float], Dict[str, float]]:
        mem_by_core = {core_id: 0.0 for core_id in self.core_ids}
        mem_by_cluster = {cluster_id: 0.0 for cluster_id in self.cluster_ids}

        for task_id, core_id in task_assignment.items():
            t_memory = self.tasks[task_id].memory

            mem_by_core[core_id] += t_memory

            cluster_id = self.core_to_cluster[core_id]
            mem_by_cluster[cluster_id] += t_memory

        core_overflow = {}
        cluster_overflow = {}

        for core_id in self.core_ids:
            core_overflow[core_id] = max(
                0.0,
                mem_by_core[core_id] - self.cores[core_id].memory_budget,
            )

        for cluster_id in self.cluster_ids:
            cluster_overflow[cluster_id] = max(
                0.0,
                mem_by_cluster[cluster_id] - self.clusters[cluster_id].memory_budget,
            )

        return core_overflow, cluster_overflow

    def _calculate_comm_cost(self, task_assignment: Dict[str, str]) -> float:
        explicit_path_penalty = self.explicit_path_penalty
        comm_penalty_weight = self.problem_instance.comms_penalty_weight
        intra_core_weight = comm_penalty_weight.get("intra_core_weight", 0)
        inter_core_weight = comm_penalty_weight.get("inter_core_weight", 0)
        inter_cluster_weight = comm_penalty_weight.get("inter_cluster_weight", 0)

        total = 0.0

        for dep in self.problem_instance.dependencies:
            i, j = dep.predecessor, dep.successor

            # Tasks without an assignment skipped (safety)
            if i not in task_assignment or j not in task_assignment:
                continue

            core_i, core_j = task_assignment[i], task_assignment[j]

            if (core_i, core_j) in explicit_path_penalty:
                total += explicit_path_penalty[(core_i, core_j)]
            elif core_i == core_j:
                total += intra_core_weight
            elif self.cores[core_i].cluster_id == self.cores[core_j].cluster_id:
                total += inter_core_weight
            else:
                total += inter_cluster_weight

        return total

    #################################################
    # Violation calculations (Job Level)
    ################################################
    def _calculate_terminal_deadline_violation(
            self,
            finishes: Dict[str, float],
    ) -> float:
        violation = 0.0

        for terminal_job_ids in self.terminal_jobs_by_chain_instance.values():
            for job_id in terminal_job_ids:
                deadline = self.jobs[job_id].absolute_deadline

                if deadline is None:
                    continue

                finish = finishes.get(job_id)

                if finish is None:
                    continue

                violation += max(0.0, finish - float(deadline))

        return violation

    def _calculate_precedence_violation(
            self,
            starts: Dict[str, float],
            finishes: Dict[str, float],
    ) -> float:
        violation = 0.0

        for dep in self.problem_instance.job_dependencies:
            pred_finish = finishes.get(dep.predecessor)
            succ_start = starts.get(dep.successor)

            if pred_finish is None or succ_start is None:
                continue

            if succ_start < pred_finish:
                violation += pred_finish - succ_start

        return violation

    def _constraint_violation_weight(self) -> float:
        return self.problem_instance.memory_penalty_scale.get(
            "constraint_violation_scale",
            self.problem_instance.memory_penalty_scale.get(
                "strict_chain_violation_scale",
                1_000_000,
            ),
        )

    def _calculate_same_core_overlap_violation(
            self,
            starts: Dict[str, float],
            finishes: Dict[str, float],
            assignment: Dict[str, str],
    ) -> float:
        intervals_by_core: Dict[str, List[Tuple[float, float, str]]] = {
            core_id: [] for core_id in self.core_ids
        }

        for job_id, core_id in assignment.items():
            start = starts.get(job_id)
            finish = finishes.get(job_id)

            if start is None or finish is None:
                continue

            intervals_by_core[core_id].append((float(start), float(finish), job_id))

        violation = 0.0

        for core_id, intervals in intervals_by_core.items():
            intervals.sort(key=lambda item: (item[0], item[1], item[2]))

            previous_finish = None

            for start, finish, job_id in intervals:
                if previous_finish is not None and start < previous_finish:
                    violation += previous_finish - start

                if previous_finish is None or finish > previous_finish:
                    previous_finish = finish

        return violation

    def _calculate_jitter_violation(self, starts: Dict[str, float]) -> float:
        if self.jitter is None or self.jitter <= 0:
            return 0.0

        violation = 0.0

        for job_id in self.job_ids:
            job = self.jobs[job_id]
            if job.is_chain_root and job.chain_id is not None:
                actual_start = starts.get(job_id)
                if actual_start is not None:
                    max_allowed_start = float(job.release_time) + self.jitter
                    if actual_start > max_allowed_start:
                        violation += (actual_start - max_allowed_start)

        return violation

    def _find_terminal_jobs_by_chain_instance(self) -> Dict[tuple[str, int], List[str]]:
        chain_to_terminal_task_id = {
            tc.id: tc.task_ids[-1]
            for tc in self.problem_instance.task_chains
            if tc.task_ids
        }

        terminal_jobs_by_chain_instance: Dict[tuple[str, int], List[str]] = defaultdict(list)

        for job_id, job in self.jobs.items():
            if job.chain_id is None or job.instance_index is None:
                continue

            terminal_task_id = chain_to_terminal_task_id.get(job.chain_id)

            if terminal_task_id is None:
                continue

            if job.task_id == terminal_task_id:
                terminal_jobs_by_chain_instance[
                    (job.chain_id, job.instance_index)
                ].append(job_id)

        return dict(terminal_jobs_by_chain_instance)