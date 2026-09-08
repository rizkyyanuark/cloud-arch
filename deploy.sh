#!/bin/bash
# ==============================================================================
# CLOUD-ARCH MASTER DEPLOYMENT SCRIPT (REPRODUCIBLE INFRASTRUCTURE PROVISIONING)
# ==============================================================================
set -e

echo "================================================================="
echo "       INITIALIZING CLOUD-ARCH ENTERPRISE INFRASTRUCTURE"
echo "================================================================="

# 1. Check Root / Sudo
if [ "$EUID" -ne 0 ]; then
  echo "Harap jalankan script ini dengan sudo: sudo ./deploy.sh"
  exit 1
fi

# 2. Check and Setup 6.0 GB NVMe SWAP (Prevents OOM on 2GB RAM instances)
SWAP_TOTAL=$(free -m | awk '/^Swap:/ {print $2}')
if [ "$SWAP_TOTAL" -lt 5000 ]; then
  echo "Mengalokasikan 6.0 GB SWAP Memory di NVMe SSD..."
  fallocate -l 6G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=6144
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  if ! grep -q "/swapfile" /etc/fstab; then
    echo "/swapfile none swap sw 0 0" >> /etc/fstab
  fi
  # Set swappiness to 10 for low-latency disk I/O
  sysctl vm.swappiness=10
  if ! grep -q "vm.swappiness" /etc/sysctl.conf; then
    echo "vm.swappiness=10" >> /etc/sysctl.conf
  fi
  echo "6.0 GB SWAP Memory dan sysctl swappiness berhasil diaktifkan."
fi

# 3. Load Environment Variables (.env)
if [ ! -f .env ]; then
  echo "File .env tidak ditemukan. Menyalin dari .env.example..."
  cp .env.example .env
fi
source .env

DOMAIN=${BASE_DOMAIN:-tugasakhir.space}
echo "Menggunakan Target Domain: $DOMAIN"

# 4. Check and Install Docker & Docker Compose if missing
if ! command -v docker &> /dev/null; then
  echo "Menginstall Docker Engine & Docker Compose Plugin..."
  apt-get update
  apt-get install -y ca-certificates curl gnupg lsb-release
  mkdir -p /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  usermod -aG docker ubuntu || true
  systemctl enable docker
  systemctl start docker
  echo "Docker Engine berhasil diinstall."
fi

# 5. Setup Persistent Directories & Ownership
echo "Menyiapkan direktori persisten..."
mkdir -p /srv/gitlab/config /srv/gitlab/logs /srv/gitlab/data
mkdir -p /srv/mlflow/data
mkdir -p /home/ubuntu/workspace /home/ubuntu/jupyter-user-data/.jupyter /home/ubuntu/jupyter-user-data/.local
mkdir -p /home/ubuntu/.gemini /home/ubuntu/.config/antigravity /home/ubuntu/antigravity-telegram
if [ ! -f /usr/local/bin/agy ] && [ ! -d /usr/local/bin/agy ]; then
  cat << 'EOF' > /usr/local/bin/agy
#!/usr/bin/env bash
echo "Antigravity CLI wrapper. Install the latest binary or npm package if needed."
EOF
  chmod +x /usr/local/bin/agy
fi
chown -R 1000:100 /home/ubuntu/workspace /home/ubuntu/jupyter-user-data
chown -R ubuntu:ubuntu /home/ubuntu/.gemini /home/ubuntu/.config /home/ubuntu/antigravity-telegram 2>/dev/null || true

# 6. Configure Nginx Reverse Proxy with Dynamic Domain
echo "Mengonfigurasi Nginx Reverse Proxy untuk domain: $DOMAIN..."
if ! command -v nginx &> /dev/null; then
  apt-get install -y nginx
fi

rm -f /etc/nginx/sites-enabled/default
sed "s/example.com/$DOMAIN/g" nginx/conf.d/cloud-arch.conf > /etc/nginx/sites-available/cloud-arch.conf
ln -sf /etc/nginx/sites-available/cloud-arch.conf /etc/nginx/sites-enabled/cloud-arch.conf
nginx -t && systemctl reload nginx

# 7. Setup Systemd Service for Telegram Antigravity Bridge
if [ -f telegram/telegram_antigravity_bridge.py ]; then
  echo "Memasang Telegram Antigravity Gateway Bridge..."
  cp telegram/telegram_antigravity_bridge.py /home/ubuntu/antigravity-telegram/
  chown -R ubuntu:ubuntu /home/ubuntu/antigravity-telegram
  chmod +x /home/ubuntu/antigravity-telegram/telegram_antigravity_bridge.py
  
  # Install python dependencies for telegram bridge if python3 is present
  if command -v python3 &> /dev/null; then
    apt-get install -y python3-pip python3-venv || true
    pip3 install --break-system-packages --progress-bar off aiohttp psutil requests telegramify_markdown 2>/dev/null || pip3 install --progress-bar off aiohttp psutil requests telegramify_markdown 2>/dev/null || true
  fi

  if [ -f telegram/antigravity-telegram.service ]; then
    cp telegram/antigravity-telegram.service /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable antigravity-telegram.service
    systemctl restart antigravity-telegram.service || true
    echo "Service antigravity-telegram berhasil dipasang."
  fi
fi

# 8. Build and Launch Containers
echo "Membangun dan menyalakan container stack..."
chmod +x mlflow/run_mlflow.sh 2>/dev/null || true
docker compose build
docker compose up -d

echo "================================================================="
echo "CLOUD-ARCH BERHASIL DI-DEPLOY DAN AKTIF"
echo "GitLab CE       : https://gitlab.$DOMAIN (Port 8080 & SSH 2222)"
echo "JupyterLab RTC  : https://lab.$DOMAIN (Port 8888)"
echo "Google OAuth Web: https://lab.$DOMAIN/oauth2callback (Port 8085)"
echo "MLflow Tracking : https://mlflow.$DOMAIN (Port 5000)"
echo "================================================================="
