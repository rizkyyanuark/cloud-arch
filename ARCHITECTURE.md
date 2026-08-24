# 🏛️ CLOUD-ARCH TECHNICAL ARCHITECTURE BLUEPRINT

```mermaid
flowchart TD
    subgraph Edge["🌍 Edge Layer (DNS & Security)"]
        CF["Cloudflare Proxy & SSL (Universal HTTPS)"]
        D1["lab.tugasakhir.space (JupyterLab)"]
        D2["gitlab.tugasakhir.space (GitLab CE)"]
        D3["mlflow.tugasakhir.space (MLflow Tracking)"]
        CF --- D1
        CF --- D2
        CF --- D3
    end

    subgraph Host["💻 Linux VM Server (AWS / GCP / Oracle)"]
        Nginx["Nginx Reverse Proxy & WebSocket WSS Handler"]
        
        subgraph DockerCompose["Docker Engine (cloud-arch stack)"]
            Jupyter["📓 JupyterLab RTC (Port 8888)"]
            GitLab["🦊 GitLab CE (Port 8080)"]
            MLflow["📊 MLflow Server (Port 5000)"]
        end
        
        subgraph Disks["💾 Persistent Storage"]
            CodeVol["📁 /home/ubuntu/workspace (Repositories)"]
            UserPref["📁 /home/ubuntu/jupyter-user-data (Settings)"]
            GitLabData["📁 /srv/gitlab/data (Git Storage)"]
            MLflowData["📁 /srv/mlflow/data (SQLite/Metadata)"]
        end
    end

    subgraph External["☁️ External Cloud Storage"]
        R2["🪣 Cloudflare R2 Data Lake ($0 Egress)"]
    end

    Edge --> Nginx
    Nginx --> Jupyter
    Nginx --> GitLab
    Nginx --> MLflow
    Jupyter <--> CodeVol
    Jupyter <--> UserPref
    GitLab <--> GitLabData
    MLflow <--> MLflowData
    MLflow <-->|Upload Weights .onnx / .pth| R2
```

---

## 🛡️ Disaster Recovery Runbook (Pindah Server dalam 5 Menit):

1. Sewa VM baru di cloud mana pun (AWS / GCP / Oracle).
2. Arahkan IP publik baru ke Cloudflare DNS `tugasakhir.space`.
3. Jalankan `git clone ... && sudo ./deploy.sh`.
4. Seluruh layanan langsung online kembali dengan data yang aman di Cloudflare R2!
