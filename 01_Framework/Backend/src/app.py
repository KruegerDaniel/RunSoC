import logging
import os
import sys
import uuid

from flask import Flask, jsonify, request, g
from flask_cors import CORS
from pydantic import ValidationError

from mappers.problem_instance_mapper import ProblemInstanceMapper
from scheduling.cpsat.cp_solver_service import CpSolverService
from services.presolver.feasability_service import FeasibilitySolverService
from scheduling.ga.ga_solver_service import GASolverService
from scheduling.ilp.ilp_solver_service import IlpSolverService
from services.scheduling_service import run_scheduling_request
from utils.logger import configure_logging

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)
CORS(app)

configure_logging(app, log_dir="logs", log_file="app.log", max_age_days=1)

logger = logging.getLogger(__name__)

feasability_service = FeasibilitySolverService()
solvers = {
    "CPSAT": CpSolverService(),
    "ILP": IlpSolverService(),
    "GA": GASolverService(),
}
mapper = ProblemInstanceMapper()


@app.before_request
def add_request_id():
    g.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))


@app.after_request
def add_request_id_header(response):
    response.headers["X-Request-ID"] = g.request_id
    return response

@app.route("/api/schedule", methods=["POST"])
def schedule():
    try:
        data = request.get_json() or {}
        logger.info(f"Scheduling request received")
        result, status = run_scheduling_request(data)
        logger.info(f"Scheduling request completed with status=%s", {status})
        return jsonify(result), status
    except Exception as e:
        logger.exception("Unhandled error in /api/schedule")
        return jsonify({"error": str(e)}), 500


@app.post("/api/solve/<solver_name>")
def solve(solver_name: str):
    try:
        data = request.get_json(silent=True) or {}
        problem = mapper.from_request_json(data)

        feasability = feasability_service.check_feasibility(problem)
        is_feasible = feasability.get("feasible", False)

        if not is_feasible:
            return jsonify(feasability), 400

        task_assignment = feasability.get("task_assignment", {})
        """
        for task in problem.tasks:
            if task.id in task_assignment and task_assignment[task.id] is not None:
                task.eligible_cores = [task_assignment[task.id]]
        """
        solver_key = solver_name.upper()
        solver = solvers.get(solver_key)

        if solver is None:
            logger.warning("Unknown solver requested: %s", solver_name)
            return jsonify({
                "error": f"Unknown solver '{solver_name}'",
                "available_solvers": list(solvers.keys()),
            }), 400

        logger.info(
            "Solver requested: %s | tasks=%s | cores=%s | clusters=%s",
            solver_key,
            len(problem.tasks),
            len(problem.cores),
            len(problem.clusters),
        )
        result = solver.solve(problem)

        logger.info("Solver completed: %s", solver_key)

        return jsonify(result), 200

    except ValidationError as e:
        logger.warning("Validation error in /api/solve/%s: %s", solver_name, e.errors())
        return jsonify({"error": e.errors()}), 400
    except Exception as e:
        logger.exception("Unhandled error in /api/solve/%s", solver_name)
        return jsonify({"error": str(e)}), 500

@app.get("/api/solve")
def list_solvers():
    return jsonify({"available_solvers": list(solvers.keys())}), 200


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"}), 200


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False, host="0.0.0.0", port=5001)