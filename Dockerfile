# Use an official Python runtime as a parent image
FROM python:3.9-slim-buster

# Set the working directory in the container
WORKDIR /app

# Install system dependencies required for mysqlclient (even if using pymysql, some libs might be needed for other packages)
# And for building Python packages
RUN apt-get update && apt-get install -y     build-essential     libmysqlclient-dev     default-libmysqlclient-dev     pkg-config     && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
COPY . /app/

# Collect static files
RUN python manage.py collectstatic --noinput

# Expose port 8000 for Gunicorn
EXPOSE 8000

# Run Gunicorn when the container launches
CMD ["gunicorn", "ifuptime.wsgi:application", "--bind", "0.0.0.0:8000"]

