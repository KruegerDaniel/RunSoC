import argparse
import json
import logging
import multiprocessing
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable, Optional

BACKEND_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = BACKEND_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from mappers.problem_instance_mapper import ProblemInstanceMapper
from scheduling.cpsat.cp_solver_service import CpSolverService
from services.presolver import feasability_service
from scheduling.ga.ga_solver_service import GASolverService
from scheduling.ilp.ilp_solver_service import IlpSolverService

logger = logging.getLogger(__name__)

feasability_service = feasability_service.FeasibilitySolverService()

AVAILABLE_SOLVERS = {
    "CPSAT": CpSolverService,
    "CBC": IlpSolverService,
    "GA": GASolverService,
}


def _make_solver(solver_name: str, timeout_seconds: int):
    solver_cls = AVAILABLE_SOLVERS[solver_name]
    return solver_cls(time_limit_seconds=timeout_seconds)


def _start_isolated_process_group() -> None:
    """Put the worker into its own process group/session.

    CBC is executed by PuLP as a separate native subprocess. If the parent Python
    worker is killed without a separate process group, the CBC binary can survive
    as an orphan process and keep running after the experiment timeout. Creating
    a new process group lets the runner kill the Python worker and any external
    solver subprocesses together.
    """
    if os.name == "posix":
        try:
            os.setsid()
        except Exception:
            logger.exception("Failed to create isolated POSIX process session.")


def _terminate_process_tree(process: multiprocessing.Process, grace_seconds: float = 5.0) -> None:
    """Terminate a worker and its external solver subprocesses.

    On POSIX, this kills the whole process group created in the worker. On
    Windows, it uses taskkill /T /F as the closest standard-library equivalent.
    """
    pid = process.pid
    if pid is None:
        return

    if os.name == "posix":
        # The process-group id is the worker pid after os.setsid(). If the
        # worker already died but left CBC behind, the group may still exist.
        pgid = pid

        try:
            pgid = os.getpgid(pid)
        except ProcessLookupError:
            # The worker is gone; try the original pid as process-group id.
            pgid = pid
        except Exception:
            logger.exception("Could not resolve process group for pid=%s.", pid)

        try:
            os.killpg(pgid, signal.SIGTERM)
        except ProcessLookupError:
            return
        except Exception:
            logger.exception("SIGTERM process-group kill failed; falling back to process.terminate().")
            try:
                process.terminate()
            except Exception:
                logger.exception("process.terminate() also failed.")

        deadline = time.monotonic() + grace_seconds
        while time.monotonic() < deadline:
            process.join(timeout=0.1)
            if not process.is_alive():
                # CBC might still be alive in the process group even if the
                # Python worker has exited. Give the group a short grace period.
                time.sleep(0.2)
                break

        try:
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except Exception:
            logger.exception("SIGKILL process-group cleanup failed.")

        process.join(timeout=1.0)
        return

    # Windows fallback.
    try:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except Exception:
        logger.exception("taskkill failed; falling back to process.terminate().")
        try:
            process.terminate()
        except Exception:
            logger.exception("process.terminate() failed.")

    process.join(timeout=grace_seconds)


def _extract_evaluation_metadata(problem_instance) -> dict:
    if (
        hasattr(problem_instance, "evaluation")
        and hasattr(problem_instance.evaluation, "model_dump")
    ):
        return problem_instance.evaluation.model_dump()

    return {}


def _build_unsolved_solution(
    solver_name: str,
    status: str,
    problem_instance,
    runtime_seconds: Optional[float] = None,
    metadata: Optional[dict] = None,
    error: Optional[str] = None,
) -> dict:
    solution = {
        "solver": solver_name,
        "status": status,
        "feasible": False,
        "objective": None,
        "makespan": None,
        "evaluation": _extract_evaluation_metadata(problem_instance),
        "summary": {
            "task_template_count": len(problem_instance.tasks),
            "job_count": len(problem_instance.jobs),
            "scheduled_job_count": 0,
            "task_chain_count": len(problem_instance.task_chains),
            "dependency_template_count": len(problem_instance.dependencies),
            "job_dependency_count": len(problem_instance.job_dependencies),
            "core_count": len(problem_instance.cores),
            "cluster_count": len(problem_instance.clusters),
            "horizon": problem_instance.horizon,
        },
        "resource_usage": {
            "core_memory": [],
            "cluster_memory": [],
        },
        "schedule": [],
        "runtime_seconds": runtime_seconds,
        "metadata": metadata or {},
    }

    if error is not None:
        solution["error"] = error

    return solution


def _worker_solve(solver_name, problem_instance, timeout_seconds, return_dict):
    """Run one solver in an isolated process to sandbox memory/crashes/timeouts."""
    _start_isolated_process_group()

    solver = _make_solver(solver_name, timeout_seconds)

    feasability = feasability_service.check_feasibility(problem_instance)
    is_feasible = feasability.get("feasible", False)

    if not is_feasible:
        return_dict["solution"] = _build_unsolved_solution(
            solver_name=solver_name,
            status="PRESOLVER_INFEASIBLE",
            problem_instance=problem_instance,
            runtime_seconds=0,
            metadata={
                "presolver": feasability,
            },
        )
        return

    task_assignment = feasability.get("task_assignment", {})
    return_dict["solution"] = solver.solve(problem_instance, hints=task_assignment)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run taskset JSON files against selected RunSoC 2.0 solvers."
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
        help="Internal timeout passed to each solver, in seconds.",
    )
    parser.add_argument(
        "--watchdog-grace-seconds",
        type=int,
        default=30,
        help=(
            "Extra outer-process grace period after the solver timeout. "
            "This allows a solver to serialize its final incumbent instead of "
            "being killed exactly at its internal time limit."
        ),
    )
    parser.add_argument(
        "--kill-grace-seconds",
        type=float,
        default=5.0,
        help="Grace period between SIGTERM and SIGKILL/taskkill cleanup.",
    )

    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if not args.input_dir.is_dir():
        raise ValueError(f"Input directory does not exist: {args.input_dir}")

    if args.timeout_seconds < 1:
        raise ValueError(
            f"Timeout must be greater than 0, got {args.timeout_seconds}."
        )

    if args.watchdog_grace_seconds < 0:
        raise ValueError(
            "watchdog_grace_seconds must be non-negative, "
            f"got {args.watchdog_grace_seconds}."
        )

    if args.kill_grace_seconds < 0:
        raise ValueError(
            "kill_grace_seconds must be non-negative, "
            f"got {args.kill_grace_seconds}."
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
    watchdog_grace_seconds: int = 30,
    kill_grace_seconds: float = 5.0,
) -> None:
    logger.info(f"Running taskset: {taskset_path.name}")

    taskset = load_taskset(taskset_path)
    taskset.setdefault("evaluation", {})
    taskset["evaluation"].setdefault("taskset_id", taskset_path.stem)
    taskset["evaluation"].setdefault("source_file", str(taskset_path))

    problem_instance = mapper.from_request_json(taskset)

    for solver_name in solver_names:
        logger.info(f"  Running solver: {solver_name}")

        manager = multiprocessing.Manager()
        return_dict = manager.dict()

        p = multiprocessing.Process(
            target=_worker_solve,
            args=(solver_name, problem_instance, timeout_seconds, return_dict),
        )

        p.start()

        watchdog_seconds = timeout_seconds + watchdog_grace_seconds
        p.join(watchdog_seconds)

        if p.is_alive():
            logger.error(
                f"  [!] Solver {solver_name} exceeded watchdog after "
                f"{watchdog_seconds}s; killing process group."
            )

            _terminate_process_tree(p, grace_seconds=kill_grace_seconds)

            solution = _build_unsolved_solution(
                solver_name=solver_name,
                status="TIMEOUT",
                problem_instance=problem_instance,
                runtime_seconds=watchdog_seconds,
                metadata={
                    "timeout_seconds": timeout_seconds,
                    "watchdog_grace_seconds": watchdog_grace_seconds,
                    "watchdog_seconds": watchdog_seconds,
                    "kill_grace_seconds": kill_grace_seconds,
                    "killed_process_group": True,
                },
                error=(
                    f"Solver {solver_name} exceeded watchdog after "
                    f"{watchdog_seconds}s and was killed as a process group."
                ),
            )

        elif p.exitcode == 0 and "solution" in return_dict:
            solution = return_dict["solution"]

        else:
            # Make a best-effort cleanup in case the worker crashed after
            # spawning an external solver subprocess.
            _terminate_process_tree(p, grace_seconds=kill_grace_seconds)

            logger.error(
                f"  [!] Solver {solver_name} crashed or ran out of memory "
                f"(Exit code: {p.exitcode})"
            )

            solution = _build_unsolved_solution(
                solver_name=solver_name,
                status="CRASHED",
                problem_instance=problem_instance,
                runtime_seconds=None,
                metadata={
                    "exitcode": p.exitcode,
                    "kill_grace_seconds": kill_grace_seconds,
                },
                error=(
                    f"Solver {solver_name} crashed or ran out of memory "
                    f"(Exit code: {p.exitcode})"
                ),
            )

        write_solution(
            output_dir=output_dir,
            taskset_name=taskset_path.stem,
            solver_name=solver_name,
            solution=solution,
        )


def main(
    input_dir: Path = Path("input"),
    output_dir: Path = Path("output"),
    solvers: Iterable[str] = tuple(AVAILABLE_SOLVERS.keys()),
    timeout_seconds: int = 300,
    watchdog_grace_seconds: int = 30,
    kill_grace_seconds: float = 5.0,
):
    mapper = ProblemInstanceMapper()
    taskset_files = find_taskset_files(input_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    for taskset_path in taskset_files:
        run_solver_on_taskset(
            taskset_path=taskset_path,
            solver_names=solvers,
            output_dir=output_dir,
            mapper=mapper,
            timeout_seconds=timeout_seconds,
            watchdog_grace_seconds=watchdog_grace_seconds,
            kill_grace_seconds=kill_grace_seconds,
        )


if __name__ == "__main__":
    args = parse_args()
    validate_args(args)
    main(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        solvers=args.solvers,
        timeout_seconds=args.timeout_seconds,
        watchdog_grace_seconds=args.watchdog_grace_seconds,
        kill_grace_seconds=args.kill_grace_seconds,
    )
