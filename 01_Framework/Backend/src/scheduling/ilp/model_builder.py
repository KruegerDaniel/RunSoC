import pulp

from schemas.schemas import ProblemInstance


def build_model(problem: ProblemInstance):
    model = pulp.LpProblem(name="test_problem", sense=pulp.LpMinimize)  # minimization problem

    tasks = {t.id: t for t in problem.tasks}
    cores = {c.id: c for c in problem.cores}
    clusters = {c.id: c for c in problem.clusters}

    task_ids = list(tasks.keys())
    core_ids = list(cores.keys())
    cluster_ids = list(clusters.keys())

    # core <-> cluster mappings
    core_to_cluster = {c.id: clusters[c.cluster_id] for c in cores.values()}
    cluster_to_cores = {cl_id: [] for cl_id in cluster_ids}
    for c in problem.cores:
        cluster_to_cores[c.cluster_id].append(c.id)

    # Big M is the sum of all
    big_m = (
            max((t.min_start for t in problem.tasks), default=0)
            + sum(
                max(t.duration * cores[c].wcet_scale for c in t.eligible_cores) for t in problem.tasks)
                + 1
    )

    # Decision Variables
    x = pulp.LpVariable.dicts("allocs", (task_ids, core_ids), cat="Binary")
    s = pulp.LpVariable.dicts("start", task_ids, lowBound=0, upBound=big_m, cat="Continuous")
    f = pulp.LpVariable.dicts("finish", task_ids, lowBound=0, upBound=big_m, cat="Continuous")
    cmax = pulp.LpVariable("c_max", lowBound=0, upBound=big_m, cat="Continuous")

    core_overflow = pulp.LpVariable.dicts("core_overflow", core_ids, lowBound=0, cat="Continuous")
    cluster_overflow = pulp.LpVariable.dicts("cluster_overflow", cluster_ids, lowBound=0,
                                             cat="Continuous")

    # ----------------------
    # Assignment constraints
    # ----------------------
    for i in task_ids:
        eligible = tasks[i].eligible_cores
        model += pulp.lpSum(
            x[i][c] for c in eligible) == 1, f"assign_once_{i}"  # only assign task once

        # do not assign task to non-affinity core
        for c in core_ids:
            if c not in eligible:
                model += x[i][c] == 0, f"ineligible_{i}_{c}"

    # -----------------------
    # Timing constraints
    # ----------------------
    for i in task_ids:
        # earliest start
        model += s[i] >= tasks[i].min_start, f"min_start_{i}"

        # finish time
        model += (
                f[i] == s[i] + pulp.lpSum(
            tasks[i].duration * cores[c].wcet_scale * x[i][c]
            for c in core_ids)
        ), f"finish_def_{i}"

        # makespan constraint
        model += cmax >= f[i], f"cmax_{i}"

    # Precedence constraints
    for dep in problem.dependencies:
        model += s[dep.successor] >= f[dep.predecessor]

    # ---------------------------
    # Core/Cluster memory overflow
    # ---------------------------
    for c in core_ids:
        model += (
                pulp.lpSum(tasks[i].memory * x[i][c] for i in task_ids)
                <= cores[c].memory_budget + core_overflow[c]
        ), f"core_mem_budget_{c}"

    for cl in cluster_ids:
        model += (
                pulp.lpSum(
                    tasks[i].memory * x[i][c] for i in task_ids for c in cluster_to_cores[cl])
                <= clusters[cl].memory_budget + cluster_overflow[cl]
        ), f"cluster_mem_budget_{cl}"

    # -------------------------------
    # No overlap on core constraint
    # -------------------------------
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
                ), f"no_overlap_ij_{i}_{j}_{c}"
                model += s[i] >= f[j] - big_m * (
                        2 + y[i, j] - x[i][c] - x[j][c]
                ), f"no_overlap_ji_{i}_{j}_{c}"

    # -----------------------------------
    # Communication penalty of paths
    # -----------------------------------
    explicit_path_penalty = {
        (comm.source, comm.target): comm.penalty for comm in problem.communication_paths
    }
    comm_penalty_weight = problem.comms_penalty_weight
    intra_core_weight = comm_penalty_weight.get("intra_core_weight", 0)
    inter_core_weight = comm_penalty_weight.get("inter_core_weight", 0)
    inter_cluster_weight = comm_penalty_weight.get("inter_cluster_weight", 0)

    comm_penalties = []
    comm_task_pairs = [(dep.predecessor, dep.successor) for dep in problem.dependencies]
    z = {}

    for i, j in comm_task_pairs:
        for c1 in tasks[i].eligible_cores:
            for c2 in tasks[j].eligible_cores:
                z[i, j, c1, c2] = pulp.LpVariable(f"z_{i}_{j}_{c1}_{c2}", cat="Binary")

                # z[i,j,c1,c2] = 1 iff x[i][c1] and x[j][c2] = 1
                model += z[i, j, c1, c2] <= x[i][c1], f"z_up1_{i}_{j}_{c1}_{c2}"
                model += z[i, j, c1, c2] <= x[j][c2], f"z_up2_{i}_{j}_{c1}_{c2}"
                model += z[i, j, c1, c2] >= x[i][c1] + x[j][c2] - 1, f"z_low_{i}_{j}_{c1}_{c2}"

                if (c1, c2) in explicit_path_penalty:
                    penalty = explicit_path_penalty[(c1, c2)]
                elif c1 == c2:
                    penalty = intra_core_weight
                elif core_to_cluster[c1] == core_to_cluster[c2]:
                    penalty = inter_core_weight
                else:
                    penalty = inter_cluster_weight

                comm_penalties.append(penalty * z[i, j, c1, c2])

    # ----------------------------
    # Objective function
    # -----------------------------
    core_overflow_scale = problem.memory_penalty_scale.get("core_overflow_scale", 1)
    cluster_overflow_scale = problem.memory_penalty_scale.get("cluster_overflow_scale", 1)
    model += (
            cmax
            + core_overflow_scale * pulp.lpSum(core_overflow[c] for c in core_ids)
            + cluster_overflow_scale * pulp.lpSum(cluster_overflow[cl] for cl in cluster_ids)
            + pulp.lpSum(comm_penalties))

    return model, {
        "x": x,
        "s": s,
        "f": f,
        "cmax": cmax,
        "core_overflow": core_overflow,
        "cluster_overflow": cluster_overflow,
    }
