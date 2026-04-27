from functools import reduce
from math import gcd

from ortools.sat.python import cp_model

from schemas.schemas import ProblemInstance


def _float_to_ratio(x: float, max_decimals: int = 6) -> tuple[int, int]:
    s = f"{x:.{max_decimals}f}".rstrip("0").rstrip(".")
    if "." not in s:
        return int(s), 1
    whole, frac = s.split(".")
    den = 10 ** len(frac)
    num = int(whole) * den + int(frac) if int(whole) >= 0 else int(s.replace(".", ""))
    g = gcd(abs(num), den)
    return num // g, den // g


def _lcm(a: int, b: int) -> int:
    return a * b // gcd(a, b)


def _lcm_many(values: list[int]) -> int:
    if not values:
        return 1
    return reduce(_lcm, values, 1)


def build_model_cpsat(problem: ProblemInstance):
    model = cp_model.CpModel()

    tasks = {t.id: t for t in problem.tasks}
    cores = {c.id: c for c in problem.cores}
    clusters = {c.id: c for c in problem.clusters}

    task_ids = list(tasks.keys())
    core_ids = list(cores.keys())
    cluster_ids = list(clusters.keys())

    # -----------------------------
    # Integer scaling for wcet_scale
    # CP-SAT is integer-only.
    # -----------------------------
    scale_denoms = []
    wcet_ratios = {}
    for c in problem.cores:
        num, den = _float_to_ratio(c.wcet_scale)
        wcet_ratios[c.id] = (num, den)
        scale_denoms.append(den)

    time_scale = _lcm_many(scale_denoms)

    scaled_duration = {}
    for t in problem.tasks:
        for c in problem.cores:
            num, den = wcet_ratios[c.id]
            # duration * wcet_scale, scaled to integer ticks
            scaled_duration[t.id, c.id] = t.duration * num * (time_scale // den)

    # horizon in scaled time units
    horizon = (
            sum(
                max(
                    (scaled_duration[t.id, c] for c in t.eligible_cores),
                    default=0,
                )
                for t in problem.tasks
            )
            + max((t.min_start for t in problem.tasks), default=0) * time_scale
            + 1
    )

    # -----------------------------
    # Core <-> cluster mappings
    # -----------------------------
    cluster_to_cores = {cl_id: [] for cl_id in cluster_ids}
    core_to_cluster = {}
    for c in problem.cores:
        cluster_to_cores[c.cluster_id].append(c.id)
        core_to_cluster[c.id] = c.cluster_id

    # -----------------------------
    # Variables
    # -----------------------------
    x = {}  # assignment BoolVar
    s = {}  # global task start (scaled integer time)
    f = {}  # global task finish (scaled integer time)
    s_local = {}  # local start if task runs on core c
    f_local = {}  # local finish if task runs on core c
    intervals = {}  # optional intervals per (task, core)
    intervals_per_core = {c: [] for c in core_ids}

    for i in task_ids:
        s[i] = model.NewIntVar(tasks[i].min_start * time_scale, horizon, f"s_{i}")
        f[i] = model.NewIntVar(0, horizon, f"f_{i}")

        eligible = tasks[i].eligible_cores
        assigned_core_vars = []

        for c in core_ids:
            if c not in eligible:
                continue

            x[i, c] = model.NewBoolVar(f"x_{i}_{c}")
            assigned_core_vars.append(x[i, c])

            dur_ic = scaled_duration[i, c]

            s_local[i, c] = model.NewIntVar(tasks[i].min_start * time_scale, horizon, f"s_{i}_{c}")
            f_local[i, c] = model.NewIntVar(0, horizon, f"f_{i}_{c}")

            intervals[i, c] = model.NewOptionalIntervalVar(
                s_local[i, c],
                dur_ic,
                f_local[i, c],
                x[i, c],
                f"interval_{i}_{c}",
            )
            intervals_per_core[c].append(intervals[i, c])

            # Channel global start/finish to the selected local start/finish
            model.Add(s[i] == s_local[i, c]).OnlyEnforceIf(x[i, c])
            model.Add(f[i] == f_local[i, c]).OnlyEnforceIf(x[i, c])

            # Interval end consistency
            model.Add(f_local[i, c] == s_local[i, c] + dur_ic).OnlyEnforceIf(x[i, c])

        model.AddExactlyOne(assigned_core_vars)

    # -----------------------------
    # Precedence constraints
    # -----------------------------
    for dep in problem.dependencies:
        model.Add(s[dep.successor] >= f[dep.predecessor])

    # -----------------------------
    # No overlap on each core
    # -----------------------------
    for c in core_ids:
        model.AddNoOverlap(intervals_per_core[c])

    # -----------------------------
    # Makespan
    # -----------------------------
    cmax = model.NewIntVar(0, horizon, "cmax")
    model.AddMaxEquality(cmax, [f[i] for i in task_ids])

    # -----------------------------
    # Core / cluster memory overflow
    # Equivalent to:
    # used <= budget + overflow
    # overflow >= 0
    # -----------------------------
    core_overflow = {}
    cluster_overflow = {}

    for c in core_ids:
        max_possible_mem = sum(
            tasks[i].memory
            for i in task_ids
            if c in tasks[i].eligible_cores
        )
        core_overflow[c] = model.NewIntVar(0, max_possible_mem, f"core_overflow_{c}")

        used_memory = sum(
            tasks[i].memory * x[i, c]
            for i in task_ids
            if (i, c) in x
        )
        model.Add(used_memory <= cores[c].memory_budget + core_overflow[c])

    for cl in cluster_ids:
        max_possible_mem = sum(
            tasks[i].memory
            for i in task_ids
            for c in cluster_to_cores[cl]
            if (i, c) in x
        )
        cluster_overflow[cl] = model.NewIntVar(0, max_possible_mem, f"cluster_overflow_{cl}")

        used_memory = sum(
            tasks[i].memory * x[i, c]
            for i in task_ids
            for c in cluster_to_cores[cl]
            if (i, c) in x
        )
        model.Add(used_memory <= clusters[cl].memory_budget + cluster_overflow[cl])

    # -----------------------------
    # Communication penalty
    # CBC used z[i,j,c1,c2] = x[i,c1] AND x[j,c2]
    # Do the same in CP-SAT.
    # -----------------------------
    explicit_path_penalty = {
        (comm.source, comm.target): comm.penalty
        for comm in problem.communication_paths
    }

    comm_penalty_weight = problem.comms_penalty_weight
    intra_core_weight = comm_penalty_weight.get("intra_core_weight", 0)
    inter_core_weight = comm_penalty_weight.get("inter_core_weight", 0)
    inter_cluster_weight = comm_penalty_weight.get("inter_cluster_weight", 0)

    z = {}
    comm_penalty_terms = []

    for dep in problem.dependencies:
        i, j = dep.predecessor, dep.successor

        for c1 in tasks[i].eligible_cores:
            for c2 in tasks[j].eligible_cores:
                z[i, j, c1, c2] = model.NewBoolVar(f"z_{i}_{j}_{c1}_{c2}")

                # z = x[i,c1] AND x[j,c2]
                model.AddMultiplicationEquality(
                    z[i, j, c1, c2],
                    [x[i, c1], x[j, c2]],
                )

                if (c1, c2) in explicit_path_penalty:
                    penalty = explicit_path_penalty[(c1, c2)]
                elif c1 == c2:
                    penalty = intra_core_weight
                elif core_to_cluster[c1] == core_to_cluster[c2]:
                    penalty = inter_core_weight
                else:
                    penalty = inter_cluster_weight

                if penalty != 0:
                    comm_penalty_terms.append(penalty * z[i, j, c1, c2])

    # -----------------------------
    # Objective
    # Keep everything in scaled time units.
    # Memory and communication terms remain unscaled, matching
    # the same relative structure as your CBC objective.
    # -----------------------------
    core_overflow_scale = problem.memory_penalty_scale.get("core_overflow_scale", 1)
    cluster_overflow_scale = problem.memory_penalty_scale.get("cluster_overflow_scale", 1)

    model.Minimize(
        cmax
        + core_overflow_scale * sum(core_overflow[c] for c in core_ids)
        + cluster_overflow_scale * sum(cluster_overflow[cl] for cl in cluster_ids)
        + sum(comm_penalty_terms)
    )

    return model, {
        "time_scale": time_scale,
        "x": x,
        "s": s,
        "f": f,
        "cmax": cmax,
        "s_local": s_local,
        "f_local": f_local,
        "intervals": intervals,
        "core_overflow": core_overflow,
        "cluster_overflow": cluster_overflow,
        "z": z,
    }
