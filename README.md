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
    ./venv/bin/celery -A ifuptime beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
    ```

9.  **Run Django Development Server:**
    ```bash
    ./venv/bin/python manage.py runserver
    ```

10. **Access the application:** Open your browser and go to `http://127.0.0.1:8000/`.

## Distributed Deployment with Docker Compose

This section outlines how to deploy the application in a distributed manner using Docker Compose, with a central master node and multiple worker-only monitoring nodes.

### Prerequisites

*   Docker installed on your server.
*   Docker Compose installed on your server.

### Deployment Architecture

*   **Master Node:** Runs the Django web application (Gunicorn), Nginx, central MySQL database, Redis server, and its own Celery Worker and **Celery Beat** instances. This node provides the main web interface and manages all monitoring tasks.
*   **Worker-Only Nodes:** These nodes only run Celery Worker instances. They do not provide a web interface or run their own database/Redis. Instead, they connect to the master node's MySQL and Redis services to execute monitoring tasks.

### Master Node Deployment

1.  **Navigate to the project root directory on your Master Node:**
    ```bash
    cd /path/to/your/ifuptime.com
    ```

2.  **Create a `.env` file:**
    Create a file named `.env` in the project root directory with the following content. **Replace `your_mysql_root_password` and `your_django_secret_key_here`** with strong, unique values.
    ```env
    MYSQL_ROOT_PASSWORD=your_mysql_root_password
    MYSQL_DATABASE=ifuptime
    MYSQL_USER=root
    MYSQL_PASSWORD=
    DJANGO_SECRET_KEY=your_django_secret_key_here

    # Monitoring Node Configuration for the Master Node's Celery instances
    MONITORING_NODE_NAME=master-node-01 # e.g., Shanghai-Master-Node
    MONITORING_NODE_LOCATION=Shanghai # e.g., Shanghai
    ```

3.  **Build Docker Images:**
    This command will build the Docker images for your services based on the `Dockerfile`.
    ```bash
    docker-compose -f docker-compose.full.yml build
    ```

4.  **Start Master Services:**
    This command will start all the services (web, nginx, db, redis, celery_worker, celery_beat) in detached mode.
    ```bash
    docker-compose -f docker-compose.full.yml up -d
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

### Worker-Only Node Deployment

For each additional monitoring node you want to deploy:

1.  **Navigate to the project root directory on your Worker-Only Node:**
    ```bash
    cd /path/to/your/ifuptime.com
    ```

2.  **Create a `.env` file:**
    Create a file named `.env` in the project root directory with the following content. **Replace the placeholder values** with your actual MySQL root password, a strong Django secret key, and the node-specific information.
    ```env
    MYSQL_ROOT_PASSWORD=your_mysql_root_password # Must match master node's MySQL root password
    MYSQL_DATABASE=ifuptime
    MYSQL_USER=root
    MYSQL_PASSWORD=
    DJANGO_SECRET_KEY=your_django_secret_key_here # Can be the same as master, or a different one

    # Master Node Database and Redis Connection (IMPORTANT: Replace with the actual IP address/hostname of your master node)
    MYSQL_HOST=your_master_node_ip_or_hostname
    MYSQL_PORT=3306
    CELERY_BROKER_URL=redis://your_master_node_ip_or_hostname:6379/0
    CELERY_RESULT_BACKEND=redis://your_master_node_ip_or_hostname:6379/0

    # Monitoring Node Configuration (IMPORTANT: Set unique values for each deployment node)
    MONITORING_NODE_NAME=your_node_name_here # e.g., Beijing-Node-02, Tokyo-Node-03
    MONITORING_NODE_LOCATION=your_node_location_here # e.g., Beijing, Tokyo
    ```
    *   **`MYSQL_HOST`**: The IP address or hostname of your master node where MySQL is running.
    *   **`CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND`**: The URL for Redis on your master node.
    *   **`MONITORING_NODE_NAME`**: A unique name for this specific monitoring node. This will be used to identify the node in the admin panel and in monitor logs.
    *   **`MONITORING_NODE_LOCATION`**: The geographical location of this node.

3.  **Build Docker Images:**
    This command will build the Docker images for your `celery_worker` service based on the `Dockerfile`.
    ```bash
    docker-compose -f docker-compose.worker-only.yml build
    ```

4.  **Start Worker-Only Services:**
    This command will start the `celery_worker` service in detached mode.
    ```bash
    docker-compose -f docker-compose.worker-only.yml up -d
    ```

### Managing Services

*   **Stop full services (Master Node):**
    ```bash
    docker-compose -f docker-compose.full.yml down -v
    ```
*   **Stop worker-only services (Worker-Only Node):**
    ```bash
    docker-compose -f docker-compose.worker-only.yml down -v
    ```
*   **View logs for full services:**
    ```bash
    docker-compose -f docker-compose.full.yml logs -f
    ```
*   **View logs for worker-only services:**
    ```bash
    docker-compose -f docker-compose.worker-only.yml logs -f
    ```

### Accessing the Application

By default, Nginx on the master node is configured to listen on port 80 and serve the application for `ifuptime.com` and `www.ifuptime.com`.

*   **DNS Configuration:** You need to configure your domain's DNS records (or your local `hosts` file for testing) to point `ifuptime.com` and `www.ifuptime.com` to the IP address of your master node.
*   **Firewall:** Ensure that port 80 (HTTP), 3306 (MySQL), and 6379 (Redis) are open on your master node for external access from worker-only nodes.

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
