#!/bin/bash
# ==============================================================================
# 🚀 CLOUD-ARCH MASTER DEPLOYMENT SCRIPT (ONE-CLICK PROVISIONING)
# ==============================================================================
set -e

echo "================================================================="
echo "       🏛️ INITIALIZING CLOUD-ARCH ENTERPRISE ECOSYSTEM 🏛️"
echo "================================================================="

# 1. Check Root / Sudo
if [ "$EUID" -ne 0 ]; then
  echo "⚠️ Harap jalankan script ini dengan sudo: sudo ./deploy.sh"
  exit 1
fi

# 2. Check and Setup 6GB NVMe SWAP (Prevents OOM on 2GB RAM instances)
SWAP_TOTAL=$(free -m | awk '/^Swap:/ {print $2}')
if [ "$SWAP_TOTAL" -lt 4000 ]; then
  echo "🧠 Mengalokasikan 6.0 GB SWAP Memory di NVMe SSD..."
  fallocate -l 6G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=6144
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  if ! grep -q "/swapfile" /etc/fstab; then
    echo "/swapfile none swap sw 0 0" >> /etc/fstab
  fi
  echo "✓ 6.0 GB SWAP Memory berhasil diaktifkan!"
fi

# 3. Load Environment Variables (.env)
if [ ! -f .env ]; then
  echo "⚠️ File .env tidak ditemukan. Menyalin dari .env.example..."
  cp .env.example .env
fi
source .env

DOMAIN=${BASE_DOMAIN:-example.com}
echo "🌐 Menggunakan Target Domain: $DOMAIN"

# 4. Check and Install Docker if missing
if ! command -v docker &> /dev/null; then
  echo "📦 Menginstall Docker Engine & Docker Compose..."
  apt-get update
  apt-get install -y ca-certificates curl gnupg lsb-release
  mkdir -p /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  systemctl enable docker
  systemctl start docker
  echo "✓ Docker berhasil diinstall!"
fi

# 5. Setup Persistent Directories & Permissions
echo "📁 Menyiapkan direktori persisten..."
mkdir -p /srv/gitlab/config /srv/gitlab/logs /srv/gitlab/data
mkdir -p /srv/mlflow/data
mkdir -p /home/ubuntu/workspace /home/ubuntu/jupyter-user-data/.jupyter /home/ubuntu/jupyter-user-data/.local
chown -R 1000:100 /home/ubuntu/workspace /home/ubuntu/jupyter-user-data

# 6. Configure Nginx Reverse Proxy with Dynamic Domain
echo "🌐 Mengonfigurasi Nginx Reverse Proxy untuk domain: $DOMAIN..."
if ! command -v nginx &> /dev/null; then
  apt-get install -y nginx
fi

rm -f /etc/nginx/sites-enabled/default
sed "s/example.com/$DOMAIN/g" nginx/conf.d/cloud-arch.conf > /etc/nginx/sites-available/cloud-arch.conf
ln -sf /etc/nginx/sites-available/cloud-arch.conf /etc/nginx/sites-enabled/cloud-arch.conf
nginx -t && systemctl reload nginx

# 6. Build and Launch Containers
echo "🐳 Membangun dan menyalakan container stack..."
docker compose build
docker compose up -d

echo "================================================================="
echo "✓ CLOUD-ARCH BERHASIL DI-DEPLOY DAN AKTIF 24/7!"
echo "• GitLab CE       : https://gitlab.$DOMAIN (Port 8080)"
echo "• JupyterLab RTC  : https://lab.$DOMAIN (Port 8888)"
echo "• MLflow Tracking : https://mlflow.$DOMAIN (Port 5000)"
echo "================================================================="
