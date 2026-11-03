from enum import StrEnum

# Workout categories understood by the planner.


class WorkoutType(StrEnum):
    HIIT_LEGS = "hiit_legs"
    PUSH = "push"
    RUN = "run"
    LEGS = "legs"
    HIIT_ABS = "hiit_abs"
    PULL = "pull"