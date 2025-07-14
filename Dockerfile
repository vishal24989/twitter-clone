# Dockerfile

# --- Build Stage ---
FROM python:3.10-slim as builder

WORKDIR /app

# Install poetry
RUN pip install poetry

# Copy dependency definition files
COPY poetry.lock pyproject.toml ./

# Configure Poetry to create the venv in the project's root
RUN poetry config virtualenvs.in-project true

# Install dependencies
RUN poetry install --only main --no-root


# --- Final Stage ---
FROM python:3.10-slim

WORKDIR /app

# Copy the virtual environment from the builder stage
COPY --from=builder /app/.venv ./.venv

# Add the venv to the PATH
ENV PATH="/app/.venv/bin:$PATH"

# Copy ALL the source code from your local machine into the container
# This is the key change that fixes the error.
COPY . .

# Correct the command to point to the 'app' object inside 'app/main.py'
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]