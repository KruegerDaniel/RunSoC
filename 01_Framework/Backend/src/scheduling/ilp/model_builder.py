import pulp

from schemas.schemas import ProblemInstance


def build_model(problem: ProblemInstance):
    model = pulp.LpProblem(name="test_problem")  # minimization problem

    tasks = {t.id: t for t in problem.tasks}
    cores = {c.id: c for c in problem.cores}

    task_ids = list(tasks.keys())
    core_ids = list(cores.keys())

    # Big M is the sum of all
    big_m = sum(t.duration for t in problem.tasks) + 1

    # Decision Variables
    x = pulp.LpVariable.dicts("allocs", (task_ids, core_ids), cat="Binary")
    s = pulp.LpVariable.dicts("start", task_ids, lowBound=0, cat="Integer")
    f = pulp.LpVariable.dicts("finish", task_ids, lowBound=0, cat="Integer")
    cmax = pulp.LpVariable("c_max", lowBound=0, cat="Integer")

    overflow = pulp.LpVariable.dicts("overflow", core_ids, lowBound=0, cat="Continuous")

    # Assignment constraints
    for i in task_ids:
        eligible = tasks[i].eligible_cores
        model += pulp.lpSum(x[i][c] for c in eligible) == 1  # only assign task once

        # do not assign task to non-affinity core
        for c in core_ids:
            if c not in eligible:
                model += x[i][c] == 0

    # Finish time definition
    for i in task_ids:
        model += f[i] == s[i] + tasks[i].duration

    # Precedence constraints
    for dep in problem.dependencies:
        model += s[dep.successor] >= f[dep.predecessor]

    # Makespan constraints
    for i in task_ids:
        model += cmax >= f[i]

    # Memory soft budget per core (To be expanded for cluster)
    for c in core_ids:
        model += (
                pulp.lpSum(tasks[i].memory * x[i][c] for i in task_ids) <= cores[c].memory_budget + overflow[c]
        )

    # No overlap on core constraint
    y = {}
    for idx1 in range(len(task_ids)):
        for idx2 in range(idx1 + 1, len(task_ids)):
            i = task_ids[idx1]
            j = task_ids[idx2]
            y[i, j] = pulp.LpVariable(f"y_{i}_{j}", cat="Binary")

            for c in core_ids:
                # If both i and j are on core c, one must precede the other
                model += s[j] >= f[i] - big_m * (
                        3 - y[i, j] - x[i][c] - x[j][c]
                )
                model += s[i] >= f[j] - big_m * (
                        2 + y[i, j] - x[i][c] - x[j][c]
                )

    # Communication cross-core penalty
    comm_penalties = []
    z = {}
    for comm in problem.communications:
        i, j = comm.source, comm.target
        for c1 in core_ids:
            for c2 in core_ids:
                if c1 == c2:
                    continue
                z[i, j, c1, c2] = pulp.LpVariable(f"z_{i}_{j}_{c1}_{c2}", cat="Binary")
                model += z[i, j, c1, c2] <= x[i][c1]
                model += z[i, j, c1, c2] <= x[j][c2]
                model += z[i, j, c1, c2] >= x[i][c1] + x[j][c2] - 1
                comm_penalties.append(comm.latency * z[i, j, c1, c2])

    # Objective function
    model += (cmax + problem.memory_penalty_weight * pulp.lpSum(overflow[c] for c in core_ids)
              + pulp.lpSum(comm_penalties))

    return model, {
        "x": x,
        "s": s,
        "f": f,
        "cmax": cmax,
        "overflow": overflow
    }
