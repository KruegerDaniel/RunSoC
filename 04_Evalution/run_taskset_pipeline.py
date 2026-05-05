import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
FRAMEWORK_BACKEND_DIR = (SCRIPT_DIR / "../01_Framework/Backend/experiments").resolve()

if str(FRAMEWORK_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRAMEWORK_BACKEND_DIR))

import taskset_generator
import taskset_runner
from utils.logger import configure_logging

DEFAULT_CONFIG = {
    "soc_template_path": "./default-soc.json",
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


def load_config(path: Path | None) -> dict[str, Any]:
    if path is None:
        return DEFAULT_CONFIG.copy()
    if not path.is_file():
        raise FileNotFoundError(f"Config file does not exist: {path}")
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def validate_config(config: dict[str, Any]) -> None:
    pass


def generate_tasksets(config: dict[str, Any]) -> None:
    generated_tasksets_dir = Path(config["generated_tasksets_dir"]).resolve()
    soc_template_path = Path(config["soc_template_path"]).resolve()
    base_seed = config.get("seed", None)

    generated_tasksets_dir.mkdir(parents=True, exist_ok=True)

    for taskset_config in config["tasksets"]:
        num_tasks = int(taskset_config["num_tasks"])
        count = int(taskset_config["count"])
        filename_prefix = str(taskset_config["filename_prefix"])

        for i in range(1, count + 1):
            filename = f"{filename_prefix}_{i:03d}.json"
            generated_seed = (int(base_seed) + i + (num_tasks * 10_000)) if base_seed is not None else None

            print(f"Calling generator: {filename}")
            # DIRECT CALL
            taskset_generator.main(
                filename=filename,
                output_dir=generated_tasksets_dir,
                soc_template=soc_template_path,
                num_tasks=num_tasks,
                seed=generated_seed
            )


def run_solvers(config: dict[str, Any]) -> None:
    generated_tasksets_dir = Path(config["generated_tasksets_dir"]).resolve()
    solver_outputs_dir = Path(config["solver_outputs_dir"]).resolve()

    print(f"\nCalling solver runner for input: {generated_tasksets_dir}")
    taskset_runner.main(
        input_dir=generated_tasksets_dir,
        output_dir=solver_outputs_dir,
        solvers=config["solvers"],
        timeout_seconds=int(config["timeout_seconds"])
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", nargs="?", type=Path, default=Path("./evaluation-config.json"))
    args = parser.parse_args()

    config = load_config(args.config)

    print("--- Starting Pipeline ---")
    generate_tasksets(config)
    run_solvers(config)
    print("\nEvaluation complete.")


if __name__ == "__main__":
    main()