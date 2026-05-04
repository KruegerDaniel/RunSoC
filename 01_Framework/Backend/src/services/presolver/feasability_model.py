import math

from ortools.sat.python import cp_model

from schemas.schemas import ProblemInstance

UTILIZATION_SCALE = 1_000_000


def build_feasibility_model(problem: ProblemInstance, effective_periods: dict[str, float]):
    model = cp_model.CpModel()

    tasks = {t.id: t for t in problem.tasks}
    cores = {c.id: c for c in problem.cores}

    task_ids = list(tasks.keys())
    core_ids = list(cores.keys())

    # --- Decision Variables ---
    # y[t][c] = True if task t is assigned to core c
    y = {}
    for t_id in task_ids:
        for c in core_ids:
            y[t_id, c] = model.NewBoolVar(f"assign_{t_id}_{c}")

    # max_utilization allows us to load-balance the cores
    max_utilization = model.NewIntVar(0, UTILIZATION_SCALE, "max_utilization")

    # --- Constraints ---

    # Exact Assignment & Eligibility
    for t_id in task_ids:
        eligible = tasks[t_id].eligible_cores
        assigned_vars = []

        for c in core_ids:
            if c in eligible:
                assigned_vars.append(y[t_id, c])
            else:
                # Force ineligible assignments to False
                model.Add(y[t_id, c] == 0)

        # Task must be assigned to exactly one eligible core
        if assigned_vars:
            model.AddExactlyOne(assigned_vars)

    # Core Utilization (The CPU Check)
    for c in core_ids:
        core_utilization_terms = []

        for t_id in task_ids:
            period = effective_periods.get(t_id, 0)
            if period > 0 and c in tasks[t_id].eligible_cores:
                # Calculate raw float utilization
                util_float = (tasks[t_id].duration * cores[c].wcet_scale) / period

                # Scale to integer. We use math.ceil to ensure we don't
                # under-approximate utilization due to truncation.
                scaled_util = math.ceil(util_float * UTILIZATION_SCALE)

                # Add the weighted term: scaled_util * y[t_id, c]
                core_utilization_terms.append(scaled_util * y[t_id, c])

        if core_utilization_terms:
            core_total_util = sum(core_utilization_terms)

            # Hard limit: Core cannot exceed 100% (UTILIZATION_SCALE)
            model.Add(core_total_util <= UTILIZATION_SCALE)

            # Tie this to the objective variable for load balancing
            model.Add(max_utilization >= core_total_util)

    # --- Objective ---
    # Minimize the maximum utilization across all cores (Load Balancing)
    model.Minimize(max_utilization)

    return model, y, max_utilization
