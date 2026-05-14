from fractions import Fraction
from functools import reduce
from math import gcd, lcm

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


def build_model_cpsat(problem: ProblemInstance, hints: dict = None):
    model = cp_model.CpModel()

    tasks = {t.id: t for t in problem.tasks}
    jobs = {j.id: j for j in problem.jobs}
    cores = {c.id: c for c in problem.cores}
    clusters = {c.id: c for c in problem.clusters}

    task_ids = list(tasks.keys())
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
    # -----------------------------
    duration_values = []
    for job in problem.jobs:
        for core in problem.cores:
            val = Fraction(str(job.duration)) * Fraction(str(core.wcet_scale))
            duration_values.append(val)

    time_scale = 1
    for val in duration_values:
        time_scale = lcm(time_scale, val.denominator)

    scaled_duration = {}
    for job in problem.jobs:
        for core in problem.cores:
            val = Fraction(str(job.duration)) * Fraction(str(core.wcet_scale))
            scaled_duration[job.id, core.id] = int(val * time_scale)

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
    # Variables: Task Binding
    # Partitioned Scheduling Enforcer
    # -----------------------------
    y = {}
    for t_id in task_ids:
        task = tasks[t_id]
        eligible = task.eligible_cores
        assigned_task_core_vars = []

        for core_id in core_ids:
            if core_id not in eligible:
                continue

            y[t_id, core_id] = model.NewBoolVar(f"y_{t_id}_{core_id}")
            assigned_task_core_vars.append(y[t_id, core_id])

        if assigned_task_core_vars:
            model.AddExactlyOne(assigned_task_core_vars)

    if hints:
        for t_id, assigned_core in hints.items():
            if (t_id, assigned_core) in y:
                model.AddHint(y[t_id, assigned_core], 1)

                for c_id in tasks[t_id].eligible_cores:
                    if c_id != assigned_core and (t_id, c_id) in y:
                        model.AddHint(y[t_id, c_id], 0)
    # -----------------------------
    # Variables: Job Scheduling
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

        s[i] = model.NewIntVar(release_tick, horizon, f"s_{i}")
        f[i] = model.NewIntVar(0, horizon, f"f_{i}")

        eligible = tasks[job.task_id].eligible_cores

        for core_id in core_ids:
            if core_id not in eligible:
                continue

            x[i, core_id] = model.NewBoolVar(f"x_{i}_{core_id}")

            # --- CRITICAL CHANGE ---
            # Channel the Job assignment (x) directly to the Task assignment (y).
            # This guarantees partitioned scheduling and removes enormous symmetry.
            model.Add(x[i, core_id] == y[job.task_id, core_id])

            dur_ic = scaled_duration[i, core_id]

            s_local[i, core_id] = model.NewIntVar(
                release_tick, horizon, f"s_{i}_{core_id}"
            )
            f_local[i, core_id] = model.NewIntVar(
                0, horizon, f"f_{i}_{core_id}"
            )

            intervals[i, core_id] = model.NewOptionalIntervalVar(
                s_local[i, core_id],
                dur_ic,
                f_local[i, core_id],
                x[i, core_id],
                f"interval_{i}_{core_id}",
            )

            intervals_per_core[core_id].append(intervals[i, core_id])

            model.Add(s[i] == s_local[i, core_id]).OnlyEnforceIf(x[i, core_id])
            model.Add(f[i] == f_local[i, core_id]).OnlyEnforceIf(x[i, core_id])

            model.Add(
                f_local[i, core_id] == s_local[i, core_id] + dur_ic
            ).OnlyEnforceIf(x[i, core_id])

        if job.is_chain_root and job.chain_id is not None:
            jitter = getattr(problem, "max_chain_jitter", 0)

            if jitter == 0:
                # Strict start
                model.Add(s[i] == release_tick)
            if jitter < 0:
                # Unbounded start
                model.add(s[i] >= release_tick)
            else:
                # Bounded start within jitter window
                model.add(s[i] >= release_tick)
                model.add(s[i] <= release_tick + jitter)

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
                    f[terminal_job_id] <= terminal_job.absolute_deadline * time_scale
                )

    # -----------------------------
    # No overlap on each core
    # -----------------------------
    for core_id in core_ids:
        model.AddNoOverlap(intervals_per_core[core_id])


    # -----------------------------
    # Core / cluster memory overflow
    # CALCULATED AT THE TASK LEVEL
    # -----------------------------
    core_overflow = {}
    cluster_overflow = {}

    for core_id in core_ids:
        max_possible_mem = sum(
            tasks[t_id].memory
            for t_id in task_ids
            if core_id in tasks[t_id].eligible_cores
        )

        core_overflow[core_id] = model.NewIntVar(
            0, max_possible_mem, f"core_overflow_{core_id}"
        )

        used_memory = sum(
            tasks[t_id].memory * y[t_id, core_id]
            for t_id in task_ids
            if (t_id, core_id) in y
        )

        model.Add(
            used_memory <= cores[core_id].memory_budget + core_overflow[core_id]
        )

    for cluster_id in cluster_ids:
        max_possible_mem = sum(
            tasks[t_id].memory
            for t_id in task_ids
            for core_id in cluster_to_cores[cluster_id]
            if (t_id, core_id) in y
        )

        cluster_overflow[cluster_id] = model.NewIntVar(
            0, max_possible_mem, f"cluster_overflow_{cluster_id}"
        )

        used_memory = sum(
            tasks[t_id].memory * y[t_id, core_id]
            for t_id in task_ids
            for core_id in cluster_to_cores[cluster_id]
            if (t_id, core_id) in y
        )

        model.Add(
            used_memory <= clusters[cluster_id].memory_budget + cluster_overflow[cluster_id]
        )

    # -----------------------------
    # Communication penalty
    # CALCULATED ON TASK DEPENDENCIES
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
        t1, t2 = dep.predecessor, dep.successor

        for c1 in tasks[t1].eligible_cores:
            for c2 in tasks[t2].eligible_cores:
                if (t1, c1) not in y or (t2, c2) not in y:
                    continue

                z[t1, t2, c1, c2] = model.NewBoolVar(
                    f"z_{t1}_{t2}_{c1}_{c2}"
                )

                model.Add(z[t1, t2, c1, c2] >= y[t1, c1] + y[t2, c2] - 1)

                if (c1, c2) in explicit_path_penalty:
                    penalty = explicit_path_penalty[(c1, c2)]
                elif c1 == c2:
                    penalty = intra_core_weight
                elif core_to_cluster[c1] == core_to_cluster[c2]:
                    penalty = inter_core_weight
                else:
                    penalty = inter_cluster_weight

                if penalty != 0:
                    comm_penalty_terms.append(penalty * z[t1, t2, c1, c2])

    core_overflow_scale = problem.memory_penalty_scale.get("core_overflow_scale", 1)
    cluster_overflow_scale = problem.memory_penalty_scale.get("cluster_overflow_scale", 1)

    model.Minimize(
        + core_overflow_scale * sum(core_overflow[c] for c in core_ids)
        + cluster_overflow_scale * sum(cluster_overflow[cl] for cl in cluster_ids)
        + sum(comm_penalty_terms)
    )

    return model, {
        "time_scale": time_scale,
        "x": x,
        "y": y,
        "s": s,
        "f": f,
        "s_local": s_local,
        "f_local": f_local,
        "intervals": intervals,
        "core_overflows": core_overflow,
        "cluster_overflows": cluster_overflow,
        "z": z,
    }