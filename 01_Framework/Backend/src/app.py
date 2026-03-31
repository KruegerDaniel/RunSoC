import os
import sys

from flask import Flask, jsonify, request
from flask_cors import CORS

from api.scheduling_service import run_scheduling_request
from scheduling.cpsat.cp_solver_service import CpSolverService
from scheduling.ilp.ilp_solver_service import IlpSolverService
from schemas.schemas import ProblemInstance

# Ensure local imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)
CORS(app)

solvers = {
    "CPSAT": CpSolverService(),
    "ILP": IlpSolverService()
}

@app.route('/api/schedule', methods=['POST'])
def schedule():
    try:
        data = request.get_json() or {}
        result, status = run_scheduling_request(data)
        return jsonify(result), status
    except Exception as e:
        # last line of defense, but most errors should be handled in service
        return jsonify({'error': str(e)}), 500

@app.post('/api/solve')
def solve():
    print("Working")
    solver_name = request.args.get('solver').upper()
    try:
        data = request.get_json()
        problem = ProblemInstance(**data)

        result = {}
        if solver_name in solvers:
            app.logger.info(f"Solver requested: {solver_name}")
            result = solvers[solver_name].solve_instance(problem)

        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'})


if __name__ == '__main__':
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=5001)
