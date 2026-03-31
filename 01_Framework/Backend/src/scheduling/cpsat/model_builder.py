from ortools.sat.python import cp_model

from schemas.schemas import ProblemInstance


def build_model_cpsat(problem: ProblemInstance):
    model = cp_model.CpModel()

    tasks = {t.id: t for t in problem.tasks}
    cores = {c.id: c for c in problem.cores}
    task_ids = list(tasks.keys())
    core_ids = list(cores.keys())

    # add memory delays in future
    horizon = sum(t.duration for t in problem.tasks) + sum(c.latency for c in problem.communications)

    x = {} # x[t,c]: True if task t assigned to core c
    s = {} # Start time for task t
    f = {} # Finish time for task t
    intervals_per_core = {c: [] for c in core_ids}

    for i in task_ids:
        s[i] = model.NewIntVar(0, horizon, f"s_{i}")
        f[i] = model.NewIntVar(0, horizon, f"f_{i}")
        duration = tasks[i].duration

        assigned_core_vars = []

        for c in core_ids:
            if c in tasks[i].eligible_cores:
                # binary assignment
                x[i,c] = model.NewBoolVar(f"x_{i}_{c}")
                assigned_core_vars.append(x[i,c])

                s_local = model.NewIntVar(0, horizon, f"s_{i}_{c}")
                f_local = model.NewIntVar(0, horizon, f"f_{i}_{c}")

                interval = model.NewOptionalIntervalVar(s_local, duration, f_local, x[i,c], f"interval_{i}_{c}")
                intervals_per_core[c].append(interval)

                model.Add(s[i] == s_local).OnlyEnforceIf(x[i,c])
                model.Add(f[i] == f_local).OnlyEnforceIf(x[i,c])

        # Constraint: Task assigned to exactly one eligible core
        model.AddExactlyOne(assigned_core_vars)

    # Precedence Constraint
    for dep in problem.dependencies:
        model.Add(s[dep.successor] >= f[dep.predecessor])

    # No overlap on core
    for c in core_ids:
        model.AddNoOverlap(intervals_per_core[c])

    # Memory soft budget constraint
    overflows = []
    for c in core_ids:
        max_possible_mem = sum(tasks[t].memory for t in task_ids if c in tasks[t].eligible_cores)

        overflow = model.NewIntVar(0, max_possible_mem, f"overflow_{c}")
        overflows.append(overflow)

        used_memory = sum(tasks[t].memory * x[t,c] for t in task_ids if c in tasks[t].eligible_cores)

        # Since overflow is minimized in objective, will drop to 0 if under budget
        model.Add(overflow >= used_memory - cores[c].memory_budget)

    # Communication cross-core penalty
    comm_penalties = []
    for comm in problem.communications:
        i, j = comm.source, comm.target
        latency = comm.latency

        penalty = model.NewIntVar(0, latency, f"comm_penalty_{i}_{j}")

        for c in core_ids:
            if c in tasks[i].eligible_cores and c in tasks[j].eligible_cores:
                model.Add(penalty == 0).OnlyEnforceIf([x[i,c], x[j,c]])

        comm_penalties.append(penalty)

    cmax = model.NewIntVar(0, horizon, "cmax")
    model.AddMaxEquality(cmax, [f[i] for i in task_ids])

    model.Minimize(
        cmax
        + int(problem.memory_penalty_weight) * sum(overflows)
        + sum(comm_penalties)
    )

    return model, {
        "x": x,
        "s": s,
        "f": f,
        "cmax": cmax,
        "overflows": overflows
    }