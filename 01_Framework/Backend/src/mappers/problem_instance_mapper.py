from collections import defaultdict, deque
from enum import Enum

from schemas.schemas import ProblemInstance, Cluster, Core, MemoryNode, Task, Dependency


class PlatformObjectType(str, Enum):
    CLUSTER = "cluster"
    CORE = "core"
    MEMORY_NODE = "memory_node"


class ProblemInstanceMapper:

    def from_request_json(self, data: dict) -> ProblemInstance:
        """
        Map a solver request JSON to a ProblemInstance object.
        Also validates values
        :param data: JSON data following empty_soc.json format
        :return: Mapped instance of ProblemInstance
        """
        comms_weight, mem_scale = self._extract_config(data)

        soc_platform = data.get("platform", {})
        num_clusters = soc_platform.get("numClusters")
        num_cores = soc_platform.get("numCores")
        clusters, cores = self._extract_cluster_cores(data)
        if num_clusters != len(clusters):
            raise ValueError(
                f"Number of clusters in the problem instance ({len(clusters)}) does not match the number of clusters specified in the request ({num_clusters}).")
        if num_cores != len(cores):
            raise ValueError(
                f"Number of cores in the problem instance ({len(cores)}) does not match the number of cores specified in the request ({num_cores}).")

        memory_nodes = self._extract_memory_nodes(data, cl_ids=[c.id for c in clusters])
        comms = self._extract_comms(data)

        tasks, dependencies = self._extract_taskset(data)
        tasks = self._map_task_to_domain_core(tasks, cores)

        return ProblemInstance(
            tasks=tasks,
            dependencies=dependencies,
            clusters=clusters,
            cores=cores,
            communications=comms,
            memory_nodes=memory_nodes,
            memory_penalty_scale=mem_scale,
            comms_penalty_weight=comms_weight,
        )

    def _extract_config(self, data: dict):
        config = data.get("config", {})
        comms_penalty_weight = config.get("commsPenaltyWeight", {})
        comms_weight = {
            "intra_core_weight": comms_penalty_weight.get("intraCoreWeight", 0),
            "inter_core_weight": comms_penalty_weight.get("interCoreWeight", 8),
            "inter_cluster_weight": comms_penalty_weight.get("interClusterWeight", 15),
            "inter_app_weight": comms_penalty_weight.get("interAppWeight", 15),
        }

        mem_penalty_scale = config.get("memoryPenaltyScale", {})
        mem_scale = {
            "inter_core_scale": mem_penalty_scale.get("interCoreScale", 1),
            "inter_cluster_scale": mem_penalty_scale.get("interClusterScale", 1),
        }
        return comms_weight, mem_scale

    def _extract_cluster_cores(self, data: dict) -> tuple[list[Cluster], list[Core]]:
        raw_clusters = data.get("platform", {}).get("clusters", [])
        clusters: list[Cluster] = []
        cores: list[Core] = []

        for cl in raw_clusters:
            memory = cl.get("memory", [])
            base_cluster = Cluster(
                id=cl.get("id"),
                name=cl.get("name"),
                execution_domain=cl.get("executionDomain"),
                memory_budget=sum(m.get("sizeKB", 0) for m in memory),
                notes=cl.get("notes", ""),
            )

            cluster_count = cl.get("count", 1)
            if cluster_count < 1:
                raise ValueError(f"Cluster {base_cluster.id}: count must be >= 1")

            concrete_clusters = [base_cluster]
            concrete_clusters.extend(
                self._duplicate_object(
                    obj_type=PlatformObjectType.CLUSTER,
                    obj=base_cluster,
                    iterations=cluster_count - 1,
                    id_prefix=base_cluster.id,
                )
            )
            clusters.extend(concrete_clusters)

            cluster_core_total = 0

            for concrete_cluster in concrete_clusters:
                for c in cl.get("cores", []):
                    base_core = Core(
                        id=c.get("id"),
                        name=c.get("name"),
                        cluster_id=concrete_cluster.id,
                        execution_domain=c.get("executionDomain", base_cluster.execution_domain),
                        wcet_scale=c.get("wcetScale"),
                        memory_budget=c.get("localMemoryKB"),
                        supported_task_types=c.get("supportedTaskTypes"),
                    )

                    core_count = c.get("count", 1)
                    if core_count < 1:
                        raise ValueError(
                            f"Core {c.get('id')} in cluster {concrete_cluster.id}: count must be >= 1"
                        )

                    if concrete_cluster.id != base_cluster.id:
                        base_core.id = f"{c.get('id')}_{concrete_cluster.id}"
                        if base_core.name:
                            base_core.name = f"{base_core.name}_{concrete_cluster.id}"

                    concrete_cores = [base_core]
                    concrete_cores.extend(
                        self._duplicate_object(
                            obj_type=PlatformObjectType.CORE,
                            obj=base_core,
                            iterations=core_count - 1,
                            id_prefix=base_core.id,
                            cluster_id=concrete_cluster.id,
                        )
                    )

                    cores.extend(concrete_cores)
                    cluster_core_total += len(concrete_cores)

            declared_num_cores = cl.get("numCores")
            expected_per_cluster = 0
            for c in cl.get("cores", []):
                expected_per_cluster += c.get("count", 1)

            if declared_num_cores != expected_per_cluster:
                raise ValueError(
                    f"Cluster {base_cluster.name}[{base_cluster.id}]: "
                    f"numCores={declared_num_cores} does not match expanded core count "
                    f"{expected_per_cluster}."
                )

        return clusters, cores

    def _extract_memory_nodes(self, data: dict, cl_ids: list[str] = None):
        raw_memory_nodes = data.get("platform", {}).get("memoryNodes", [])
        memory_nodes = []
        for mn in raw_memory_nodes:
            capacity_gb = mn.get("capacityGB")
            memory_node_id = mn.get("id")
            memory_node = MemoryNode(
                id=memory_node_id,
                name=mn.get("name"),
                type=mn.get("type", "dram"),
                scope=mn.get("scope", "system"),
                accessible_by=mn.get("accessibleBy", []),
                capacity=mn.get("capacityGB") * (1024 ** 2) if capacity_gb else 0
            )
            # check accessibility values
            for cl in memory_node.accessible_by:
                if cl not in cl_ids:
                    raise ValueError(
                        f"MemoryNode {memory_node_id}: Cluster {cl} referenced in accessibleBy is not in the problem instance.")
            memory_nodes.append(memory_node)
        return memory_nodes

    def _extract_comms(self, data: dict):
        config = data.get("config", {})

        is_generate_mode = config.get("generateComms", True)
        if not is_generate_mode:
            num_pairings = len(self.problem_instance.cores) * (
                    len(self.problem_instance.cores) - 1) // 2
        # todo: implement later. Assuming is_generate_mode
        return []

    def _extract_taskset(self, data: dict, dup_id_suffix: str = "_2"):
        """
        Extracts tasks and dependencies from JSON.
        Duplicates periodic tasks and their entire task chain, once.
        :param data:
        :return:
        """
        raw_tasks = data.get("tasks", [])
        tasks = []
        task_dict = {}
        dependencies = []
        adj_list = defaultdict(list)

        for t in raw_tasks:
            task = Task(
                id=t.get("id"),
                name=t.get("name"),
                required_domain=t.get("requiredDomain"),
                task_type="periodic" if t.get("period") > 0 else "event",
                duration=t.get("wcet"),
                period=t.get("period", 0),
                memory=t.get("memoryUsageKB"),
                eligible_cores=t.get("eligibleCores", [])
            )
            tasks.append(task)
            task_dict[task.id] = task

        for t in raw_tasks:
            deps = t.get("dependencies", [])
            t_id = t.get("id")
            for d in deps:
                dependencies.append(Dependency(
                    predecessor=d,
                    successor=t_id
                ))
                adj_list[d].append(t_id)

        # Periodic duplication via graph traversal
        new_tasks_map = {}
        new_dependencies = []
        periodics = [t for t in tasks if t.task_type == "periodic"]

        for p in periodics:
            # Queue for BFS
            queue = deque([p.id])
            visited = set([p.id])

            while queue:
                curr_id = queue.popleft()
                curr_task = task_dict[curr_id]
                dup_id = f"{curr_id}{dup_id_suffix}"

                if dup_id not in new_tasks_map:
                    new_tasks_map[dup_id] = Task(
                        id=dup_id,
                        name=f"{curr_task.name}{dup_id_suffix}",
                        required_domain=curr_task.required_domain,
                        task_type=curr_task.task_type,
                        duration=curr_task.duration,
                        period=curr_task.period,
                        memory=curr_task.memory,
                        eligible_cores=curr_task.eligible_cores,
                    )

                for succ in adj_list[curr_id]:
                    succ_dup_id = f"{succ}{dup_id_suffix}"
                    new_dependencies.append(Dependency(
                        predecessor=dup_id,
                        successor=succ_dup_id
                    ))

                    if succ not in visited:
                        queue.append(succ)
                        visited.add(succ)

        tasks.extend(new_tasks_map.values())
        dependencies.extend(new_dependencies)

        return tasks, dependencies

    def _map_task_to_domain_core(self, tasks: list[Task], cores: list[Core]) -> list[Task]:

        core_domain_map = defaultdict(list)
        for c in cores:
            core_domain_map[c.execution_domain].append(c.id)

        for t in tasks:
            t_domain = t.required_domain
            t.eligible_cores.extend(core_domain_map.get(t_domain, []))

        return tasks

    def _duplicate_object(
            self,
            obj_type: PlatformObjectType,
            obj,
            iterations: int,
            id_prefix: str,
            cluster_id: str | None = None,
    ) -> list[Cluster] | list[Core] | list[MemoryNode]:
        """
        Helper function to duplicate platform objects (core, cluster, memory node) if count is specified in request.
        """
        duplicates = []

        for i in range(1, iterations + 1):
            new_id = f"{id_prefix}_{i}"

            if obj_type == PlatformObjectType.CLUSTER:
                dup = Cluster(
                    id=new_id,
                    name=f"{obj.name}_{i}" if obj.get("name") else new_id,
                    execution_domain=obj.get("executionDomain"),
                    memory_budget=sum(m.get("sizeKB") for m in obj.get("memory", [])),
                    notes=obj.get("notes", "")
                )
                duplicates.append(dup)

            elif obj_type == PlatformObjectType.CORE:
                dup = Core(
                    id=new_id,
                    name=f"{obj.name}_{i}" if obj.get("name") else new_id,
                    cluster_id=cluster_id if cluster_id is not None else obj.get("clusterId"),
                    execution_domain=obj.get("executionDomain"),
                    wcet_scale=obj.get("wcetScale"),
                    memory_budget=obj.get("localMemoryKB"),
                    supported_task_types=obj.get("supportedTaskTypes", []),
                )
                duplicates.append(dup)
            else:
                raise ValueError(f"Invalid object type for duplication: {obj_type}")

        return duplicates
