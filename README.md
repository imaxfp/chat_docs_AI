# 🚀 Chat with your DOCS using Airflow & MinIO: GenAI LLMs and RAG Pipeline

***Transform your static PDF collection into a searchable, interactive knowledge base using Airflow and Vector Embeddings.***


## TODO simple demo how it works


## 🚀 Getting Started

Follow these simple steps to get your intelligent PDF pipeline up and running.

### 1. Launch Infrastructure
Spin up all services (Postgres, MinIO, Airflow, Qdrant, and Microservices):
```bash
docker-compose up -d
```

### 2. Configure Airflow
Create your admin credentials to access the dashboard:
```bash
docker exec -it airflow-api-server airflow users create \
  --username admin --password admin \
  --firstname Admin --lastname Admin \
  --role Admin \
  --email admin@example.com
```

### 3. Upload Your Documents
1.  Open **[MinIO Console](http://localhost:9001)** (Login: `minioadmin` / `minioadmin`).
2.  Create a bucket named **`test1`**.
3.  Upload your PDF files into this bucket.

### 4. Process the PDFs
1.  Open the **[Airflow UI](http://localhost:8080/dags)** (Login: `admin` / `admin`).
2.  Locate the **`minio_pdf_processor_dag`**.
3.  **Unpause** it and click **Trigger** to start extracting data and generating embeddings.

### 5. Chat with Your Data
Once processing is complete, test your RAG pipeline via the **[Search API Swagger](http://localhost:8003/docs#/default/find_by_text_search_post)**.

**Example Query:**
```json
{
  "query": "UK-based businesses",
  "limit": 5
}
```

---

## 📖 Project Overview

This project implements a complete **Retrieval-Augmented Generation (RAG)** pipeline. It automates the ingestion of PDF documents, extracts semantic information, and enables natural language querying.

- **Orchestration**: Managed by **Apache Airflow 3.x**.
- **Storage**: Files in **MinIO**, Metadata in **Postgres**, Vectors in **Qdrant**.
- **AI**: Embeddings via **Sentence Transformers**.

### 🏗 Architecture At a Glance

The system is composed of the Airflow ecosystem and two specialized microservices:
- **Extraction Microservice**: `./services/typing-pdf-extractor-service` (FastAPI)
- **Chat Docs Microservice**: `./services/chat-docs-service` (FastAPI)
- **Vector DB**: `qdrant-vector-db` (Qdrant)
- **Metadata DB**: `pg-typing-pdf-extractor-db` (Postgres)
- **Airflow DB**: `pg-airflow-db` (Postgres)
- **Object Storage**: `minio` (MinIO)
- **Embedding/LLM Chat**: Ollama services (`ollama-llm-embedding`, `ollama-llm-chat`)

---

## Airflow Orchestration

Airflow is the heart of the project, coordinating data movement and processing.

### 📋 DAG Catalog

- **`minio_pdf_processor_dag`**: The primary pipeline. It monitors MinIO buckets for new PDF uploads and triggers the extraction microservice to process them in real-time.
- **`hello_world_dag`**: A simple diagnostic DAG to verify scheduler health.
- **`debug_test_dag`**: Used for testing internal API connections and core Airflow variables.

### 🛠 Working with DAGs

#### Adding New Logic
1.  Place your `.py` files in the `./dags` folder.
2.  The **DAG Processor** will automatically detect and serialize them within seconds.
3.  Check the status via CLI:
    ```bash
    docker exec -it airflow-api-server airflow dags list
    ```

#### Monitoring & Logs
Tracking task execution is critical. Use these commands to inspect the scheduler's behavior:
```bash
# Check if the scheduler sees your file
docker logs airflow-scheduler | grep your_dag_name.py

# Get logs for a specific task instance
docker exec -it airflow-scheduler airflow tasks logs <dag_id> <task_id> <run_id>
```

#### Manual Triggering & Testing
Sometimes you need to bypass the sensor and run a DAG immediately:
```bash
# Test a specific task without running the whole DAG
docker exec -it airflow-api-server airflow tasks test <dag_id> <task_id> 2024-01-01

# Trigger a full DAG run
docker exec -it airflow-scheduler airflow dags trigger <dag_id>
```

---

## 🐞 Developer Experience (DX)

### Debugging DAGs in VS Code
The environment is pre-configured for remote debugging using `debugpy`.

1.  Add this to your `.vscode/launch.json`:
    ```json
    {
        "version": "0.2.0",
        "configurations": [
            {
                "name": "Airflow: Attach to Docker",
                "type": "debugpy",
                "request": "attach",
                "connect": { "host": "localhost", "port": 5678 },
                "pathMappings": [
                    { "localRoot": "${workspaceFolder}/dags", "remoteRoot": "/opt/airflow/dags" }
                ]
            }
        ]
    }
    ```
2.  Run the task with the debug flag:
    ```bash
    docker exec -it -e AIRFLOW_DEBUG=true airflow-scheduler airflow tasks test <dag_id> <task_id> 2026-01-01
    ```

## Project structure and project organization
📌 Key references / standards behind it

12-Factor App

Each service is self-contained, with its own dependencies and config.

Dockerfile per service follows this principle.

https://12factor.net/

Docker & Container Best Practices

Each image builds from its service folder.

Avoids coupling multiple services in one Dockerfile.

https://docs.docker.com/develop/develop-images/dockerfile_best-practices/

Microservice Architecture Patterns (Sam Newman, Martin Fowler)

Each microservice should be independently deployable.

Clear separation from orchestrators (like Airflow).

https://martinfowler.com/articles/microservices.html

Monorepo / Multi-repo Guidelines

Organize by service folder for maintainability and CI/CD.

Root-level DAGs remain isolated.

project-root/
│
├── dags/                     # Airflow DAGs
│
├── services/                 # Standard microservices
│   ├── user-service/
│   ├── order-service/
│   └── billing-service/
│
├── llm-services/             # All Ollama LLM services
│   ├── llm-model-1/
│   │   ├── Dockerfile
│   │   ├── model/            # Optional mounted model files
│   │   └── README.md
│   │
│   ├── llm-model-2/
│   ├── llm-model-3/
│   ├── llm-model-4/
│   └── llm-model-5/
│
├── shared/                   # Optional shared libraries / utils
│
├── volumes/                  # Mounted volumes for DBs, data, models
│   ├── user-service-db/
│   ├── order-service-db/
│   ├── shared-data/
│   └── llm-models/           # Could have subfolders for each model
│       ├── llm-model-1/
│       ├── llm-model-2/
│       └── llm-model-3/
│
├── docker-compose.yml         # Local dev orchestration
├── README.md
└── pyproject.toml / requirements.txt




---

## 🏷 Tags
`Airflow 3.x` • `MinIO` • `Qdrant` • `PostgreSQL` • `RAG` • `Docker` • `Python` • `FastAPI`