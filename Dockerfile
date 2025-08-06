# Use the official Python image from the Docker Hub
FROM python:3.10.11-slim-buster 

# Set the working directory in the container
WORKDIR /app

# Set environment variables for the virtual environment
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Create a virtual environment
RUN python -m venv $VIRTUAL_ENV

# Copy the requirements file into the container
COPY requirements.txt .

# Install the Python dependencies into the virtual environment
RUN pip install --no-cache-dir -r requirements.txt 

# Copy the rest of the application code into the container
COPY . .

# Expose the port your Flask app runs on (default for Gunicorn is 8000)
EXPOSE 8000

# Command to run the application using Gunicorn from within the virtual environment
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]