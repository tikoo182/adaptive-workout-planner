from enum import StrEnum

# Workout categories understood by the planner.
# Broad training categories used to keep the rotation balanced.
class WorkoutCategory(StrEnum):
    CARDIO = "cardio"
    STRENGTH = "strength"


class WorkoutType(StrEnum):
    HIIT_LEGS = "hiit_legs"
    PUSH = "push"
    RUN = "run"
    LEGS = "legs"
    HIIT_ABS = "hiit_abs"
    PULL = "pull"
    CUSTOM = "custom"


# Map each workout type to its training category.
WORKOUT_CATEGORIES = {
    WorkoutType.HIIT_LEGS: WorkoutCategory.CARDIO,
    WorkoutType.PUSH: WorkoutCategory.STRENGTH,
    WorkoutType.RUN: WorkoutCategory.CARDIO,
    WorkoutType.LEGS: WorkoutCategory.STRENGTH,
    WorkoutType.HIIT_ABS: WorkoutCategory.CARDIO,
    WorkoutType.PULL: WorkoutCategory.STRENGTH,
    WorkoutType.CUSTOM: WorkoutCategory.STRENGTH,
}


# Return the category for one workout type.
def get_workout_category(workout_type: WorkoutType) -> WorkoutCategory:
    return WORKOUT_CATEGORIES[workout_type]


class WorkoutVariant(StrEnum):
    PUSH_DIPS = "push_dips"
    PUSH_PIKE_RUSSIAN = "push_pike_russian"
    PUSH_PIKE_WEIGHTED = "push_pike_weighted"
    PUSH_PIKE_ARCHER = "push_pike_archer"
    PULL_CHINUPS_AND_PULLUPS = "pull_chinups_and_pullups"
    PULL_DEAD_HANGS_AND_ABS = "pull_dead_hangs_and_abs"
    LEGS_LUNGES = "legs_lunges"
    LEGS_WEIGHTED_SITUPS = "legs_weighted_situps"


# The order each workout category uses to rotate through its variations.
WORKOUT_VARIANT_ROTATIONS = {
    WorkoutType.PUSH: (
        WorkoutVariant.PUSH_DIPS,
        WorkoutVariant.PUSH_PIKE_RUSSIAN,
        WorkoutVariant.PUSH_DIPS,
        WorkoutVariant.PUSH_PIKE_WEIGHTED,
        WorkoutVariant.PUSH_PIKE_ARCHER,
    ),
    WorkoutType.PULL: (
        WorkoutVariant.PULL_CHINUPS_AND_PULLUPS,
        WorkoutVariant.PULL_DEAD_HANGS_AND_ABS,
    ),
    WorkoutType.LEGS: (
        WorkoutVariant.LEGS_LUNGES,
        WorkoutVariant.LEGS_WEIGHTED_SITUPS,
    ),
}
