import os
import sys

from flask import Flask, jsonify, request
from flask_cors import CORS
from pydantic import ValidationError

from mappers.problem_instance_mapper import ProblemInstanceMapper
from scheduling.cpsat.cp_solver_service import CpSolverService
from scheduling.ilp.ilp_solver_service import IlpSolverService
from schemas.schemas import ProblemInstance
from services.scheduling_service import run_scheduling_request

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)
CORS(app)

solvers = {
    "CPSAT": CpSolverService(),
    "ILP": IlpSolverService(),
}
mapper = ProblemInstanceMapper()


@app.route("/api/schedule", methods=["POST"])
def schedule():
    try:
        data = request.get_json() or {}
        result, status = run_scheduling_request(data)
        return jsonify(result), status
    except Exception as e:
        app.logger.exception("Unhandled error in /api/schedule")
        return jsonify({"error": str(e)}), 500


@app.post("/api/solve/<solver_name>")
def solve(solver_name: str):
    try:
        data = request.get_json(silent=True) or {}
        problem = mapper.from_request_json(data)

        solver_key = solver_name.upper()
        solver = solvers.get(solver_key)

        if solver is None:
            return jsonify({
                "error": f"Unknown solver '{solver_name}'",
                "available_solvers": list(solvers.keys()),
            }), 400

        app.logger.info(f"Solver requested: {solver_key}")
        result = solver.solve(problem)

        return jsonify(result), 200

    except ValidationError as e:
        return jsonify({"error": e.errors()}), 400
    except Exception as e:
        app.logger.exception(f"Unhandled error in /api/solve/{solver_name}")
        return jsonify({"error": str(e)}), 500


@app.get("/api/solve")
def list_solvers():
    return jsonify({"available_solvers": list(solvers.keys())}), 200


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"}), 200


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False, host="0.0.0.0", port=5001)