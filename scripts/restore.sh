#!/usr/bin/env bash
# ==============================================================================
# 🔄 CLOUD-ARCH DISASTER RECOVERY & RESTORE ENGINE
# ==============================================================================
# Restores GitLab CE repositories/secrets, MLflow SQLite DB, and Jupyter state.
# Can restore from local archive or fetch latest backup from Cloudflare R2.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Load Environment Variables (.env) with Auto-Discovery
for env_file in "${ROOT_DIR}/.env" "/home/ubuntu/infra-hub/.env" "/home/ubuntu/cloud-arch/.env" "/etc/cloud-arch/.env"; do
    if [ -f "${env_file}" ]; then
        # shellcheck disable=SC1090
        source "${env_file}"
        export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-}"
        export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-}"
        break
    fi
done

R2_BUCKET="${R2_BUCKET_NAME:-mini-project-lake}"
R2_ENDPOINT="${R2_ENDPOINT_URL:-https://11d2d9aa25f8977089f6f9430db62d02.r2.cloudflarestorage.com}"

TARGET_ARCHIVE="${1:-}"

TEMP_RESTORE_DIR="/tmp/cloud-arch-restore"
mkdir -p "${TEMP_RESTORE_DIR}"
chmod 700 "${TEMP_RESTORE_DIR}"

cleanup() {
    rm -rf "${TEMP_RESTORE_DIR}"
}
trap cleanup EXIT

echo "================================================================="
echo "       🔄 INITIALIZING CLOUD-ARCH RESTORE ENGINE"
echo "================================================================="

# 1. Fetch Archive if not provided locally
if [ -z "${TARGET_ARCHIVE}" ]; then
    echo "Mencari arsip cadangan terbaru di Cloudflare R2..."
    LATEST_REMOTE=$(aws s3 ls "s3://${R2_BUCKET}/backups/" --endpoint-url "${R2_ENDPOINT}" | sort -k1,2 | tail -n 1 | awk '{print $4}' || true)
    if [ -z "${LATEST_REMOTE}" ]; then
        echo "❌ Tidak ditemukan arsip cadangan di Cloudflare R2!"
        exit 1
    fi
    echo "Mengunduh cadangan terbaru: ${LATEST_REMOTE}..."
    TARGET_ARCHIVE="/tmp/${LATEST_REMOTE}"
    aws s3 cp "s3://${R2_BUCKET}/backups/${LATEST_REMOTE}" "${TARGET_ARCHIVE}" --endpoint-url "${R2_ENDPOINT}"
fi

if [ ! -f "${TARGET_ARCHIVE}" ]; then
    echo "❌ File arsip tidak ditemukan: ${TARGET_ARCHIVE}"
    exit 1
fi

echo "Mengekstrak arsip cadangan..."
tar -xzf "${TARGET_ARCHIVE}" -C "${TEMP_RESTORE_DIR}"

# 2. Restore MLflow SQLite DB
if [ -f "${TEMP_RESTORE_DIR}/mlflow.db" ]; then
    echo "🔄 [1/3] Memulihkan MLflow SQLite Metadata..."
    mkdir -p /srv/mlflow/data
    cp "${TEMP_RESTORE_DIR}/mlflow.db" /srv/mlflow/data/mlflow.db
    echo "✓ Database MLflow berhasil dipulihkan."
fi

# 3. Restore Jupyter Settings
if [ -d "${TEMP_RESTORE_DIR}/jupyter-settings" ]; then
    echo "🔄 [2/3] Memulihkan Pengaturan Jupyter..."
    mkdir -p /home/ubuntu/jupyter-user-data/.jupyter
    cp -r "${TEMP_RESTORE_DIR}/jupyter-settings/"* /home/ubuntu/jupyter-user-data/.jupyter/ 2>/dev/null || true
    chown -R 1000:100 /home/ubuntu/jupyter-user-data
    echo "✓ Pengaturan Jupyter berhasil dipulihkan."
fi

# 4. Restore GitLab CE
if [ -f "${TEMP_RESTORE_DIR}/gitlab-secrets.json" ]; then
    echo "🔄 [3/3] Memulihkan Konfigurasi dan Secrets GitLab..."
    mkdir -p /srv/gitlab/config /srv/gitlab/data/backups
    cp "${TEMP_RESTORE_DIR}/gitlab-secrets.json" /srv/gitlab/config/gitlab-secrets.json
    if [ -f "${TEMP_RESTORE_DIR}/gitlab.rb" ]; then
        cp "${TEMP_RESTORE_DIR}/gitlab.rb" /srv/gitlab/config/gitlab.rb
    fi
    echo "✓ Secrets GitLab berhasil dipulihkan."
fi

if [ -f "${TEMP_RESTORE_DIR}/gitlab_backup.tar" ]; then
    echo "Menyalin tarball backup GitLab ke direktori /srv/gitlab/data/backups/..."
    cp "${TEMP_RESTORE_DIR}/gitlab_backup.tar" /srv/gitlab/data/backups/
    echo "Untuk menyelesaikan pemulihan repositori GitLab, jalankan di dalam container:"
    echo "docker exec -it gitlab-ce gitlab-backup restore BACKUP=gitlab_backup force=yes"
fi

echo "================================================================="
echo "✅ PROSES PEMULIHAN (RESTORE) SELESAI!"
echo "================================================================="
