from pydantic import BaseModel, Field, model_validator


MUSCLE_GROUPS = [
    "chest", "back", "shoulders", "biceps", "triceps", "forearms",
    "core", "glutes", "quadriceps", "hamstrings", "calves",
]


class WorkoutDefinition(BaseModel):
    id: str = Field(min_length=1, max_length=32, pattern=r"^[a-z0-9_]+$")
    name: str = Field(min_length=1, max_length=60)
    category: str = Field(pattern=r"^(cardio|strength|other)$")
    variants: list[str] = Field(default_factory=list)
    variant_muscles: dict[str, list[str]] = Field(default_factory=dict)
    variant_uses_rings: dict[str, bool] = Field(default_factory=dict)
    muscles: list[str] = Field(default_factory=list)
    uses_rings: bool = False
    is_hiit: bool = False
    enabled: bool = True

    @model_validator(mode="after")
    def fill_variant_ring_defaults(self):
        for variant in self.variants:
            self.variant_uses_rings.setdefault(
                variant,
                self.uses_rings or (self.id == "push" and variant == "push_dips"),
            )
        return self


class PlannerTimingSettings(BaseModel):
    earliest_start: str = "07:00"
    latest_start: str = "20:00"
    evening_start: str = "17:30"
    latest_ring_morning_start: str = "09:00"
    latest_non_ring_morning_start: str = "11:00"
    latest_hiit_start: str = "09:00"
    workout_duration_minutes: int = Field(default=60, ge=15, le=240)
    calendar_buffer_minutes: int = Field(default=60, ge=0, le=240)
    max_consecutive_workout_days: int = Field(default=3, ge=1, le=10)
    muscle_recovery_days: int = Field(default=1, ge=0, le=14)


class PlannerSettings(BaseModel):
    workouts: list[WorkoutDefinition]
    rotation: list[str]
    timing: PlannerTimingSettings = Field(default_factory=PlannerTimingSettings)

    @model_validator(mode="after")
    def validate_rotation(self):
        definitions = {item.id: item for item in self.workouts}
        if not self.rotation:
            raise ValueError("Add at least one workout to the rotation.")
        if len(self.rotation) != len(set(self.rotation)):
            raise ValueError("A workout can only appear once in the rotation.")
        if any(workout_id not in definitions for workout_id in self.rotation):
            raise ValueError("The rotation can only include saved workouts.")
        if not any(definitions[workout_id].enabled for workout_id in self.rotation):
            raise ValueError("Include at least one workout in the rotation.")
        if len(definitions) != len(self.workouts):
            raise ValueError("Workout identifiers must be unique.")
        return self


class PlannerSettingsResponse(PlannerSettings):
    muscle_groups: list[str] = Field(default_factory=lambda: MUSCLE_GROUPS.copy())


DEFAULT_SETTINGS = PlannerSettings(
    workouts=[
        WorkoutDefinition(id="hiit_legs", name="HIIT Legs", category="cardio", muscles=["quadriceps", "glutes", "hamstrings"], is_hiit=True),
        WorkoutDefinition(id="push", name="Push", category="strength", variants=["push_dips", "push_pike_russian", "push_dips", "push_pike_weighted", "push_pike_archer"], variant_muscles={"push_dips": ["chest", "shoulders", "triceps"], "push_pike_russian": ["shoulders", "triceps"], "push_pike_weighted": ["shoulders", "triceps"], "push_pike_archer": ["chest", "shoulders", "triceps"]}, variant_uses_rings={"push_dips": True, "push_pike_russian": False, "push_pike_weighted": False, "push_pike_archer": False}, muscles=["chest", "shoulders", "triceps"]),
        WorkoutDefinition(id="run", name="Run", category="cardio", muscles=["quadriceps", "hamstrings", "glutes", "calves"]),
        WorkoutDefinition(id="legs", name="Legs", category="strength", variants=["legs_lunges", "legs_weighted_situps"], variant_muscles={"legs_lunges": ["quadriceps", "glutes", "hamstrings"], "legs_weighted_situps": ["core"]}, muscles=["quadriceps", "glutes", "hamstrings"]),
        WorkoutDefinition(id="hiit_abs", name="HIIT Abs", category="cardio", muscles=["core"], is_hiit=True),
        WorkoutDefinition(id="pull", name="Pull", category="strength", variants=["pull_chinups_and_pullups", "pull_dead_hangs_and_abs"], variant_muscles={"pull_chinups_and_pullups": ["back", "biceps", "forearms"], "pull_dead_hangs_and_abs": ["back", "forearms", "core"]}, variant_uses_rings={"pull_chinups_and_pullups": True, "pull_dead_hangs_and_abs": True}, muscles=["back", "biceps", "forearms"], uses_rings=True),
    ],
    rotation=["hiit_legs", "push", "run", "legs", "hiit_abs", "pull"],
)
