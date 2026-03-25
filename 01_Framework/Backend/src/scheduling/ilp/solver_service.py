import pulp

from scheduling.ilp.model_builder import build_model
from scheduling.ilp.postprocess import extract_solution
from schemas.schemas import ProblemInstance, Task


def solve_instance(problem: ProblemInstance):
    print("Building problem")
    model, variables = build_model(problem)

    print("Solving problem")

    solver = pulp.PULP_CBC_CMD(msg=True, keepFiles=True, logPath="cbc.log")
    status = model.solve(solver)

    return extract_solution(problem, model, variables, status)

