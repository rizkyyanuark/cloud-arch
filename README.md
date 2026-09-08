# Cloud-Arch: Reproducible Infrastructure-as-Code (IaC)

Blueprint Infrastructure-as-Code (IaC) untuk membangun dan mereplikasi server riset machine learning, version control, dan pelacakan eksperimen pada satu mesin Linux (AWS EC2, GCP Compute Engine, atau Bare Metal).

Infrastruktur ini dirancang khusus untuk berjalan stabil pada mesin dengan memori terbatas (minimal 2.0 GB RAM fisik dengan 6.0 GB NVMe SWAP) hingga server berkapasitas besar.

---

## 1. Komponen Inti Ekosistem

1. **GitLab Community Edition (CE):**
   * Version Control terpusat dengan GitOps dan CI/CD pipeline.
   * Profil memori teroptimasi (Puma mode proses tunggal, buffer PostgreSQL 64MB, batas worker Gitaly).
   * Notifikasi email transaksional melalui gateway Resend SMTP pada port 465 SSL/TLS.
   * Port akses: Web UI pada port 8080 dan Git SSH pada port 2222.

2. **JupyterLab Real-Time Collaboration (RTC):**
   * Kolaborasi dokumen real-time berbasis CRDT Yjs.
   * Dynamic Kernel Auto-Discovery: Memindai folder proyek dan otomatis mengenali virtual environment Python (`.venv`) tanpa perlu me-restart kontainer.
   * Integrasi Antigravity CLI (`agy`) dan konfigurasi MCP yang terpasang langsung dari host.
   * Penonaktifan auto-aktivasi Conda pada shell untuk memastikan terminal web terbuka dalam 0.2 detik.
   * Port akses: Port 8888.

3. **MLflow Tracking Server:**
   * Pencatatan metrik pelatihan model, parameter eksperimen, dan visualisasi artefak.
   * Penyimpanan artefak terhubung langsung ke Cloudflare R2 Data Lake dengan biaya transfer data keluar gratis ($0 egress fee).
   * Database metadata berbasis SQLite pada volume persisten lokal.
   * Port akses: Port 5000.

4. **Nginx Reverse Proxy & WSS Streamer:**
   * Manajemen multi-subdomain dengan pemetaan otomatis berdasarkan variabel domain.
   * Dukungan WebSocket WSS untuk JupyterLab RTC dan terminal.
   * Penonaktifan buffer proxy (`proxy_buffering off;`) untuk menjamin respon ketikan keyboard pada terminal browser tanpa jeda.
   * Rute callback untuk Google Web OAuth 2.0 receiver pada path `/oauth2callback` (port 8085).

5. **Telegram Antigravity Gateway Bridge:**
   * Layanan systemd untuk pemantauan kesehatan server dan alur kerja agen AI jarak jauh melalui bot Telegram.
   * Terintegrasi dengan server callback web OAuth lokal.

---

## 2. Prasyarat Sistem Minimum

* **Sistem Operasi:** Ubuntu 22.04 LTS atau Ubuntu 24.04 LTS (Arsitektur ARM64 Graviton atau x86_64).
* **CPU:** Minimal 2 vCPU.
* **RAM:** Minimal 2.0 GB Physical RAM.
* **Storage:** Minimal 35 GB SSD NVMe (direkomendasikan untuk menampung data GitLab dan 6.0 GB SWAP).
* **Akses Jaringan:** Port 80, 443 (via reverse proxy/Cloudflare), dan port 2222 (opsional, untuk SSH Git).

---

## 3. Panduan Instalasi Cepat (One-Command Provisioning)

Pada mesin server Ubuntu yang baru dibuat, jalankan langkah berikut:

### Langkah 1: Kloning Repositori
```bash
git clone https://github.com/rizkyyanuark/cloud-arch.git
cd cloud-arch
```

### Langkah 2: Salin dan Sesuaikan Variabel Lingkungan
```bash
cp .env.example .env
nano .env
```
Isi konfigurasi penting pada berkas `.env`:
* `BASE_DOMAIN`: Domain utama Anda (contoh: `tugasakhir.space`).
* `GITLAB_ROOT_PASSWORD`: Password awal untuk akun root GitLab.
* `SMTP_PASSWORD`: API key dari Resend untuk pengiriman email notifikasi.
* `AWS_ACCESS_KEY_ID` & `AWS_SECRET_ACCESS_KEY`: Kredensial Cloudflare R2.
* `TELEGRAM_BOT_TOKEN`: Token bot Telegram (jika mengaktifkan layanan gateway bridge).

### Langkah 3: Eksekusi Skrip Otomasi Deployment
```bash
chmod +x deploy.sh
sudo ./deploy.sh
```

Skrip `deploy.sh` akan melakukan seluruh tahapan berikut secara otomatis:
1. Mengalokasikan 6.0 GB SWAP memory pada SSD dengan nilai `swappiness=10`.
2. Menginstall Docker Engine dan Docker Compose plugin resmi jika belum terpasang.
3. Menyiapkan seluruh direktori persisten di `/srv/` dan `/home/ubuntu/`.
4. Mengonfigurasi Nginx reverse proxy dengan domain target dan me-reload layanan.
5. Memasang dan mengaktifkan service systemd `antigravity-telegram.service`.
6. Membangun image lokal dan menyalakan seluruh kontainer Docker.

---

## 4. Konfigurasi DNS di Cloudflare

Arahkan record DNS pada panel Cloudflare Anda ke IP publik server:

| Tipe | Nama Record | Target | Status Proxy |
| :--- | :--- | :--- | :--- |
| `A` | `gitlab` | `IP_SERVER_ANDA` | Proxied (Orange Cloud) |
| `A` | `lab` | `IP_SERVER_ANDA` | Proxied (Orange Cloud) |
| `A` | `mlflow` | `IP_SERVER_ANDA` | Proxied (Orange Cloud) |

*Pastikan SSL/TLS mode di Cloudflare diatur ke **Full** atau **Flexible**, dan fitur WebSockets diaktifkan pada menu Network.*

---

## 5. Struktur Berkas Repositori

```text
cloud-arch/
├── .env.example             # Template konfigurasi variabel lingkungan lengkap
├── docker-compose.yml       # Definisi kontainer GitLab CE, JupyterLab, dan MLflow
├── deploy.sh                # Skrip orkestrasi provisioning otomatis dari nol
├── ARCHITECTURE.md          # Dokumentasi teknis mendalam dan diagram alur sistem
├── README.md                # Panduan operasional dan pengenalan ekosistem
├── gitlab/                  # Skrip pembantu dan template email GitLab
├── jupyter/
│   ├── Dockerfile           # Base image Jupyter minimal dengan uv dan tools IDE
│   ├── dynamic_kernels.py   # Modul auto-discovery kernel virtual environment
│   ├── gitlab_auth.py       # Modul autentikasi SSO terintegrasi GitLab
│   └── jupyter_server_config.py # Konfigurasi server JupyterLab
├── mlflow/
│   ├── Dockerfile           # Image pelacak MLflow ringan
│   └── run_mlflow.sh        # Skrip inisialisasi koneksi SQLite dan Cloudflare R2
├── nginx/
│   └── conf.d/
│       └── cloud-arch.conf  # Template konfigurasi reverse proxy Nginx dan WSS
├── telegram/
│   ├── antigravity-telegram.service # File unit systemd untuk daemon bot
│   └── telegram_antigravity_bridge.py # Backend gateway Telegram & OAuth receiver
└── scripts/
    ├── check_health.sh      # Skrip audit status proses dan port server
    └── seed_gitlab.py       # Inisialisasi awal repositori dan akun
```

---

## 6. Operasi dan Pemeliharaan Harian

### Memeriksa Status Kontainer:
```bash
docker compose ps
```

### Melihat Log Layanan Tertentu:
```bash
docker compose logs -f gitlab
docker compose logs -f jupyter
docker compose logs -f mlflow
```

### Me-restart Seluruh Layanan:
```bash
docker compose restart
```

### Memeriksa Penggunaan RAM dan SWAP:
```bash
free -h
```
