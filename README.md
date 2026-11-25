# Adaptive Workout Planner

A local web app that builds a flexible workout plan around your schedule.

## What it does

- Builds a rolling 10-day workout plan from your configurable workout rotation.
- Balances cardio and strength using recent workouts, avoids recently trained muscles when possible, respects time and calendar conflicts, and can favor Sunday runs.
- Rebuilds the remaining plan after completed or skipped workouts while filling other available slots in the 10-day window.
- Logs completed workouts with start and end times, tracks history, and lets you correct workout details.
- Syncs planned and completed workouts with a selected Google Calendar.
- Runs as a full stack app with Angular, FastAPI, PostgreSQL, and Docker Compose.

This repository currently contains the browser beta. Mobile and wearable integrations are outside this beta.

## Requirements

- Docker Desktop
- A Google Cloud project with the Google Calendar API enabled
- Google OAuth credentials for a Web application

## First-time setup

1. Copy `.env.example` to `.env` in the project root.
2. Set `POSTGRES_PASSWORD`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_TOKEN_ENCRYPTION_KEY`.
3. Generate a Fernet key for `GOOGLE_TOKEN_ENCRYPTION_KEY`:

   ```sh
   python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
   ```

4. Add `http://localhost:8000/auth/google/callback` as an authorized redirect URI in your Google OAuth client.

## Run the app

From the project root, start Docker Desktop and run:

```sh
docker compose up --build
```

Open the planner at <http://localhost:4200>. The API documentation is at <http://localhost:8000/docs>.

The API applies database migrations on startup. Connect Google Calendar in the planner and choose the calendar where workout events should be created. Refresh the plan after making calendar changes.

## Project structure

- `backend/` — FastAPI API, scheduling logic, database models, and migrations
- `frontend/` — Angular browser app
- `compose.yaml` — PostgreSQL, API, and frontend containers

## Current scope

This is a personal beta focused on the browser workflow and local Docker setup. Google OAuth must be configured for the account used to run it.
