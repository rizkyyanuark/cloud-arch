#!/usr/bin/env bash
# ==============================================================================
# 🩺 CLOUD-ARCH AUTOMATED READINESS & HEALTH PROBE
# ==============================================================================
# Performs end-to-end status auditing for Docker, local ports, memory, and Nginx.
# Exits with 0 on full health, 1 on any failure.
# ==============================================================================

set -uo pipefail

FAILED=0

echo "================================================================="
echo "       🩺 AUDITING CLOUD-ARCH INFRASTRUCTURE HEALTH"
echo "================================================================="

# 1. Memory & SWAP Check
echo "🔍 [1/4] Memeriksa Alokasi Memori & Swap..."
SWAP_TOTAL=$(free -m | awk '/^Swap:/ {print $2}')
SWAP_USED=$(free -m | awk '/^Swap:/ {print $3}')
if [ "$SWAP_TOTAL" -lt 2000 ]; then
    echo "⚠️ PERINGATAN: SWAP memory kurang dari 2.0 GB (${SWAP_TOTAL} MB terdeteksi)."
    FAILED=1
else
    echo "✓ SWAP Memory memadai: Total ${SWAP_TOTAL} MB, Terpakai ${SWAP_USED} MB."
fi

# 2. Docker Containers Health
echo "🔍 [2/4] Memeriksa Status Kontainer Docker..."
CONTAINERS=("jupyterlab" "gitlab-ce" "mlflow-server")
for c in "${CONTAINERS[@]}"; do
    STATUS=$(docker inspect --format '{{.State.Status}}' "$c" 2>/dev/null || echo "not_found")
    HEALTH=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$c" 2>/dev/null || echo "none")
    OOM=$(docker inspect --format '{{.State.OOMKilled}}' "$c" 2>/dev/null || echo "false")
    
    if [ "$STATUS" = "running" ]; then
        if [ "$OOM" = "true" ]; then
            echo "❌ KONTROL: Kontainer $c pernah terbunuh oleh Linux OOM!"
            FAILED=1
        else
            echo "✓ Kontainer $c aktif (Health: $HEALTH)"
        fi
    else
        echo "❌ Kontainer $c TIDAK AKTIF (Status: $STATUS)!"
        FAILED=1
    fi
done

# 3. Internal Service Ports Check
echo "🔍 [3/4] Memeriksa Konektivitas Port Lokal..."
# JupyterLab (8888)
if curl -s -m 5 -o /dev/null -w "%{http_code}" http://127.0.0.1:8888 | grep -qE "200|302|405"; then
    echo "✓ JupyterLab merespons di http://127.0.0.1:8888"
else
    echo "❌ JupyterLab gagal merespons di port 8888!"
    FAILED=1
fi

# MLflow (5000)
if curl -s -m 5 -o /dev/null -w "%{http_code}" http://127.0.0.1:5000 | grep -qE "200"; then
    echo "✓ MLflow merespons di http://127.0.0.1:5000"
else
    echo "❌ MLflow gagal merespons di port 5000!"
    FAILED=1
fi

# GitLab (8080)
if curl -s -m 5 -o /dev/null -w "%{http_code}" http://127.0.0.1:8080 | grep -qE "200|302"; then
    echo "✓ GitLab CE merespons di http://127.0.0.1:8080"
else
    echo "❌ GitLab CE gagal merespons di port 8080 (kemungkinan masih migrasi database)!"
    FAILED=1
fi

# 4. Nginx Reverse Proxy Check
echo "🔍 [4/4] Memeriksa Nginx Reverse Proxy..."
if systemctl is-active --quiet nginx; then
    echo "✓ Layanan Nginx aktif dan berjalan."
else
    echo "❌ Layanan Nginx TIDAK AKTIF!"
    FAILED=1
fi

echo "================================================================="
if [ "$FAILED" -eq 0 ]; then
    echo "🎉 SELURUH SISTEM CLOUD-ARCH DALAM KONDISI PRIMA (STATUS: HEALTHY)"
    echo "================================================================="
    exit 0
else
    echo "⚠️ DITEMUKAN KOMPONEN TIDAK SEHAT ATAU MASIH PROSES INISIALISASI"
    echo "================================================================="
    exit 1
fi
