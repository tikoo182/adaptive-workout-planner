from fastapi import FastAPI
from .api.plan import router as plan_router
from .api.completed_workouts import router as completed_workouts_router
from .api.google_calendar import router as google_calendar_router
from .api.settings import router as settings_router


# Main entry point for the API.
app = FastAPI(title="Adaptive Workout Planner API")

app.include_router(plan_router)
app.include_router(completed_workouts_router)
app.include_router(google_calendar_router)
app.include_router(settings_router)

# Confirm the API is responding.
@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
