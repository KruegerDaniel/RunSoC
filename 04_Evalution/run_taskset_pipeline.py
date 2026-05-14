import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
FRAMEWORK_BACKEND_DIR = (SCRIPT_DIR / "../01_Framework/Backend/experiments").resolve()

if str(FRAMEWORK_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRAMEWORK_BACKEND_DIR))

import taskset_generator
import taskset_runner
from utils.logger import configure_logging


DEFAULT_CONFIG = {
    "platforms": [
        {
            "name": "default",
            "soc_template_path": "./default-soc.json",
        }
    ],
    "solvers": ["CPSAT", "CBC", "GA"],
    "timeout_seconds": 300,
    "generated_tasksets_dir": "output/generated_tasksets",
    "solver_outputs_dir": "output/solutions",
    "seed": None,
    "tasksets": [
        {
            "num_tasks": 100,
            "count": 1,
            "filename_prefix": "taskset_100",
        }
    ],
}

configure_logging(log_dir=".logs", log_file="evaluation.log", level="INFO")


def load_config(path: Optional[Path]) -> dict[str, Any]:
    if path is None:
        return DEFAULT_CONFIG.copy()

    if not path.is_file():
        raise FileNotFoundError(f"Config file does not exist: {path}")

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def validate_config(config: dict[str, Any]) -> None:
    if "platforms" not in config:
        raise ValueError("Config must contain a 'platforms' list.")

    if not isinstance(config["platforms"], list) or not config["platforms"]:
        raise ValueError("'platforms' must be a non-empty list.")

    for platform in config["platforms"]:
        if "name" not in platform:
            raise ValueError("Each platform must define 'name'.")
        if "soc_template_path" not in platform:
            raise ValueError(f"Platform {platform.get('name')} is missing 'soc_template_path'.")

        soc_template_path = Path(platform["soc_template_path"])
        if not soc_template_path.is_file():
            raise FileNotFoundError(
                f"SoC template for platform '{platform['name']}' does not exist: "
                f"{soc_template_path}"
            )

    if "tasksets" not in config:
        raise ValueError("Config must contain a 'tasksets' list.")

    if not isinstance(config["tasksets"], list) or not config["tasksets"]:
        raise ValueError("'tasksets' must be a non-empty list.")

    for taskset_config in config["tasksets"]:
        num_tasks = int(taskset_config["num_tasks"])
        count = int(taskset_config["count"])

        if num_tasks < 1:
            raise ValueError(f"num_tasks must be positive, got {num_tasks}.")

        if count < 1:
            raise ValueError(f"count must be positive, got {count}.")

        if "filename_prefix" not in taskset_config:
            raise ValueError("Each taskset entry must define 'filename_prefix'.")

    if "solvers" not in config or not config["solvers"]:
        raise ValueError("Config must contain a non-empty 'solvers' list.")

    timeout_seconds = int(config.get("timeout_seconds", 300))
    if timeout_seconds < 1:
        raise ValueError(f"timeout_seconds must be positive, got {timeout_seconds}.")


def sanitize_platform_name(name: str) -> str:
    cleaned = name.strip().lower()
    cleaned = cleaned.replace("-", "_")
    cleaned = cleaned.replace(" ", "_")
    cleaned = "".join(ch for ch in cleaned if ch.isalnum() or ch == "_")
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return cleaned


def make_taskset_filename(
    platform_name: str,
    filename_prefix: str,
    index: int,
) -> str:
    platform_key = sanitize_platform_name(platform_name)

    if not filename_prefix.startswith("taskset_"):
        raise ValueError(
            f"filename_prefix should start with 'taskset_', got: {filename_prefix}"
        )

    suffix = filename_prefix[len("taskset_"):]
    return f"taskset_{platform_key}_{suffix}_{index:03d}.json"


def make_generated_seed(
    base_seed: Optional[int],
    platform_index: int,
    num_tasks: int,
    taskset_index: int,
) -> Optional[int]:
    if base_seed is None:
        return None

    return int(base_seed) + (platform_index * 1_000_000) + (num_tasks * 10_000) + taskset_index


def generate_tasksets(config: dict[str, Any]) -> None:
    generated_tasksets_dir = Path(config["generated_tasksets_dir"]).resolve()
    base_seed = config.get("seed", None)

    generated_tasksets_dir.mkdir(parents=True, exist_ok=True)

    for platform_index, platform in enumerate(config["platforms"], start=1):
        platform_name = str(platform["name"])
        soc_template_path = Path(platform["soc_template_path"]).resolve()

        print(f"\n--- Generating tasksets for platform: {platform_name} ---")

        for taskset_config in config["tasksets"]:
            num_tasks = int(taskset_config["num_tasks"])
            count = int(taskset_config["count"])
            filename_prefix = str(taskset_config["filename_prefix"])

            for i in range(1, count + 1):
                filename = make_taskset_filename(
                    platform_name=platform_name,
                    filename_prefix=filename_prefix,
                    index=i,
                )

                generated_seed = make_generated_seed(
                    base_seed=base_seed,
                    platform_index=platform_index,
                    num_tasks=num_tasks,
                    taskset_index=i,
                )

                print(f"Calling generator: {filename}")

                taskset_generator.main(
                    filename=filename,
                    output_dir=generated_tasksets_dir,
                    soc_template=soc_template_path,
                    num_tasks=num_tasks,
                    seed=generated_seed,
                    platform_key=sanitize_platform_name(platform_name),
                )


def run_solvers(config: dict[str, Any]) -> None:
    generated_tasksets_dir = Path(config["generated_tasksets_dir"]).resolve()
    solver_outputs_dir = Path(config["solver_outputs_dir"]).resolve()

    print(f"\nCalling solver runner for input: {generated_tasksets_dir}")

    taskset_runner.main(
        input_dir=generated_tasksets_dir,
        output_dir=solver_outputs_dir,
        solvers=config["solvers"],
        timeout_seconds=int(config["timeout_seconds"]),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "config",
        nargs="?",
        type=Path,
        default=Path("./evaluation-config.json"),
    )
    args = parser.parse_args()

    config = load_config(args.config)
    validate_config(config)

    print("--- Starting Pipeline ---")
    generate_tasksets(config)
    run_solvers(config)
    print("\nEvaluation complete.")


if __name__ == "__main__":
    main()