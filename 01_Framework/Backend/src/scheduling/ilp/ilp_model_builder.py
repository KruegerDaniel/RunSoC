import pulp

from schemas.schemas import ProblemInstance


def build_model(problem: ProblemInstance):
    model = pulp.LpProblem(name="test_problem", sense=pulp.LpMinimize)

    tasks = {t.id: t for t in problem.tasks}
    jobs = {j.id: j for j in problem.jobs}
    cores = {c.id: c for c in problem.cores}
    clusters = {c.id: c for c in problem.clusters}

    task_ids = list(tasks.keys())
    job_ids = list(jobs.keys())
    core_ids = list(cores.keys())
    cluster_ids = list(clusters.keys())

    # Core <-> cluster mappings.
    #
    # Keep both forms:
    # - core_to_cluster gives direct access to the cluster object if needed.
    # - core_to_cluster_id is used for cheap and robust equality checks.
    core_to_cluster = {c.id: clusters[c.cluster_id] for c in cores.values()}
    core_to_cluster_id = {c.id: c.cluster_id for c in cores.values()}

    cluster_to_cores = {cl_id: [] for cl_id in cluster_ids}
    for c in problem.cores:
        cluster_to_cores[c.cluster_id].append(c.id)

    # -----------------------------------
    # Task-chain helpers
    # -----------------------------------
    jobs_by_chain_instance = {}
    for j in problem.jobs:
        if j.chain_id is not None and j.instance_index is not None:
            key = (j.chain_id, j.instance_index)
            jobs_by_chain_instance.setdefault(key, []).append(j.id)

    successors_by_job = {j_id: set() for j_id in job_ids}
    predecessors_by_job = {j_id: set() for j_id in job_ids}

    for dep in problem.job_dependencies:
        if dep.successor in job_ids and dep.predecessor in job_ids:
            successors_by_job[dep.predecessor].add(dep.successor)
            predecessors_by_job[dep.successor].add(dep.predecessor)

    terminal_jobs_by_chain_instance = {}
    for key, chain_job_ids in jobs_by_chain_instance.items():
        chain_job_set = set(chain_job_ids)
        terminal_jobs = [
            j_id
            for j_id in chain_job_ids
            if not any(succ in chain_job_set for succ in successors_by_job[j_id])
        ]
        terminal_jobs_by_chain_instance[key] = terminal_jobs

    # -----------------------------------
    # Big-M
    # -----------------------------------
    # Valid time upper bound:
    # - If the mapper provides a horizon, include it.
    # - Also include release times plus the worst possible total execution load.
    #
    # This keeps the M value valid for no-overlap constraints while avoiding
    # smaller invalid M values on instances where the horizon is only a nominal
    # activation horizon and the schedule may still extend beyond it.
    max_release = max((j.release_time for j in problem.jobs), default=0)
    worst_total_duration = sum(
        max(j.duration * cores[c].wcet_scale for c in j.eligible_cores)
        for j in problem.jobs
    )
    mapper_horizon = getattr(problem, "horizon", None) or 0
    big_m = max(mapper_horizon, max_release + worst_total_duration) + 1

    # -----------------------------------
    # Task-level decision variables
    # -----------------------------------
    y_alloc = pulp.LpVariable.dicts(
        "task_allocs",
        (task_ids, core_ids),
        cat="Binary",
    )

    # -----------------------------------
    # Job-level decision variables
    # -----------------------------------
    s = pulp.LpVariable.dicts(
        "start",
        job_ids,
        lowBound=0,
        upBound=big_m,
        cat="Continuous",
    )

    f = pulp.LpVariable.dicts(
        "finish",
        job_ids,
        lowBound=0,
        upBound=big_m,
        cat="Continuous",
    )

    core_overflow = pulp.LpVariable.dicts(
        "core_overflow",
        core_ids,
        lowBound=0,
        cat="Continuous",
    )

    cluster_overflow = pulp.LpVariable.dicts(
        "cluster_overflow",
        cluster_ids,
        lowBound=0,
        cat="Continuous",
    )

    # Enforced partitioned scheduling:
    # every job inherits the allocation of its task template.
    x = {i: {} for i in job_ids}
    for i in job_ids:
        task_id = jobs[i].task_id
        for c in core_ids:
            x[i][c] = y_alloc[task_id][c]

    # ----------------------
    # Assignment constraints at task level
    # ----------------------
    for task_id in task_ids:
        eligible = tasks[task_id].eligible_cores

        model += (
            pulp.lpSum(y_alloc[task_id][c] for c in eligible) == 1
        ), f"assign_once_{task_id}"

        for c in core_ids:
            if c not in eligible:
                model += y_alloc[task_id][c] == 0, f"ineligible_{task_id}_{c}"

    # -----------------------
    # Timing constraints
    # ----------------------
    for job_id in job_ids:
        job = jobs[job_id]

        model += s[job_id] >= job.release_time, f"release_time_{job_id}"

        # Chain-root start policy.
        if job.is_chain_root and job.chain_id is not None:
            jitter = getattr(problem, "max_chain_jitter", 0)

            if jitter == 0:
                model += (
                    s[job_id] == job.release_time
                ), f"strict_chain_start_eq_{job_id}"
            elif jitter > 0:
                model += (
                    s[job_id] <= job.release_time + jitter
                ), f"strict_chain_start_up_{job_id}"

        # Finish definition.
        #
        # Restrict the expression to job.eligible_cores. Ineligible variables are
        # fixed to zero at task level, so using all cores is equivalent, but this
        # smaller expression reduces model size.
        model += (
            f[job_id]
            == s[job_id]
            + pulp.lpSum(
                job.duration * cores[c].wcet_scale * x[job_id][c]
                for c in job.eligible_cores
            )
        ), f"finish_def_{job_id}"

    # Precedence constraints.
    for dep in problem.job_dependencies:
        model += (
            s[dep.successor] >= f[dep.predecessor]
        ), f"precedence_{dep.predecessor}_{dep.successor}"

    # Task-chain finish deadline.
    for key, terminal_job_ids in terminal_jobs_by_chain_instance.items():
        chain_id, instance_index = key

        for terminal_job_id in terminal_job_ids:
            terminal_job = jobs[terminal_job_id]
            if terminal_job.absolute_deadline is not None:
                model += (
                    f[terminal_job_id] <= terminal_job.absolute_deadline
                ), f"strict_chain_finish_{chain_id}_{instance_index}_{terminal_job_id}"

    # ---------------------------
    # Core/cluster memory overflow at task level
    # ---------------------------
    #
    # This keeps the updated exact memory objective:
    # - core_overflow[c] = max(0, core_used_memory[c] - core_budget[c])
    # - cluster_used_memory[cl] = sum core_overflow[c] over cores in cluster
    # - cluster_overflow[cl] = max(0, cluster_used_memory[cl] - cluster_budget[cl])
    #
    # Note: this cluster formulation treats cluster pressure as aggregate core
    # spill, not as total task memory mapped into the cluster. That matches the
    # provided updated objective.
    core_used_memory = {}
    cluster_used_memory = {}

    core_spill_active = {}
    cluster_spill_active = {}

    core_max_possible_mem = {}

    # Exact core overflow modeling.
    for c in core_ids:
        core_budget = int(cores[c].memory_budget)

        max_possible_mem = sum(
            int(tasks[task_id].memory)
            for task_id in task_ids
            if c in tasks[task_id].eligible_cores
        )

        core_max_possible_mem[c] = max_possible_mem

        core_used_memory[c] = pulp.LpVariable(
            f"core_used_memory_{c}",
            lowBound=0,
            upBound=max_possible_mem,
            cat="Continuous",
        )

        core_spill_active[c] = pulp.LpVariable(
            f"core_spill_active_{c}",
            cat="Binary",
        )

        used_expr = pulp.lpSum(
            int(tasks[task_id].memory) * y_alloc[task_id][c]
            for task_id in task_ids
            if c in tasks[task_id].eligible_cores
        )

        model += (
            core_used_memory[c] == used_expr
        ), f"core_used_memory_def_{c}"

        # diff = core_used_memory[c] - core_budget
        # core_overflow[c] = max(0, diff)
        diff_expr = core_used_memory[c] - core_budget

        # Big-M must cover both positive and negative diff ranges.
        core_m = max(core_budget, max_possible_mem - core_budget, 0)

        model += (
            core_overflow[c] >= diff_expr
        ), f"core_overflow_lb_diff_{c}"

        model += (
            core_overflow[c] >= 0
        ), f"core_overflow_lb_zero_{c}"

        model += (
            core_overflow[c] <= diff_expr + core_m * (1 - core_spill_active[c])
        ), f"core_overflow_ub_diff_{c}"

        model += (
            core_overflow[c] <= core_m * core_spill_active[c]
        ), f"core_overflow_ub_zero_{c}"

    # Exact cluster overflow modeling.
    for cluster_id in cluster_ids:
        cluster_budget = int(clusters[cluster_id].memory_budget)
        cluster_core_ids = cluster_to_cores[cluster_id]

        max_possible_cluster_spill = sum(
            core_max_possible_mem[c]
            for c in cluster_core_ids
        )

        cluster_used_memory[cluster_id] = pulp.LpVariable(
            f"cluster_used_memory_{cluster_id}",
            lowBound=0,
            upBound=max_possible_cluster_spill,
            cat="Continuous",
        )

        cluster_spill_active[cluster_id] = pulp.LpVariable(
            f"cluster_spill_active_{cluster_id}",
            cat="Binary",
        )

        model += (
            cluster_used_memory[cluster_id]
            == pulp.lpSum(core_overflow[c] for c in cluster_core_ids)
        ), f"cluster_used_memory_def_{cluster_id}"

        # diff = cluster_used_memory[cluster_id] - cluster_budget
        # cluster_overflow[cluster_id] = max(0, diff)
        diff_expr = cluster_used_memory[cluster_id] - cluster_budget

        cluster_m = max(
            cluster_budget,
            max_possible_cluster_spill - cluster_budget,
            0,
        )

        model += (
            cluster_overflow[cluster_id] >= diff_expr
        ), f"cluster_overflow_lb_diff_{cluster_id}"

        model += (
            cluster_overflow[cluster_id] >= 0
        ), f"cluster_overflow_lb_zero_{cluster_id}"

        model += (
            cluster_overflow[cluster_id]
            <= diff_expr + cluster_m * (1 - cluster_spill_active[cluster_id])
        ), f"cluster_overflow_ub_diff_{cluster_id}"

        model += (
            cluster_overflow[cluster_id]
            <= cluster_m * cluster_spill_active[cluster_id]
        ), f"cluster_overflow_ub_zero_{cluster_id}"

    # -------------------------------
    # No-overlap on core constraints
    # -------------------------------
    #
    # Improvement merged here:
    # Only generate pairwise ordering constraints for cores that both jobs can
    # actually share. This is equivalent to the full model because a pair of jobs
    # cannot overlap on a core unless both jobs are eligible for that core. On
    # heterogeneous platforms this removes many redundant constraints.
    overlap_bin = {}

    for idx1 in range(len(job_ids)):
        for idx2 in range(idx1 + 1, len(job_ids)):
            i = job_ids[idx1]
            j = job_ids[idx2]

            common_cores = sorted(
                set(jobs[i].eligible_cores).intersection(jobs[j].eligible_cores)
            )

            if not common_cores:
                continue

            overlap_bin[i, j] = pulp.LpVariable(
                f"overlap_{i}_{j}",
                cat="Binary",
            )

            for c in common_cores:
                # If both i and j are on core c, one must precede the other.
                model += (
                    s[j]
                    >= f[i]
                    - big_m * (3 - overlap_bin[i, j] - x[i][c] - x[j][c])
                ), f"no_overlap_ij_{i}_{j}_{c}"

                model += (
                    s[i]
                    >= f[j]
                    - big_m * (2 + overlap_bin[i, j] - x[i][c] - x[j][c])
                ), f"no_overlap_ji_{i}_{j}_{c}"

    # -----------------------------------
    # Communication penalty of paths at task level
    # -----------------------------------
    explicit_path_penalty = {
        (comm.source, comm.target): comm.penalty
        for comm in problem.communication_paths
    }

    comm_penalty_weight = problem.comms_penalty_weight
    intra_core_weight = comm_penalty_weight.get("intra_core_weight", 0)
    inter_core_weight = comm_penalty_weight.get("inter_core_weight", 0)
    inter_cluster_weight = comm_penalty_weight.get("inter_cluster_weight", 0)

    comm_penalties = []
    comm_task_pairs = [
        (dep.predecessor, dep.successor)
        for dep in problem.dependencies
    ]

    z = {}

    for t1, t2 in comm_task_pairs:
        for c1 in tasks[t1].eligible_cores:
            for c2 in tasks[t2].eligible_cores:
                z[t1, t2, c1, c2] = pulp.LpVariable(
                    f"z_{t1}_{t2}_{c1}_{c2}",
                    cat="Binary",
                )

                # z[t1,t2,c1,c2] = 1 iff
                # y_alloc[t1][c1] = 1 and y_alloc[t2][c2] = 1.
                model += (
                    z[t1, t2, c1, c2] <= y_alloc[t1][c1]
                ), f"z_up1_{t1}_{t2}_{c1}_{c2}"

                model += (
                    z[t1, t2, c1, c2] <= y_alloc[t2][c2]
                ), f"z_up2_{t1}_{t2}_{c1}_{c2}"

                model += (
                    z[t1, t2, c1, c2]
                    >= y_alloc[t1][c1] + y_alloc[t2][c2] - 1
                ), f"z_low_{t1}_{t2}_{c1}_{c2}"

                if (c1, c2) in explicit_path_penalty:
                    penalty = explicit_path_penalty[(c1, c2)]
                elif c1 == c2:
                    penalty = intra_core_weight
                elif core_to_cluster_id[c1] == core_to_cluster_id[c2]:
                    penalty = inter_core_weight
                else:
                    penalty = inter_cluster_weight

                comm_penalties.append(penalty * z[t1, t2, c1, c2])

    # ----------------------------
    # Objective function
    # -----------------------------
    core_overflow_scale = problem.memory_penalty_scale.get(
        "core_overflow_scale",
        1,
    )

    cluster_overflow_scale = problem.memory_penalty_scale.get(
        "cluster_overflow_scale",
        1,
    )

    model += (
        core_overflow_scale * pulp.lpSum(core_overflow[c] for c in core_ids)
        + cluster_overflow_scale
        * pulp.lpSum(cluster_overflow[cluster_id] for cluster_id in cluster_ids)
        + pulp.lpSum(comm_penalties)
    )

    return model, {
        "x": x,
        "s": s,
        "f": f,
        "core_overflow": core_overflow,
        "cluster_overflow": cluster_overflow,
    }
