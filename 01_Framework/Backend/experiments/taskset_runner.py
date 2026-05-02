import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

BACKEND_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = BACKEND_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from mappers.problem_instance_mapper import ProblemInstanceMapper
from scheduling.cpsat.cp_solver_service import CpSolverService
from scheduling.ga.ga_solver_service import GASolverService
from scheduling.ilp.ilp_solver_service import IlpSolverService


AVAILABLE_SOLVERS = {
    "CPSAT": CpSolverService,
    "CBC": IlpSolverService,
    "GA": GASolverService,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run taskset JSON files against selected solvers."
    )

    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("input"),
        help="Directory containing taskset JSON files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory where solver outputs will be written.",
    )
    parser.add_argument(
        "--solvers",
        nargs="+",
        default=list(AVAILABLE_SOLVERS.keys()),
        choices=AVAILABLE_SOLVERS.keys(),
        help="Solvers to run.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=300,
        help="Timeout for each solver in seconds.",
    )

    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if not args.input_dir.is_dir():
        raise ValueError(f"Input directory does not exist: {args.input_dir}")

    if args.timeout_seconds < 1:
        raise ValueError(
            f"Timeout must be greater than 0, got {args.timeout_seconds}."
        )


def find_taskset_files(input_dir: Path) -> list[Path]:
    json_files = sorted(input_dir.glob("*.json"))

    if not json_files:
        raise ValueError(f"No JSON taskset files found in: {input_dir}")

    return json_files


def load_taskset(taskset_path: Path) -> dict:
    with taskset_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_solution(
    output_dir: Path,
    taskset_name: str,
    solver_name: str,
    solution: dict,
) -> None:
    taskset_output_dir = output_dir / taskset_name
    taskset_output_dir.mkdir(parents=True, exist_ok=True)

    output_path = taskset_output_dir / f"{solver_name}_solution.json"

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(solution, file, indent=2)


def run_solver_on_taskset(
    taskset_path: Path,
    solver_names: Iterable[str],
    output_dir: Path,
    mapper: ProblemInstanceMapper,
    timeout_seconds: int = 300,
) -> None:
    print(f"Running taskset: {taskset_path.name}")

    taskset = load_taskset(taskset_path)
    problem_instance = mapper.from_request_json(taskset)

    for solver_name in solver_names:
        print(f"  Running solver: {solver_name}")

        solver = AVAILABLE_SOLVERS[solver_name]()
        solution = solver.solve(problem_instance)

        write_solution(
            output_dir=output_dir,
            taskset_name=taskset_path.stem,
            solver_name=solver_name,
            solution=solution,
        )


def main() -> None:
    args = parse_args()
    validate_args(args)

    mapper = ProblemInstanceMapper()
    taskset_files = find_taskset_files(args.input_dir)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    for taskset_path in taskset_files:
        run_solver_on_taskset(
            taskset_path=taskset_path,
            solver_names=args.solvers,
            output_dir=args.output_dir,
            mapper=mapper,
        )


if __name__ == "__main__":
    main()