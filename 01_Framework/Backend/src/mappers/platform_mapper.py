from typing import Optional

from mappers.validators import _validate_cluster_core_count
from schemas.schemas import Cluster, Core, MemoryNode, CommunicationPath


def _parse_platform(data: dict) -> tuple[list[Cluster], list[Core]]:
    platform = data.get("platform", {})
    clusters, cores = _extract_cluster_cores(data)

    declared_num_clusters = platform.get("numClusters")
    declared_num_cores = platform.get("numCores")

    if declared_num_clusters is not None and declared_num_clusters != len(clusters):
        raise ValueError(
            f"Expanded clusters={len(clusters)} does not match "
            f"platform.numClusters={declared_num_clusters}"
        )

    if declared_num_cores is not None and declared_num_cores != len(cores):
        raise ValueError(
            f"Expanded cores={len(cores)} does not match "
            f"platform.numCores={declared_num_cores}"
        )

    return clusters, cores


def _extract_cluster_cores(data: dict) -> tuple[list[Cluster], list[Core]]:
    raw_clusters = data.get("platform", {}).get("clusters", [])

    clusters: list[Cluster] = []
    cores: list[Core] = []

    for raw_cluster in raw_clusters:
        concrete_clusters = _expand_cluster(raw_cluster)
        clusters.extend(concrete_clusters)

        for concrete_cluster in concrete_clusters:
            concrete_cores = _expand_cores_for_cluster(
                raw_cluster=raw_cluster,
                concrete_cluster=concrete_cluster,
                base_cluster_id=raw_cluster.get("id"),
            )
            cores.extend(concrete_cores)

        _validate_cluster_core_count(raw_cluster)

    return clusters, cores


def _expand_cluster(raw_cluster: dict) -> list[Cluster]:
    memory = raw_cluster.get("memory", [])

    base_cluster = Cluster(
        id=raw_cluster.get("id"),
        name=raw_cluster.get("name"),
        type=raw_cluster.get("type", "application"),
        memory_budget=sum(m.get("sizeKB", 0) for m in memory),
        notes=raw_cluster.get("notes", ""),
    )

    cluster_count = raw_cluster.get("count", 1)
    if cluster_count < 1:
        raise ValueError(f"Cluster {base_cluster.id}: count must be >= 1")

    clusters = [base_cluster]
    clusters.extend(
        _duplicate_cluster(
            base_cluster=base_cluster,
            count=cluster_count,
        )
    )

    return clusters


def _expand_cores_for_cluster(
        raw_cluster: dict,
        concrete_cluster: Cluster,
        base_cluster_id: str,
) -> list[Core]:
    cores: list[Core] = []

    for raw_core in raw_cluster.get("cores", []):
        base_core_id = raw_core.get("id")

        core_id = base_core_id
        core_name = raw_core.get("name")

        if concrete_cluster.id != base_cluster_id:
            core_id = f"{base_core_id}_{concrete_cluster.id}"
            if core_name:
                core_name = f"{core_name}_{concrete_cluster.id}"

        base_core = Core(
            id=core_id,
            name=core_name,
            cluster_id=concrete_cluster.id,
            execution_domain=raw_core.get("executionDomain", "general_purpose"),
            wcet_scale=raw_core.get("wcetScale", 1.0),
            memory_budget=raw_core.get("localMemoryKB", 0),
            supported_task_types=raw_core.get(
                "supportedTaskTypes",
                ["event", "periodic"],
            ),
            notes=raw_core.get("notes", ""),
        )

        core_count = raw_core.get("count", 1)
        if core_count < 1:
            raise ValueError(
                f"Core {base_core_id} in cluster {concrete_cluster.id}: "
                f"count must be >= 1"
            )

        expanded = [base_core]
        expanded.extend(
            _duplicate_core(
                base_core=base_core,
                count=core_count,
                cluster_id=concrete_cluster.id,
            )
        )

        cores.extend(expanded)

    return cores


def _duplicate_cluster(
        base_cluster: Cluster,
        count: int,
) -> list[Cluster]:
    return [
        Cluster(
            id=f"{base_cluster.id}_{i}",
            name=f"{base_cluster.name}_{i}" if base_cluster.name else f"{base_cluster.id}_{i}",
            type=base_cluster.type,
            memory_budget=base_cluster.memory_budget,
            memory_type=base_cluster.memory_type,
            memory_level=base_cluster.memory_level,
            notes=base_cluster.notes,
        )
        for i in range(1, count)
    ]


def _duplicate_core(
        base_core: Core,
        count: int,
        cluster_id: str,
) -> list[Core]:
    return [
        Core(
            id=f"{base_core.id}_{i}",
            name=f"{base_core.name}_{i}" if base_core.name else f"{base_core.id}_{i}",
            cluster_id=cluster_id,
            execution_domain=base_core.execution_domain,
            wcet_scale=base_core.wcet_scale,
            memory_budget=base_core.memory_budget,
            supported_task_types=list(base_core.supported_task_types),
            notes=base_core.notes,
        )
        for i in range(1, count)
    ]


def _extract_memory_nodes(
        data: dict,
        cl_ids: Optional[list[str]] = None,
) -> list[MemoryNode]:
    cl_id_set = set(cl_ids or [])
    raw_memory_nodes = data.get("platform", {}).get("memoryNodes", [])

    memory_nodes: list[MemoryNode] = []

    for raw_node in raw_memory_nodes:
        capacity_gb = raw_node.get("capacityGB")
        memory_node_id = raw_node.get("id")

        memory_node = MemoryNode(
            id=memory_node_id,
            name=raw_node.get("name"),
            type=raw_node.get("type", "dram"),
            scope=raw_node.get("scope", "system"),
            accessible_by=raw_node.get("accessibleBy", []),
            capacity=capacity_gb * (1024 ** 2) if capacity_gb else 0,
            notes=raw_node.get("notes", ""),
        )

        for cluster_id in memory_node.accessible_by:
            if cl_id_set and cluster_id not in cl_id_set:
                raise ValueError(
                    f"MemoryNode {memory_node_id}: cluster {cluster_id} "
                    f"referenced in accessibleBy is not in the platform"
                )

        memory_nodes.append(memory_node)

    return memory_nodes


def _parse_comms(data: dict, core_ids: set[str]) -> list[CommunicationPath]:
    config = data.get("config", {})
    generate_comms = config.get("generateComms", True)

    raw_paths = data.get("communicationPaths", [])

    if not generate_comms:
        # Directed full graph count.
        required_edges = len(core_ids) * (len(core_ids) - 1)

        if len(raw_paths) < required_edges:
            raise ValueError(
                f"communicationPaths={len(raw_paths)} is less than the "
                f"directed full core graph edge count={required_edges}"
            )

    communication_paths: list[CommunicationPath] = []

    for raw_path in raw_paths:
        source = raw_path.get("source")
        target = raw_path.get("target")

        if source not in core_ids or target not in core_ids:
            raise ValueError(
                f"Communication path {source} -> {target} contains invalid core IDs"
            )

        communication_paths.append(
            CommunicationPath(
                source=source,
                target=target,
                penalty=raw_path.get("penalty", 0),
                notes=raw_path.get("notes", ""),
            )
        )

    return communication_paths
