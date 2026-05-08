from abc import ABC, abstractmethod

from schemas.schemas import ProblemInstance


class BaseSolver(ABC):
    name: str

    @abstractmethod
    def solve(self, problem: ProblemInstance, hints: dict = None) -> dict:
        pass