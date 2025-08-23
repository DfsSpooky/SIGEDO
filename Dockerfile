# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . /app/

# Set the working directory to the Django project root
WORKDIR /app/gestion_docentes

# Collect static files with a dummy secret key to allow the build to succeed
# These dummy values are only used during build time and will be overridden by .env at runtime.
RUN SECRET_KEY='dummy-key-for-build' ID_ENCRYPTION_KEY='WPTnEteKbDAIR4cGw5PYHXeu_xgnafkmwmdn3HvXwnI=' python manage.py collectstatic --noinput

# Expose port 8000
EXPOSE 8000

# Run gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "gestion_docentes.gestion_docentes.wsgi"]
