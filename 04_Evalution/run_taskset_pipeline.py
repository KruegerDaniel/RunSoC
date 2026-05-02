import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


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


def load_config(path: Path | None) -> dict[str, Any]:
    if path is None:
        return DEFAULT_CONFIG.copy()

    if not path.is_file():
        raise FileNotFoundError(f"Config file does not exist: {path}")

    if path.suffix.lower() != ".json":
        raise ValueError(
            f"Unsupported config file type: {path.suffix}. "
            "Use .json, for example ./evaluation-config.json."
        )

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def validate_config(config: dict[str, Any]) -> None:
    required_top_level = [
        "soc_template_path",
        "solvers",
        "timeout_seconds",
        "generated_tasksets_dir",
        "solver_outputs_dir",
        "tasksets",
    ]

    for key in required_top_level:
        if key not in config:
            raise ValueError(f"Missing required config key: {key}")

    if "seed" in config and config["seed"] is not None:
        try:
            int(config["seed"])
        except ValueError:
            raise ValueError("seed must be an integer or null if provided.")

    if not isinstance(config["solvers"], list) or not config["solvers"]:
        raise ValueError("solvers must be a non-empty list.")

    if int(config["timeout_seconds"]) < 1:
        raise ValueError("timeout_seconds must be >= 1.")

    if not isinstance(config["tasksets"], list) or not config["tasksets"]:
        raise ValueError("tasksets must be a non-empty list.")

    for index, taskset_config in enumerate(config["tasksets"]):
        for key in ["num_tasks", "count", "filename_prefix"]:
            if key not in taskset_config:
                raise ValueError(f"Missing key tasksets[{index}]['{key}'].")

        if int(taskset_config["num_tasks"]) < 1:
            raise ValueError(f"tasksets[{index}]['num_tasks'] must be >= 1.")

        if int(taskset_config["count"]) < 1:
            raise ValueError(f"tasksets[{index}]['count'] must be >= 1.")

        if not str(taskset_config["filename_prefix"]).strip():
            raise ValueError(
                f"tasksets[{index}]['filename_prefix'] must not be empty."
            )


def run_command(command: list[str], cwd: Path) -> None:
    print()
    print("Running:")
    print(" ".join(command))
    print()

    completed = subprocess.run(command, cwd=cwd)

    if completed.returncode != 0:
        raise RuntimeError(
            f"Command failed with exit code {completed.returncode}: "
            f"{' '.join(command)}"
        )


def generate_tasksets(
    *,
    script_dir: Path,
    generator_script: Path,
    config: dict[str, Any],
) -> None:
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

            command = [
                sys.executable,
                str(generator_script),
                "--filename",
                filename,
                "--output-dir",
                str(generated_tasksets_dir),
                "--soc-template",
                str(soc_template_path),
                "--num_tasks",
                str(num_tasks),
            ]

            if base_seed is not None:
                generated_seed = int(base_seed) + i + (num_tasks * 10_000)
                command.extend(["--seed", str(generated_seed)])

            run_command(command, cwd=script_dir)


def run_solvers(
    *,
    script_dir: Path,
    runner_script: Path,
    config: dict[str, Any],
) -> None:
    generated_tasksets_dir = Path(config["generated_tasksets_dir"]).resolve()
    solver_outputs_dir = Path(config["solver_outputs_dir"]).resolve()

    solver_outputs_dir.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        str(runner_script),
        "--input-dir",
        str(generated_tasksets_dir),
        "--output-dir",
        str(solver_outputs_dir),
        "--solvers",
        *config["solvers"],
        "--timeout-seconds",
        str(config["timeout_seconds"]),
    ]

    run_command(command, cwd=script_dir)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate tasksets and run taskset_runner over them."
    )

    parser.add_argument(
        "config",
        nargs="?",
        type=Path,
        default=Path("./evaluation-config.json"),
        help="Path to evaluation config JSON. Default: ./evaluation-config.json",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    script_dir = Path("../01_Framework/Backend/experiments").resolve()
    generator_script = script_dir / "taskset_generator.py"
    runner_script = script_dir / "taskset_runner.py"

    if not generator_script.is_file():
        raise FileNotFoundError(f"Could not find: {generator_script}")

    if not runner_script.is_file():
        raise FileNotFoundError(f"Could not find: {runner_script}")

    config = load_config(args.config)
    validate_config(config)

    print("Evaluation config loaded.")
    print(f"Config file:             {args.config.resolve()}")
    print(f"Generated tasksets dir:  {Path(config['generated_tasksets_dir']).resolve()}")
    print(f"Solver outputs dir:      {Path(config['solver_outputs_dir']).resolve()}")
    print(f"Solvers:                 {', '.join(config['solvers'])}")
    print(f"Seed:                    {config.get('seed', None)}")

    generate_tasksets(
        script_dir=script_dir,
        generator_script=generator_script,
        config=config,
    )

    run_solvers(
        script_dir=script_dir,
        runner_script=runner_script,
        config=config,
    )

    print()
    print("Evaluation complete.")


if __name__ == "__main__":
    main()