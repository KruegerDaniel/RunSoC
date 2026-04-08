from dataclasses import dataclass

@dataclass
class ScheduleEntry:
    task: str
    start_time: int
    finish_time: int
    core: str
    eligible_time: int
