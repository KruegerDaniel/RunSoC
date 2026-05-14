import pulp

from schemas.schemas import ProblemInstance


def build_model(problem: ProblemInstance):
    model = pulp.LpProblem(name="test_problem", sense=pulp.LpMinimize)  # minimization problem

    jobs = {j.id: j for j in problem.jobs}
    cores = {c.id: c for c in problem.cores}
    clusters = {c.id: c for c in problem.clusters}

    job_ids = list(jobs.keys())
    core_ids = list(cores.keys())
    cluster_ids = list(clusters.keys())

    # core <-> cluster mappings
    core_to_cluster = {c.id: clusters[c.cluster_id] for c in cores.values()}
    cluster_to_cores = {cl_id: [] for cl_id in cluster_ids}
    for c in problem.cores:
        cluster_to_cores[c.cluster_id].append(c.id)

    # task chain helpers
    chain_by_id = {tc.id: tc for tc in problem.task_chains}

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

    # Decision Variables
    x = pulp.LpVariable.dicts("allocs", (job_ids, core_ids), cat="Binary")
    s = pulp.LpVariable.dicts("start", job_ids, lowBound=0, upBound=big_m, cat="Continuous")
    f = pulp.LpVariable.dicts("finish", job_ids, lowBound=0, upBound=big_m, cat="Continuous")

    core_overflow = pulp.LpVariable.dicts("core_overflow", core_ids, lowBound=0, cat="Continuous")
    cluster_overflow = pulp.LpVariable.dicts("cluster_overflow", cluster_ids, lowBound=0,
                                             cat="Continuous")

    # ----------------------
    # Assignment constraints
    # ----------------------
    for i in job_ids:
        eligible = jobs[i].eligible_cores
        model += pulp.lpSum(
            x[i][c] for c in eligible) == 1, f"assign_once_{i}"  # only assign job once

        # do not assign task to non-affinity core
        for c in core_ids:
            if c not in eligible:
                model += x[i][c] == 0, f"ineligible_{i}_{c}"

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

        # finish time
        model += (
                f[i] == s[i] + pulp.lpSum(
            job.duration * cores[c].wcet_scale * x[i][c]
            for c in core_ids)
        ), f"finish_def_{i}"

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
    # Core/Cluster memory overflow
    # ---------------------------
    for c in core_ids:
        model += (
                pulp.lpSum(jobs[i].memory * x[i][c] for i in job_ids)
                <= cores[c].memory_budget + core_overflow[c]
        ), f"core_mem_budget_{c}"

    for cl in cluster_ids:
        model += (
                pulp.lpSum(
                    jobs[i].memory * x[i][c] for i in job_ids for c in cluster_to_cores[cl])
                <= clusters[cl].memory_budget + cluster_overflow[cl]
        ), f"cluster_mem_budget_{cl}"

    # -------------------------------
    # No overlap on core constraint
    # -------------------------------
    y = {}
    for idx1 in range(len(job_ids)):
        for idx2 in range(idx1 + 1, len(job_ids)):
            i = job_ids[idx1]
            j = job_ids[idx2]
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
    comm_job_pairs = [(dep.predecessor, dep.successor) for dep in problem.job_dependencies]
    z = {}

    for i, j in comm_job_pairs:
        for c1 in jobs[i].eligible_cores:
            for c2 in jobs[j].eligible_cores:
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
            core_overflow_scale * pulp.lpSum(core_overflow[c] for c in core_ids)
            + cluster_overflow_scale * pulp.lpSum(cluster_overflow[cl] for cl in cluster_ids)
            + pulp.lpSum(comm_penalties))

    return model, {
        "x": x,
        "s": s,
        "f": f,
        "core_overflow": core_overflow,
        "cluster_overflow": cluster_overflow,
    }
