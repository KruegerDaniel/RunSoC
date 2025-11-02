import os
import sys

from flask import Flask, jsonify, request
from flask_cors import CORS

from api.scheduling_service import run_scheduling_request

# Ensure local imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)
CORS(app)


@app.route('/api/schedule', methods=['POST'])
def schedule():
    try:
        data = request.get_json() or {}
        result, status = run_scheduling_request(data)
        return jsonify(result), status
    except Exception as e:
        # last line of defense, but most errors should be handled in service
        return jsonify({'error': str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'})


if __name__ == '__main__':
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=5001)
