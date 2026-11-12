# Start from a small Python 3.13 image.
FROM python:3.13-slim

# Keep the application files under /app in the container.
WORKDIR /app

# Install the backend dependencies.
COPY backend/requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt

# Copy the API and its migration files.
COPY backend/app ./app
COPY backend/alembic.ini ./alembic.ini
COPY backend/migrations ./migrations

# Document the port used by the API.
EXPOSE 8000

# Start the FastAPI server when the container launches.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]