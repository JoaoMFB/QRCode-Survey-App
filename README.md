
# QR Code Survey App - Cloud Computing Project

This project is a full-featured web application for creating real-time surveys, built on a scalable and resilient microservices architecture. The application allows users to create a question, and the system generates a unique voting page accessible via a QR Code, making it ideal for fast, interactive polling.

This project was developed for the "Cloud Computing" course to demonstrate key concepts such as containerization, orchestration, load balancing, data persistence, and network security.

---

##  System Architecture

The application follows a 3-tier architecture, fully containerized with Docker and orchestrated using Docker Compose or Kubernetes.

- **Tier 1: Load Balancer**
  - **Service:** HAProxy  
  - **Responsibility:** Receives all incoming user traffic on port 80 and distributes it between the available web server nodes. This is the single entry point to the application.

- **Tier 2: Application Servers**
  - **Services:** `web1` and `web2` (two identical instances of the FastAPI application)  
  - **Responsibility:** Handle the business logic, such as creating surveys, processing votes, and rendering HTML pages. They communicate with the database to store and retrieve data.

- **Tier 3: Database**
  - **Service:** Redis  
  - **Responsibility:** Stores all application data, including survey questions and vote counts. It is configured for data persistence to prevent data loss on restart.

---

## Technologies Used

- **Orchestration:** Docker, Docker Compose, Kubernetes (Minikube)
- **Web Application:** Python 3, FastAPI
- **Database:** Redis (for data storage and counters)
- **Load Balancer:** HAProxy
- **Base Operating System:** Amazon Linux 2
- **QR Code Generation:** `qrcode` (Python library)
- **HTML Templating:** Jinja2

---

## Prerequisites

- [Docker](https://www.docker.com/get-started) installed and running.
- [Docker Compose](https://docs.docker.com/compose/install/) (typically included with Docker Desktop).
- [kubectl](https://kubernetes.io/docs/tasks/tools/) installed.
- [Minikube](https://minikube.sigs.k8s.io/docs/start/) installed.

---

## How to Run the Project

### ▶With Docker Compose

#### 1. Clone the repository

```bash
git clone https://github.com/JoaoMFB/QRCode-Survey-App.git
cd <QRCode-Survey-App>
```

#### 2. Build and start the containers

```bash
docker compose up --build -d
```

- `--build`: Forces the images to be rebuilt from the Dockerfiles.  
- `-d`: Runs the containers in detached mode (in the background).

#### 3. Access the application

- **On your computer:** Open a browser and navigate to `http://localhost`.
- **On other devices (e.g. mobile):** Get your computer's local IP address (e.g., `192.168.1.105`) and go to `http://<YOUR-LOCAL-IP>`.

#### 4. Stop the application

```bash
docker compose down
```

---

### With Kubernetes (Minikube)

#### 1. Start your Minikube cluster

```bash
minikube start --driver=docker
```

#### 2. Point your shell to Minikube's Docker daemon

```bash
eval $(minikube -p minikube docker-env)
```

#### 3. Build the container images

```bash
docker build -t qr-survey-app -f Dockerfile.app .
docker build -t qr-survey-redis -f Dockerfile.redis .
docker build -t qr-survey-haproxy -f Dockerfile.haproxy .
```

#### 4. Deploy the application to Kubernetes

```bash
kubectl apply -f k8s/
```

#### 5. Access the application

```bash
minikube service haproxy-service
```

#### 6. Stop and clean up

```bash
kubectl delete -f k8s/
minikube stop
```

---

##  Architectural Decisions Explained

###  Docker

- **Containerization:** Each service (app, database, load balancer) runs in its own container to ensure isolation and portability.
- **Scalability & Load Balancing:** Two FastAPI instances (`web1`, `web2`) are served by HAProxy using a `roundrobin` strategy for balanced request handling.
- **Network Security:** Two custom bridge networks:
  - `frontend-network`: Connects HAProxy to web servers.
  - `backend-network`: Isolated internal network between web servers and Redis.
  - **Redis is never exposed to the internet.**
- **Data Persistence:** A Docker volume (`redis_data`) is mounted to Redis, and **AOF** is enabled for durability.

###  Kubernetes

- **Redis:**
  - Deployed as a **StatefulSet** for persistent identity and durable storage via `PersistentVolumeClaim`.
  - Exposed internally via a **ClusterIP** Service.
- **FastAPI Application:**
  - Deployed as a **Deployment** with `replicas: 2` for horizontal scalability and rolling updates.
  - Also exposed via **ClusterIP**.
- **HAProxy:**
  - Deployed as a **Deployment**.
  - Configuration provided through a **ConfigMap**.
- **External Access:**
  - A **LoadBalancer Service** exposes HAProxy, acting as the single external entry point.
- **Resilience:**
  - Application includes retry logic with exponential backoff for Redis connection failures—following best practices for distributed systems.

