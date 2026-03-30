import pulp

from config import Config
from scheduling.ilp.model_builder import build_model
from scheduling.ilp.postprocess import extract_solution
from schemas.schemas import ProblemInstance, Task


def solve_instance(problem: ProblemInstance):
    print("Building problem")
    model, variables = build_model(problem)

    print("Solving problem")
    timelimit = Config.PULP_TIMELIMIT_SECONDS
    solver = pulp.PULP_CBC_CMD(msg=True, keepFiles=True, logPath="cbc.log", timeLimit=timelimit)
    status = model.solve(solver)

    return extract_solution(problem, model, variables, status)

