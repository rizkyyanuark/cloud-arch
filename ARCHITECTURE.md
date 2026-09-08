# Technical Architecture: Cloud-Arch Infrastructure Blueprint

> Blueprint arsitektur Infrastructure-as-Code (IaC) untuk server riset dan machine learning engineering.  
> Digunakan pada server produksi AWS EC2 ARM64 (`t4g.small`, 2 vCPU, 2.0 GB RAM, 35 GB NVMe SSD) di region `us-east-1`.

---

## 1. Diagram Alur Sistem Terintegrasi

```mermaid
flowchart TD
    subgraph Edge["Edge Layer: DNS, SSL & Keamanan"]
        CF["Cloudflare Proxy & Universal HTTPS"]
        ZT["Cloudflare Zero Trust Access (OTP Email)"]
        D1["gitlab.tugasakhir.space (GitLab CE)"]
        D2["lab.tugasakhir.space (JupyterLab RTC)"]
        D3["mlflow.tugasakhir.space (MLflow Tracking)"]
        CF --- D1
        CF --- D2
        CF --- ZT --- D3
    end

    subgraph Host["Host Layer: AWS EC2 (34.196.37.78 / Ubuntu 24.04 ARM64)"]
        Nginx["Nginx Reverse Proxy & WSS Streamer<br/>(/etc/nginx/sites-available/cloud-arch.conf)"]
        
        subgraph DockerCompose["Docker Engine (cloud-arch stack)"]
            GitLab["GitLab CE (Port 8080 & SSH 2222)<br/>(gitlab/gitlab-ce:latest / gitlab-ce)"]
            Jupyter["JupyterLab RTC (Port 8888)<br/>(cloud-arch-jupyter:latest / jupyterlab)"]
            MLflow["MLflow Server (Port 5000)<br/>(cloud-arch-mlflow:latest / mlflow-server)"]
        end
        
        subgraph HostServices["Layanan Host Systemd"]
            TeleBridge["Telegram Gateway Bridge (Port 8085)<br/>(antigravity-telegram.service)"]
        end
        
        subgraph Storage["Persistent Storage di Disk SSD"]
            GitLabData["/srv/gitlab (Data, Config, Logs)"]
            MLflowData["/srv/mlflow/data (SQLite Metadata)"]
            CodeVol["/home/ubuntu/workspace (Multi-Project Repos)"]
            UserPref["/home/ubuntu/jupyter-user-data (Pengaturan & State)"]
            SwapVol["/swapfile (6.0 GB Active Swap, Swappiness 10)"]
        end
    end

    subgraph External["Layanan Cloud Eksternal"]
        R2["Cloudflare R2 Data Lake (mini-project-lake, $0 Egress)"]
        Resend["Resend SMTP Gateway (smtp.resend.com:465)"]
    end

    Edge --> Nginx
    Nginx -->|Proxy Pass Port 8080| GitLab
    Nginx -->|Proxy Pass Port 8888 + Upgrade WSS| Jupyter
    Nginx -->|Proxy Pass Port 8085 (OAuth Callback)| TeleBridge
    Nginx -->|Proxy Pass Port 5000| MLflow
    GitLab <--> GitLabData
    GitLab -->|Notifikasi Akun & Verifikasi| Resend
    Jupyter <--> CodeVol
    Jupyter <--> UserPref
    MLflow <--> MLflowData
    MLflow <-->|Simpan Bobot Model .pt & .onnx| R2
```

---

## 2. Parameter Teknis dan Alasan Desain

Setiap keputusan teknis pada arsitektur ini memiliki alasan yang terukur:

### A. Alokasi 6.0 GB SWAP di SSD NVMe
* **Keputusan:** Mengaktifkan file swap 6.0 GB dengan parameter kernel `vm.swappiness=10`.
* **Alasan teknis:** Mesin `t4g.small` memiliki RAM fisik 2.0 GB (sekitar 1.8 GB usable). GitLab CE dan JupyterLab memiliki kebutuhan dasar sekitar 1.15 GB RAM. Alokasi swap mencegah Linux OOM-killer mematikan proses saat Rails melakukan *cold boot* atau saat kompilasi aset. Pengaturan `swappiness=10` memastikan sistem tetap memprioritaskan RAM fisik dan hanya menggunakan swap saat benar-benar dibutuhkan.

### B. Mode Tunggal Puma pada GitLab (`worker_processes = 0`)
* **Keputusan:** Menyetel `puma['worker_processes'] = 0`, `puma['max_threads'] = 2`, dan `postgresql['shared_buffers'] = "64MB"`.
* **Alasan teknis:** Mode cluster Puma standar menjalankan 1 proses master dan minimal 2 worker, yang masing-masing menghabiskan ~450 MB RAM. Mode proses tunggal memotong konsumsi memori GitLab hingga ~400 MB tanpa mengorbankan fungsionalitas Git push/pull dan antarmuka web untuk tim kecil.

### C. Nginx Unbuffered Streaming (`proxy_buffering off;`)
* **Keputusan:** Menambahkan `proxy_buffering off;` dan `proxy_cache off;` pada blok router JupyterLab.
* **Alasan teknis:** Nginx secara default menahan paket respons HTTP sampai ukuran buffer terpenuhi. Untuk sesi terminal interaktif berbasis WebSocket (`/terminals/websocket/`), penahanan paket ini menyebabkan keterlambatan respon ketikan keyboard. Menonaktifkan buffer memastikan setiap karakter terkirim seketika tanpa jeda.

### D. Cloudflare R2 untuk Penyimpanan Model MLflow
* **Keputusan:** Mengarahkan backend artifact MLflow ke Cloudflare R2 (`mini-project-lake`).
* **Alasan teknis:** R2 kompatibel dengan S3 API dan tidak mengenakan biaya transfer data keluar (*zero egress fee*). Hal ini menjaga biaya cloud tetap terprediksi saat mengunduh bobot model berukuran besar untuk inferensi.

### E. Integrasi Resend SMTP melalui Port 465 SSL/TLS
* **Keputusan:** Menggunakan `smtp.resend.com` pada port 465 dengan opsi `smtp_tls = true` dan `smtp_enable_starttls_auto = false`.
* **Alasan teknis:** Port 25 sering diblokir oleh penyedia cloud untuk mencegah spam, sedangkan port 587 dengan STARTTLS sering mengalami *handshake timeout* pada koneksi transit tertentu. Koneksi implisit TLS pada port 465 memberikan pengiriman email verifikasi dan reset password yang konsisten.

---

## 3. Matriks Port dan Layanan

| Port Host | Protokol | Layanan | Tujuan |
| :--- | :--- | :--- | :--- |
| `80` | HTTP | Nginx Reverse Proxy | Menerima lalu lintas dari Cloudflare |
| `8080` | HTTP | GitLab CE Web | Antarmuka web dan API GitLab |
| `2222` | TCP | GitLab SSH | Git clone dan push via SSH |
| `8888` | HTTP/WSS | JupyterLab RTC | Antarmuka notebook dan terminal WebSocket |
| `8085` | HTTP | Antigravity Gateway | Endpoint penerima OAuth 2.0 Web Callback |
| `5000` | HTTP | MLflow Tracking | UI dan endpoint logging eksperimen ML |

---

## 4. Prosedur Pemulihan Bencana (Disaster Recovery)

Jika server fisik mengalami kendala atau perlu dipindahkan ke penyedia cloud lain:

1. Buat VM baru (Ubuntu 22.04 atau 24.04, ARM64 atau x86_64).
2. Pasang repositori ini dan siapkan berkas konfigurasi:
   ```bash
   git clone https://github.com/rizkyyanuark/cloud-arch.git
   cd cloud-arch
   cp .env.example .env
   ```
3. Sesuaikan `BASE_DOMAIN` dan kredensial pada berkas `.env`.
4. Jalankan script instalasi otomatis:
   ```bash
   chmod +x deploy.sh
   sudo ./deploy.sh
   ```
5. Perbarui DNS A Record di Cloudflare ke IP publik VM yang baru. Seluruh layanan akan aktif kembali dengan konfigurasi yang identik.
