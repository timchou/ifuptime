# ifuptime.com - Website Monitoring Project

This project provides a web application to monitor the health of websites and APIs, including uptime checks, keyword checks, and API response validation.

## Project Setup (Local Development)

1.  **Clone the repository:**
    ```bash
    git clone <your-repository-url>
    cd ifuptime.com
    ```

2.  **Create a Python Virtual Environment and Install Dependencies:**
    ```bash
    python3 -m venv venv
    ./venv/bin/pip install -r requirements.txt
    ```

3.  **Configure Database (MySQL):**
    Ensure you have a MySQL server running. Create a database named `ifuptime`.

4.  **Run Database Migrations:**
    ```bash
    ./venv/bin/python manage.py migrate
    ```

5.  **Create a Superuser:**
    ```bash
    ./venv/bin/python manage.py createsuperuser
    ```

6.  **Start Redis Server:**
    Ensure your Redis server is running locally.

7.  **Run Celery Worker:**
    ```bash
    ./venv/bin/celery -A ifuptime worker -l info
    ```

8.  **Run Celery Beat:**
    ```bash
    ./venv/bin/celery -A ifuptime beat -l info
    ```

9.  **Run Django Development Server:**
    ```bash
    ./venv/bin/python manage.py runserver
    ```

10. **Access the application:** Open your browser and go to `http://127.0.0.1:8000/`.

## Deployment with Docker Compose

This section outlines how to deploy the application using Docker Compose, which includes Nginx, Gunicorn (Django), MySQL, Redis, Celery Worker, and Celery Beat.

### Prerequisites

*   Docker installed on your server.
*   Docker Compose installed on your server.

### Deployment Steps

1.  **Navigate to the project root directory:**
    ```bash
    cd /path/to/your/ifuptime.com
    ```

2.  **Create a `.env` file:**
    Create a file named `.env` in the project root directory with the following content. **Replace the placeholder values** with your actual MySQL root password, a strong Django secret key, and the node-specific information.
    ```env
    MYSQL_ROOT_PASSWORD=your_mysql_root_password
    MYSQL_DATABASE=ifuptime
    MYSQL_USER=root
    MYSQL_PASSWORD=
    DJANGO_SECRET_KEY=your_django_secret_key_here

    # Monitoring Node Configuration (IMPORTANT: Set unique values for each deployment node)
    MONITORING_NODE_NAME=your_node_name_here # e.g., Shanghai-Node-01, Beijing-Node-02
    MONITORING_NODE_LOCATION=your_node_location_here # e.g., Shanghai, Beijing
    ```
    *   **`MYSQL_ROOT_PASSWORD`**: The root password for your MySQL database. If your local MySQL root password is empty, you can leave this empty as well, but it's highly recommended to set a strong password in production.
    *   **`DJANGO_SECRET_KEY`**: A unique, unpredictable secret key for your Django project. You can copy this from your local `ifuptime/settings.py` file.
    *   **`MONITORING_NODE_NAME`**: A unique name for this specific monitoring node. This will be used to identify the node in the admin panel and in monitor logs.
    *   **`MONITORING_NODE_LOCATION`**: The geographical location of this node.

3.  **Build Docker Images:**
    This command will build the Docker images for your `web`, `celery_worker`, and `celery_beat` services based on the `Dockerfile`.
    ```bash
    docker-compose build
    ```

4.  **Start Services:**
    This command will start all the services defined in `docker-compose.yml` in detached mode (in the background).
    ```bash
    docker-compose up -d
    ```

5.  **Run Database Migrations (inside the Docker container):**
    After the `db` service is up, you need to apply Django migrations to the new MySQL database instance inside the container.
    ```bash
    docker-compose exec web python manage.py migrate
    ```

6.  **Create a Superuser (inside the Docker container):**
    You'll need a superuser account to access the Django admin panel and manage your application.
    ```bash
    docker-compose exec web python manage.py createsuperuser
    ```

### Managing Services

*   **Stop all services:**
    ```bash
    docker-compose down
    ```
*   **Stop and remove containers, networks, and volumes:**
    ```bash
    docker-compose down -v
    ```
*   **View logs for all services:**
    ```bash
    docker-compose logs -f
    ```
*   **View logs for a specific service (e.g., `web`):**
    ```bash
    docker-compose logs -f web
    ```

### Accessing the Application

By default, Nginx is configured to listen on port 80 and serve the application for `ifuptime.com` and `www.ifuptime.com`.

*   **DNS Configuration:** You need to configure your domain's DNS records (or your local `hosts` file for testing) to point `ifuptime.com` and `www.ifuptime.com` to the IP address of the server where Docker is running.
*   **Firewall:** Ensure that port 80 (HTTP) is open in your server's firewall.

Once DNS is propagated and services are running, you can access your application by navigating to `http://ifuptime.com` in your web browser.

## Monitoring Nodes

Each deployed instance of the application (running `celery_worker` and `celery_beat` services) acts as a monitoring node. These nodes will send periodic heartbeats to the central database, allowing you to monitor their status.

### Node Configuration

Before deploying a new node, ensure you set the `MONITORING_NODE_NAME` and `MONITORING_NODE_LOCATION` environment variables in its `.env` file. Each node must have a **unique** `MONITORING_NODE_NAME`.

### Viewing Node Status

As an administrator, you can view the status of all running monitoring nodes in the Django Admin panel:

1.  Log in to the Django Admin (`http://ifuptime.com/admin/`).
2.  Navigate to the `Monitoring` section.
3.  Click on `Nodes`.

Here you will see a list of all registered nodes, their last heartbeat time, and whether they are currently considered active.

### Node Information in Monitor Logs

When a monitoring check is performed by a specific node, the `node_name` is recorded in the `MonitorLog` entry. This allows you to track which node performed a particular check.