import pulp
from schemas.schemas import ProblemInstance


def build_feasibility_model(problem: ProblemInstance, effective_periods: dict[str, float]):
    model = pulp.LpProblem("MPSoC_Feasibility", pulp.LpMinimize)

    tasks = {t.id: t for t in problem.tasks}
    cores = {c.id: c for c in problem.cores}
    clusters = {c.id: c for c in problem.clusters}

    task_ids = list(tasks.keys())
    core_ids = list(cores.keys())
    cluster_ids = list(clusters.keys())

    cluster_to_cores = {cl_id: [] for cl_id in cluster_ids}
    for c in problem.cores:
        cluster_to_cores[c.cluster_id].append(c.id)

    # --- Decision Variables ---
    # y[t][c] = 1 if task t is assigned to core c
    y = pulp.LpVariable.dicts("assign", (task_ids, core_ids), cat="Binary")

    # max_utilization allows us to load-balance the cores
    max_utilization = pulp.LpVariable("max_utilization", lowBound=0, upBound=1.0, cat="Continuous")

    # --- Constraints ---

    # 1. Exact Assignment & Eligibility
    for t_id in task_ids:
        eligible = tasks[t_id].eligible_cores
        model += pulp.lpSum(y[t_id][c] for c in eligible) == 1, f"assign_once_{t_id}"
        for c in core_ids:
            if c not in eligible:
                model += y[t_id][c] == 0, f"ineligible_{t_id}_{c}"

    # 4. Core Utilization (The CPU Check)
    # Utilization U = WCET / Period. Sum of U on a core must be <= 1.0
    for c in core_ids:
        core_utilization_expr = pulp.lpSum(
            ((tasks[t_id].duration * cores[c].wcet_scale) / effective_periods[t_id]) * y[t_id][c]
            for t_id in task_ids if effective_periods.get(t_id, 0) > 0
        )

        # Hard limit: Core cannot exceed 100% processing capacity
        model += core_utilization_expr <= 1.0, f"utilization_cap_{c}"

        # Tie this to the objective variable for load balancing
        model += max_utilization >= core_utilization_expr, f"track_max_util_{c}"

    # --- Objective ---
    # Minimize the maximum utilization across all cores (Load Balancing)
    model += max_utilization

    return model, y, max_utilization