# Cloud-Arch Infrastructure

[![Docker](https://img.shields.io/badge/Docker-Engine%20%7C%20Compose-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![JupyterLab](https://img.shields.io/badge/JupyterLab-RTC%20Workspace-F37626?logo=jupyter&logoColor=white)](https://jupyter.org/)
[![MLflow](https://img.shields.io/badge/MLflow-Tracking%20%26%20Registry-0194E2?logo=mlflow&logoColor=white)](https://mlflow.org/)
[![GitLab CE](https://img.shields.io/badge/GitLab-GitOps%20%26%20CI%2FCD-FC6D26?logo=gitlab&logoColor=white)](https://about.gitlab.com/)
[![Cloudflare R2](https://img.shields.io/badge/Cloudflare%20R2-S3--Compatible%20Lake-F38020?logo=cloudflare&logoColor=white)](https://www.cloudflare.com/products/r2/)
[![Ubuntu](https://img.shields.io/badge/OS-Ubuntu%2022.04%20%7C%2024.04%20LTS-E95420?logo=ubuntu&logoColor=white)](https://ubuntu.com/)

This repository is the **Infrastructure as Code (IaC)** and automated orchestration blueprint for the **Cloud-Arch** AI/ML platform. It provisions and manages an integrated, resource-optimized MLOps ecosystem consisting of **GitLab CE**, **JupyterLab RTC**, and **MLflow Tracking Server** backed by **Cloudflare R2** and **Nginx**.

---

## 🏗️ Architecture & Service Topology

```mermaid
flowchart LR
    subgraph Ingress["Ingress & Edge Security"]
        CF["Cloudflare Edge\n(SSL Termination & WSS)"]
        NGINX["Nginx Gateway\n(Zero-Buffer Reverse Proxy)"]
    end

    subgraph CoreServices["Core MLOps Stack"]
        GL["GitLab CE\n(Version Control & GitOps)"]
        JUP["JupyterLab RTC\n(Dynamic Kernel Discovery)"]
        MLF["MLflow Server\n(Experiment & Model Registry)"]
    end

    subgraph StorageLayer["Persistence & Artifact Lake"]
        NVMe["Local NVMe Storage\n(/srv & /home/ubuntu)"]
        R2["Cloudflare R2\n($0 Egress S3 Artifact Lake)"]
    end

    CF --> NGINX
    NGINX -->|Port 8080 / SSH 2222| GL
    NGINX -->|Port 8888 + WSS| JUP
    NGINX -->|Port 5000| MLF
    GL --> NVMe
    JUP --> NVMe
    MLF --> NVMe
    MLF -->|Model Weights| R2
```

| Service | Subdomain | Host Port | Description |
| :--- | :--- | :--- | :--- |
| **GitLab CE** | `gitlab.<domain>` | `8080` (HTTP) / `2222` (SSH) | GitOps repository, CI/CD engine, code versioning |
| **JupyterLab RTC** | `lab.<domain>` | `8888` (HTTP/WSS) | Collaborative notebooks with dynamic `uv` kernel auto-discovery |
| **MLflow Server** | `mlflow.<domain>` | `5000` (HTTP) | Experiment tracking & model registry backed by Cloudflare R2 |
| **Nginx Proxy** | `*.<domain>` | `80` / `443` | Reverse proxy, WSS streaming router, and SSL gateway |

---

## 📋 Prerequisites

### 1. System Requirements & Tools
- **Operating System:** Ubuntu 22.04 LTS or Ubuntu 24.04 LTS (x86_64 / ARM64)
- **Compute & RAM:** Minimum 2 vCPU, 2.0 GB RAM
- **Storage:** 35+ GB NVMe SSD
- **Docker Engine:** v24.0+ & **Docker Compose:** v2.20+ *(auto-installed by `deploy.sh` if missing)*
- **Nginx:** Web server & reverse proxy

### 2. Access Credentials & External Services
Before provisioning, prepare the required credentials:
- **Cloudflare DNS:** Managed DNS zone for your target domain
- **Cloudflare R2:** S3 API credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and bucket name)
- **Resend SMTP:** API key for transactional email notifications
- *(Optional)* **Telegram Bot:** Bot Token & Admin Chat ID for remote telemetry notifications

---

## 🚀 Deployment & Provisioning

### 1. Clone the Repository
```bash
git clone https://github.com/rizkyyanuark/cloud-arch.git
cd cloud-arch
```

### 2. Environment Configuration
Copy the configuration template and set your environment variables:
```bash
cp .env.example .env
nano .env
```

Key environment parameters:
| Variable | Description | Example / Default |
| :--- | :--- | :--- |
| `BASE_DOMAIN` | Target root domain | `example.com` |
| `GITLAB_ROOT_PASSWORD` | Initial GitLab administrator password | `SecurePassword123!` |
| `AWS_ACCESS_KEY_ID` | Cloudflare R2 access key ID | `your_r2_access_key` |
| `AWS_SECRET_ACCESS_KEY` | Cloudflare R2 secret access key | `your_r2_secret_key` |
| `R2_BUCKET_NAME` | Cloudflare R2 bucket name | `mini-project-lake` |
| `SMTP_PASSWORD` | Resend API key for outbound emails | `re_123456789` |

### 3. Run Automated Provisioning
Execute the master deployment script with superuser privileges:
```bash
chmod +x deploy.sh
sudo ./deploy.sh
```

The script automatically executes:
- Kernel memory tuning and swap space initialization for workload stability.
- Docker Engine and Compose plugin dependency checks and installation.
- Persistent volume directories and permission mapping (`/srv/gitlab`, `/srv/mlflow`, `/home/ubuntu/workspace`).
- Nginx reverse proxy configuration generation and reload.
- Docker container builds and multi-service stack orchestration.

---

## 🌐 DNS & Edge Routing

Create `A` records in your Cloudflare DNS dashboard pointing to your server's public IP:

| Type | Name | Target | Proxy Status |
| :--- | :--- | :--- | :--- |
| `A` | `gitlab` | `<SERVER_PUBLIC_IP>` | Proxied (Orange Cloud) |
| `A` | `lab` | `<SERVER_PUBLIC_IP>` | Proxied (Orange Cloud) |
| `A` | `mlflow` | `<SERVER_PUBLIC_IP>` | Proxied (Orange Cloud) |

> **Note:** Ensure Cloudflare SSL/TLS encryption mode is set to **Full** (or **Strict**) and **WebSockets** are enabled under the *Network* tab.

---

## 🛠️ Operations & Maintenance (Day-2 Ops)

### Health Check Probe
Verify service availability across all subdomains:
```bash
./scripts/check_health.sh
```

### Service Stack Lifecycle
```bash
# Check container status
docker compose ps

# Inspect real-time service logs
docker compose logs -f jupyter
docker compose logs -f mlflow
docker compose logs -f gitlab

# Restart entire stack
docker compose restart
```

---

## 📁 Repository Structure

```text
cloud-arch/
├── .env.example             # Environment configuration template
├── docker-compose.yml       # Multi-container service definitions
├── deploy.sh                # Master automated provisioning script
├── ARCHITECTURE.md          # In-depth architectural design & technical rationales
├── README.md                # Infrastructure blueprint guide
├── jupyter/                 # JupyterLab RTC Dockerfile & dynamic kernel discovery
├── mlflow/                  # MLflow Tracking Dockerfile & R2 entrypoint
├── nginx/                   # Nginx reverse proxy configurations
├── telegram/                # Telemetry bridge daemon & systemd unit
└── scripts/                 # Health check probes & repository seeders
```

---

For detailed technical benchmarks, memory optimization parameters, and disaster recovery procedures, refer to [ARCHITECTURE.md](ARCHITECTURE.md).
