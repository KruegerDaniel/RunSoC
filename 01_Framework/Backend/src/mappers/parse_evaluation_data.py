import re

from schemas.schemas import EvaluationMetadata


def _normalize_platform_key(platform_name: str | None) -> str | None:
    if not platform_name:
        return None

    s = platform_name.lower()

    if "renesas" in s or "rcar" in s or "r-car" in s:
        return "renesas"
    if "nvidia" in s or "jetson" in s or "orin" in s:
        return "nvidia"
    if "tda4" in s or "texas" in s or s.startswith("ti"):
        return "ti"

    cleaned = re.sub(r"[^a-z0-9]+", "_", s)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or None


def _parse_evaluation_metadata(data: dict) -> EvaluationMetadata:
    platform = data.get("platform", {}) or {}
    platform_name = platform.get("name")

    evaluation_data = data.get("evaluation", {}) or {}

    return EvaluationMetadata(
        taskset_id=evaluation_data.get("taskset_id"),
        platform_name=evaluation_data.get("platform_name") or platform_name,
        platform_key=evaluation_data.get("platform_key") or _normalize_platform_key(platform_name),
        source_file=evaluation_data.get("source_file"),
        seed=evaluation_data.get("seed"),
    )