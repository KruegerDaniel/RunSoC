import pulp

from schemas.schemas import ProblemInstance


def build_model(problem: ProblemInstance):
    model = pulp.LpProblem(name="test_problem", sense=pulp.LpMinimize)  # minimization problem

    tasks = {t.id: t for t in problem.tasks}
    jobs = {j.id: j for j in problem.jobs}
    cores = {c.id: c for c in problem.cores}
    clusters = {c.id: c for c in problem.clusters}

    task_ids = list(tasks.keys())
    job_ids = list(jobs.keys())
    core_ids = list(cores.keys())
    cluster_ids = list(clusters.keys())

    # core <-> cluster mappings
    core_to_cluster = {c.id: clusters[c.cluster_id] for c in cores.values()}
    cluster_to_cores = {cl_id: [] for cl_id in cluster_ids}
    for c in problem.cores:
        cluster_to_cores[c.cluster_id].append(c.id)

    # task chain helpers
    jobs_by_chain_instance = {}
    for j in problem.jobs:
        if j.chain_id is not None and j.instance_index is not None:
            key = (j.chain_id, j.instance_index)
            jobs_by_chain_instance.setdefault(key, []).append(j.id)

    successors_by_job = {j_id: set() for j_id in job_ids}
    predecessors_by_job = {j_id: set() for j_id in job_ids}
    for dep in problem.job_dependencies:
        if dep.successor in job_ids and dep.predecessor in job_ids:
            successors_by_job[dep.successor].add(dep.predecessor)
            predecessors_by_job[dep.predecessor].add(dep.successor)

    terminal_jobs_by_chain_instance = {}
    for key, chain_jobs_ids in jobs_by_chain_instance.items():
        chain_job_set = set(chain_jobs_ids)
        terminal_jobs = [
            j_id
            for j_id in chain_jobs_ids
            if not any(succ in chain_job_set for succ in successors_by_job[j_id])
        ]
        terminal_jobs_by_chain_instance[key] = terminal_jobs

    # Big M is the sum of all
    big_m = (
            max((j.release_time for j in problem.jobs), default=0)
            + sum(
        max(j.duration * cores[c].wcet_scale for c in j.eligible_cores) for j in problem.jobs)
            + 1
    )

    # -----------------------------------
    # Task-Level Decision Variables
    # -----------------------------------
    y_alloc = pulp.LpVariable.dicts("task_allocs", (task_ids, core_ids), cat="Binary")

    # -----------------------------------
    # Job-Level Decision Variables
    # -----------------------------------
    s = pulp.LpVariable.dicts("start", job_ids, lowBound=0, upBound=big_m, cat="Continuous")
    f = pulp.LpVariable.dicts("finish", job_ids, lowBound=0, upBound=big_m, cat="Continuous")
    cmax = pulp.LpVariable("c_max", lowBound=0, upBound=big_m, cat="Continuous")

    core_overflow = pulp.LpVariable.dicts("core_overflow", core_ids, lowBound=0, cat="Continuous")
    cluster_overflow = pulp.LpVariable.dicts("cluster_overflow", cluster_ids, lowBound=0, cat="Continuous")

    # Enforced partitioned scheduling.
    # Link Job allocations (x) strictly to Task allocations (y_alloc)
    x = {i: {} for i in job_ids}
    for i in job_ids:
        t_id = jobs[i].task_id
        for c in core_ids:
            x[i][c] = y_alloc[t_id][c]

    # ----------------------
    # Assignment constraints at Task Level
    # ----------------------
    for t_id in task_ids:
        eligible = tasks[t_id].eligible_cores
        model += pulp.lpSum(y_alloc[t_id][c] for c in eligible) == 1, f"assign_once_{t_id}"

        # do not assign task to non-affinity core
        for c in core_ids:
            if c not in eligible:
                model += y_alloc[t_id][c] == 0, f"ineligible_{t_id}_{c}"

    # -----------------------
    # Timing constraints
    # ----------------------
    for i in job_ids:
        job = jobs[i]

        # earliest start
        model += s[i] >= job.release_time, f"release_time_{i}"

        # strict chain start periodicity
        if job.is_chain_root and job.chain_id is not None:
            model += s[i] == job.release_time, f"strict_chain_start_{i}"

        # finish time (uses x alias perfectly)
        model += (
                f[i] == s[i] + pulp.lpSum(
            job.duration * cores[c].wcet_scale * x[i][c]
            for c in core_ids)
        ), f"finish_def_{i}"

        # makespan constraint
        model += cmax >= f[i], f"cmax_{i}"

    # Precedence constraints
    for dep in problem.job_dependencies:
        model += s[dep.successor] >= f[dep.predecessor]

    # Task chain finish deadline
    for key, terminal_jobs_ids in terminal_jobs_by_chain_instance.items():
        chain_id, instance_index = key
        for terminal_job_id in terminal_jobs_ids:
            terminal_job = jobs[terminal_job_id]
            if terminal_job.absolute_deadline is not None:
                model += (
                        f[terminal_job_id] <= terminal_job.absolute_deadline
                ), f"strict_chain_finish_{chain_id}_{instance_index}_{terminal_job_id}"

    # ---------------------------
    # Core/Cluster memory overflow at Task Level
    # ---------------------------
    for c in core_ids:
        model += (
                pulp.lpSum(tasks[t_id].memory * y_alloc[t_id][c] for t_id in task_ids)
                <= cores[c].memory_budget + core_overflow[c]
        ), f"core_mem_budget_{c}"

    for cl in cluster_ids:
        model += (
                pulp.lpSum(
                    tasks[t_id].memory * y_alloc[t_id][c]
                    for t_id in task_ids
                    for c in cluster_to_cores[cl]
                ) <= clusters[cl].memory_budget + cluster_overflow[cl]
        ), f"cluster_mem_budget_{cl}"

    # -------------------------------
    # No overlap on core constraint
    # -------------------------------
    # Renamed y to overlap_bin to avoid shadowing task allocation y_alloc
    overlap_bin = {}
    for idx1 in range(len(job_ids)):
        for idx2 in range(idx1 + 1, len(job_ids)):
            i = job_ids[idx1]
            j = job_ids[idx2]
            overlap_bin[i, j] = pulp.LpVariable(f"overlap_{i}_{j}", cat="Binary")

            for c in core_ids:
                # If both i and j are on core c, one must precede the other
                model += s[j] >= f[i] - big_m * (
                        3 - overlap_bin[i, j] - x[i][c] - x[j][c]
                ), f"no_overlap_ij_{i}_{j}_{c}"
                model += s[i] >= f[j] - big_m * (
                        2 + overlap_bin[i, j] - x[i][c] - x[j][c]
                ), f"no_overlap_ji_{i}_{j}_{c}"

    # -----------------------------------
    # Communication penalty of paths at Task Level
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

    for t1, t2 in comm_task_pairs:
        for c1 in tasks[t1].eligible_cores:
            for c2 in tasks[t2].eligible_cores:
                z[t1, t2, c1, c2] = pulp.LpVariable(f"z_{t1}_{t2}_{c1}_{c2}", cat="Binary")

                # z[t1,t2,c1,c2] = 1 iff y_alloc[t1][c1] and y_alloc[t2][c2] = 1
                model += z[t1, t2, c1, c2] <= y_alloc[t1][c1], f"z_up1_{t1}_{t2}_{c1}_{c2}"
                model += z[t1, t2, c1, c2] <= y_alloc[t2][c2], f"z_up2_{t1}_{t2}_{c1}_{c2}"
                model += z[t1, t2, c1, c2] >= y_alloc[t1][c1] + y_alloc[t2][c2] - 1, f"z_low_{t1}_{t2}_{c1}_{c2}"

                if (c1, c2) in explicit_path_penalty:
                    penalty = explicit_path_penalty[(c1, c2)]
                elif c1 == c2:
                    penalty = intra_core_weight
                elif core_to_cluster[c1] == core_to_cluster[c2]:
                    penalty = inter_core_weight
                else:
                    penalty = inter_cluster_weight

                comm_penalties.append(penalty * z[t1, t2, c1, c2])

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