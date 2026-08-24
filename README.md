# 🏛️ Cloud-Arch: Production-Grade MLOps & DevOps Infrastructure

> **Master Infrastructure-as-Code (IaC) Blueprint**  
> **Author & Architect:** Rizky Yanuar Kristianto (`rizkyyanuarkristianto@gmail.com`)  
> **Production Domain:** `tugasakhir.space`  
> **Compatibility:** Multi-Cloud (AWS, GCP, Oracle Cloud, Bare Metal) on ARM64 & x86_64

---

## 🌟 Fitur Utama Ekosistem:

1. **🦊 GitLab Community Edition (CE):**
   - Version Control terpusat dengan GitOps & CI/CD Pipelines.
   - Otomasi password reset untuk user baru (*Zero-Friction Onboarding*).
   - Single Sign-On (SSO) OAuth 2.0 terintegrasi.
2. **📓 JupyterLab RTC (Real-Time Collaboration):**
   - Live pair programming dengan kursor sinkron avatar GitLab.
   - **Dynamic Kernel Auto-Discovery:** Mengetik `uv sync` di folder mana pun seketika memunculkan kernel `Python (<nama_proyek>)` secara otomatis tanpa restart container.
3. **📊 MLflow Tracking Server:**
   - Pencatatan metrik, parameter, dan visualisasi perbandingan model ML.
   - Terhubung langsung ke **Cloudflare R2 Data Lake ($0 Egress)**.
4. **🌐 High-Performance Nginx Proxy:**
   - Manajemen multi-subdomain dengan SSL Universal Cloudflare dan WebSocket WSS stabil.

---

## 🚀 Panduan Instalasi Cepat (*One-Command Deploy*):

Pada server Linux/Ubuntu baru mana pun:

```bash
# 1. Clone repositori ini
git clone https://github.com/rizkyyanuark/cloud-arch.git
cd cloud-arch

# 2. Salin dan sesuaikan environment
cp .env.example .env

# 3. Jalankan script instalasi otomatis
chmod +x deploy.sh
sudo ./deploy.sh
```

Dalam waktu **~3 menit**, seluruh sistem akan aktif 24/7 di domain Anda!
