FROM python:3.11-slim

# HF Spaces requires a non-root user with UID 1000
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Install dependencies first (better layer caching)
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=appuser:appuser . .

# Switch to non-root user
USER appuser

# Ensure Python can always find local modules in /app regardless of
# how uvicorn sets sys.path at startup (fixes ModuleNotFoundError).
ENV PYTHONPATH=/app
ENV PORT=7860

EXPOSE 7860

# Shell form so $PORT expands correctly at runtime
CMD python -m uvicorn app:app --host 0.0.0.0 --port ${PORT}
