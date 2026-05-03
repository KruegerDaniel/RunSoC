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

    if whole.startswith("-"):
        num = int(whole) * den - int(frac)
    else:
        num = int(whole) * den + int(frac)

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

    jobs = {j.id: j for j in problem.jobs}
    cores = {c.id: c for c in problem.cores}
    clusters = {c.id: c for c in problem.clusters}

    job_ids = list(jobs.keys())
    core_ids = list(cores.keys())
    cluster_ids = list(clusters.keys())

    # -----------------------------
    # Task-chain helpers
    # -----------------------------
    jobs_by_chain_instance: dict[tuple[str, int], list[str]] = {}

    for job in problem.jobs:
        if job.chain_id is not None and job.instance_index is not None:
            key = (job.chain_id, job.instance_index)
            jobs_by_chain_instance.setdefault(key, []).append(job.id)

    successors_by_job = {job_id: set() for job_id in job_ids}

    for dep in problem.job_dependencies:
        if dep.predecessor in jobs and dep.successor in jobs:
            successors_by_job[dep.predecessor].add(dep.successor)

    terminal_jobs_by_chain_instance: dict[tuple[str, int], list[str]] = {}

    for key, chain_job_ids in jobs_by_chain_instance.items():
        chain_job_set = set(chain_job_ids)

        terminal_jobs_by_chain_instance[key] = [
            job_id
            for job_id in chain_job_ids
            if not any(
                successor in chain_job_set
                for successor in successors_by_job[job_id]
            )
        ]

    # -----------------------------
    # Integer scaling
    # CP-SAT is integer-only.
    # -----------------------------
    duration_ratios = {}
    wcet_ratios = {}
    scale_denoms = []

    for job in problem.jobs:
        num, den = _float_to_ratio(job.duration)
        duration_ratios[job.id] = (num, den)
        scale_denoms.append(den)

    for core in problem.cores:
        num, den = _float_to_ratio(core.wcet_scale)
        wcet_ratios[core.id] = (num, den)
        scale_denoms.append(den)

    time_scale = _lcm_many(scale_denoms)

    scaled_duration = {}

    for job in problem.jobs:
        duration_num, duration_den = duration_ratios[job.id]

        for core in problem.cores:
            wcet_num, wcet_den = wcet_ratios[core.id]

            scaled_duration[job.id, core.id] = (
                    duration_num
                    * wcet_num
                    * time_scale
                    // duration_den
                    // wcet_den
            )

    # -----------------------------
    # Horizon in scaled time units
    # -----------------------------
    max_release = max(
        (job.release_time for job in problem.jobs),
        default=0,
    )

    max_deadline = max(
        (
            job.absolute_deadline
            for job in problem.jobs
            if job.absolute_deadline is not None
        ),
        default=0,
    )

    total_worst_case_duration = sum(
        max(
            (
                scaled_duration[job.id, core_id]
                for core_id in job.eligible_cores
            ),
            default=0,
        )
        for job in problem.jobs
    )

    horizon = (
            max(max_release, max_deadline) * time_scale
            + total_worst_case_duration
            + 1
    )

    # -----------------------------
    # Core <-> cluster mappings
    # -----------------------------
    cluster_to_cores = {cl_id: [] for cl_id in cluster_ids}
    core_to_cluster = {}

    for core in problem.cores:
        cluster_to_cores[core.cluster_id].append(core.id)
        core_to_cluster[core.id] = core.cluster_id

    # -----------------------------
    # Variables
    # -----------------------------
    x = {}
    s = {}
    f = {}

    s_local = {}
    f_local = {}

    intervals = {}
    intervals_per_core = {core_id: [] for core_id in core_ids}

    for i in job_ids:
        job = jobs[i]

        release_tick = job.release_time * time_scale

        s[i] = model.NewIntVar(
            release_tick,
            horizon,
            f"s_{i}",
        )

        f[i] = model.NewIntVar(
            0,
            horizon,
            f"f_{i}",
        )

        eligible = job.eligible_cores
        assigned_core_vars = []

        for core_id in core_ids:
            if core_id not in eligible:
                continue

            x[i, core_id] = model.NewBoolVar(f"x_{i}_{core_id}")
            assigned_core_vars.append(x[i, core_id])

            dur_ic = scaled_duration[i, core_id]

            s_local[i, core_id] = model.NewIntVar(
                release_tick,
                horizon,
                f"s_{i}_{core_id}",
            )

            f_local[i, core_id] = model.NewIntVar(
                0,
                horizon,
                f"f_{i}_{core_id}",
            )

            intervals[i, core_id] = model.NewOptionalIntervalVar(
                s_local[i, core_id],
                dur_ic,
                f_local[i, core_id],
                x[i, core_id],
                f"interval_{i}_{core_id}",
            )

            intervals_per_core[core_id].append(intervals[i, core_id])

            # Channel global start/finish to selected local start/finish.
            model.Add(s[i] == s_local[i, core_id]).OnlyEnforceIf(x[i, core_id])
            model.Add(f[i] == f_local[i, core_id]).OnlyEnforceIf(x[i, core_id])

            # Interval end consistency.
            model.Add(
                f_local[i, core_id] == s_local[i, core_id] + dur_ic
            ).OnlyEnforceIf(x[i, core_id])

        model.AddExactlyOne(assigned_core_vars)

        # Strict periodic task-chain root start.
        if job.is_chain_root and job.chain_id is not None:
            model.Add(s[i] == release_tick)

    # -----------------------------
    # Job precedence constraints
    # -----------------------------
    for dep in problem.job_dependencies:
        model.Add(s[dep.successor] >= f[dep.predecessor])

    # -----------------------------
    # Strict task-chain finish
    # -----------------------------
    for key, terminal_job_ids in terminal_jobs_by_chain_instance.items():
        for terminal_job_id in terminal_job_ids:
            terminal_job = jobs[terminal_job_id]

            if terminal_job.absolute_deadline is not None:
                model.Add(
                    f[terminal_job_id]
                    <= terminal_job.absolute_deadline * time_scale
                )

    # -----------------------------
    # No overlap on each core
    # -----------------------------
    for core_id in core_ids:
        model.AddNoOverlap(intervals_per_core[core_id])

    # -----------------------------
    # Makespan
    # -----------------------------
    cmax = model.NewIntVar(0, horizon, "cmax")

    if job_ids:
        model.AddMaxEquality(cmax, [f[i] for i in job_ids])
    else:
        model.Add(cmax == 0)

    # -----------------------------
    # Core / cluster memory overflow
    # Equivalent to:
    # used <= budget + overflow
    # overflow >= 0
    # -----------------------------
    core_overflow = {}
    cluster_overflow = {}

    for core_id in core_ids:
        max_possible_mem = sum(
            jobs[i].memory
            for i in job_ids
            if core_id in jobs[i].eligible_cores
        )

        core_overflow[core_id] = model.NewIntVar(
            0,
            max_possible_mem,
            f"core_overflow_{core_id}",
        )

        used_memory = sum(
            jobs[i].memory * x[i, core_id]
            for i in job_ids
            if (i, core_id) in x
        )

        model.Add(
            used_memory
            <= cores[core_id].memory_budget + core_overflow[core_id]
        )

    for cluster_id in cluster_ids:
        max_possible_mem = sum(
            jobs[i].memory
            for i in job_ids
            for core_id in cluster_to_cores[cluster_id]
            if (i, core_id) in x
        )

        cluster_overflow[cluster_id] = model.NewIntVar(
            0,
            max_possible_mem,
            f"cluster_overflow_{cluster_id}",
        )

        used_memory = sum(
            jobs[i].memory * x[i, core_id]
            for i in job_ids
            for core_id in cluster_to_cores[cluster_id]
            if (i, core_id) in x
        )

        model.Add(
            used_memory
            <= clusters[cluster_id].memory_budget
            + cluster_overflow[cluster_id]
        )

    # -----------------------------
    # Communication penalty
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

    for dep in problem.job_dependencies:
        i, j = dep.predecessor, dep.successor

        for c1 in jobs[i].eligible_cores:
            for c2 in jobs[j].eligible_cores:
                z[i, j, c1, c2] = model.NewBoolVar(
                    f"z_{i}_{j}_{c1}_{c2}"
                )

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
        "core_overflows": core_overflow,
        "cluster_overflows": cluster_overflow,
        "z": z,
    }
