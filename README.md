# Adaptive Workout Planner

A personal workout planner with a rolling schedule, workout history, Google Calendar conflict checks, and a browser interface. The app currently runs locally with Docker Compose. Apple Watch / HealthKit import is not implemented yet; completed workouts can be logged in the app manually.

## What you need

- Docker Desktop
- A Google Cloud project with the Google Calendar API enabled
- Google OAuth credentials for a **Web application**

## First-time setup

1. From the project root, copy `.env.example` to `.env`.
2. Fill in the values in `.env`:
   - `POSTGRES_PASSWORD`: a local database password of your choice.
   - `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`: from your Google Cloud OAuth client.
   - `GOOGLE_TOKEN_ENCRYPTION_KEY`: generate a Fernet key with Python:

     ```sh
     python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
     ```

3. In Google Cloud, configure the OAuth consent screen. While the app is in testing, add the Google account you will use as a test user.
4. Add this exact authorized redirect URI to the OAuth client:

   ```text
   http://localhost:8000/auth/google/callback
   ```

5. Start Docker Desktop, then run from the project root:

   ```sh
   docker compose up --build
   ```

   The API applies database migrations when it starts. The first build can take a few minutes.

## Open the app

- Planner: <http://localhost:4200>
- API documentation: <http://localhost:8000/docs>
- API health check: <http://localhost:8000/health>

Connect Google Calendar from the app, choose the calendar where workouts should be created, then refresh the plan after calendar changes. Calendar events are checked for conflicts when the plan is rebuilt. The current app does not continuously watch Google Calendar in the background.

## Stop and restart

Stop the running services with `Ctrl+C`, or from another terminal in the project root run:

```sh
docker compose down
```

Start them again with `docker compose up`. PostgreSQL data is kept in the `postgres_data` Docker volume, so stopping the services does not erase workout history or calendar connection data.

To remove the database and all saved app data as well, run:

```sh
docker compose down --volumes
```

This permanently deletes the local database contents.

## Keep credentials private

`.env` contains passwords and Google credentials. Do not commit it or share its contents. Use `.env.example` as the safe template; it contains placeholders only.

## Current limits

- Calendar updates are applied when you refresh or rebuild the plan; automatic background calendar monitoring is not implemented.
- Apple Watch workouts are not imported yet. The app currently supports manual workout logging.
- This setup is for local development, not public production hosting.
