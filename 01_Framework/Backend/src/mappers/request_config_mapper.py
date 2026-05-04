def _parse_config(data: dict) -> tuple[dict, dict, int]:
    config = data.get("config", {})

    comms_penalty_weight = config.get("commsPenaltyWeight", {})
    comms_weight = {
        "intra_core_weight": comms_penalty_weight.get("intraCoreWeight", 0),
        "inter_core_weight": comms_penalty_weight.get("interCoreWeight", 8),
        "inter_cluster_weight": comms_penalty_weight.get("interClusterWeight", 15),
    }

    mem_penalty_scale = config.get("memoryPenaltyScale", {})
    mem_scale = {
        "core_overflow_scale": mem_penalty_scale.get("coreOverflowScale", 1),
        "cluster_overflow_scale": mem_penalty_scale.get("clusterOverflowScale", 1),
    }

    max_chain_jitter = config.get("maxChainJitter", 0)

    return comms_weight, mem_scale, max_chain_jitter
