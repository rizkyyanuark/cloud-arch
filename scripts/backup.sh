#!/usr/bin/env bash
# ==============================================================================
# 💾 CLOUD-ARCH AUTOMATED DISASTER RECOVERY & BACKUP ENGINE
# ==============================================================================
# Backs up GitLab CE, MLflow SQLite DB, and Jupyter configuration.
# Bundles, timestamps, and uploads archives to Cloudflare R2 ($0 Egress).
# Retains last 7 days of daily backups automatically.
# ==============================================================================

set -euo pipefail

BACKUP_DATE=$(date +"%Y%m%d_%H%M%S")
TEMP_DIR="/tmp/cloud-arch-backup-${BACKUP_DATE}"
RETENTION_DAYS=7

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Load Environment Variables (.env)
if [ -f "${ROOT_DIR}/.env" ]; then
    # shellcheck disable=SC1091
    source "${ROOT_DIR}/.env"
fi

R2_BUCKET="${R2_BUCKET_NAME:-mini-project-lake}"
R2_ENDPOINT="${R2_ENDPOINT_URL:-https://11d2d9aa25f8977089f6f9430db62d02.r2.cloudflarestorage.com}"

echo "================================================================="
echo "       🚀 STARTING CLOUD-ARCH AUTOMATED SYSTEM BACKUP"
echo "• Timestamp      : ${BACKUP_DATE}"
echo "• Target Storage : Cloudflare R2 (s3://${R2_BUCKET}/backups/)"
echo "• Endpoint URL   : ${R2_ENDPOINT}"
echo "================================================================="

mkdir -p "${TEMP_DIR}"
chmod 700 "${TEMP_DIR}"

cleanup() {
    rm -rf "${TEMP_DIR}"
}
trap cleanup EXIT

# 1. Backup GitLab CE (Omnibus CRON mode)
echo "📦 [1/4] Mencadangkan GitLab CE (Database & Repositories)..."
if docker ps --format '{{.Names}}' | grep -q "^gitlab-ce$"; then
    docker exec gitlab-ce gitlab-backup create CRON=1
    
    # Locate latest GitLab backup tarball
    LATEST_GITLAB_TAR=$(find /srv/gitlab/data/backups -name "*_gitlab_backup.tar" -type f -printf '%T@ %p\n' 2>/dev/null | sort -k1nr | head -n 1 | awk '{print $2}' || true)
    if [ -n "${LATEST_GITLAB_TAR}" ] && [ -f "${LATEST_GITLAB_TAR}" ]; then
        cp "${LATEST_GITLAB_TAR}" "${TEMP_DIR}/gitlab_backup.tar"
        echo "✓ GitLab backup tarball berhasil disalin: $(basename "${LATEST_GITLAB_TAR}")"
    fi

    # Crucial: Backup GitLab secrets & configuration
    if [ -f /srv/gitlab/config/gitlab-secrets.json ]; then
        cp /srv/gitlab/config/gitlab-secrets.json "${TEMP_DIR}/gitlab-secrets.json"
        echo "✓ gitlab-secrets.json berhasil dicadangkan."
    fi
    if [ -f /srv/gitlab/config/gitlab.rb ]; then
        cp /srv/gitlab/config/gitlab.rb "${TEMP_DIR}/gitlab.rb"
        echo "✓ gitlab.rb berhasil dicadangkan."
    fi
else
    echo "⚠️ Kontainer gitlab-ce tidak berjalan, melewati pencadangan GitLab."
fi

# 2. Backup MLflow Metadata (Consistent SQLite Snapshot)
echo "📦 [2/4] Mencadangkan MLflow Database Metadata..."
if [ -f /srv/mlflow/data/mlflow.db ]; then
    if command -v sqlite3 &>/dev/null; then
        sqlite3 /srv/mlflow/data/mlflow.db ".backup '${TEMP_DIR}/mlflow.db'"
    else
        # Fallback to file copy if sqlite3 binary is absent on host
        cp /srv/mlflow/data/mlflow.db "${TEMP_DIR}/mlflow.db"
    fi
    echo "✓ Database SQLite MLflow berhasil dicadangkan."
fi

# 3. Backup Jupyter User Settings & Collaboration State
echo "📦 [3/4] Mencadangkan Pengaturan Jupyter & State Kolaborasi..."
if [ -d /home/ubuntu/jupyter-user-data/.jupyter ]; then
    mkdir -p "${TEMP_DIR}/jupyter-settings"
    cp -r /home/ubuntu/jupyter-user-data/.jupyter/* "${TEMP_DIR}/jupyter-settings/" 2>/dev/null || true
    echo "✓ Pengaturan Jupyter (.jupyter) berhasil dicadangkan."
fi

# 4. Compress, Package, and Upload to Cloudflare R2
ARCHIVE_NAME="cloud-arch-backup-${BACKUP_DATE}.tar.gz"
ARCHIVE_PATH="/tmp/${ARCHIVE_NAME}"

echo "📦 [4/4] Mengompresi dan mengunggah arsip ke Cloudflare R2..."
tar -czf "${ARCHIVE_PATH}" -C "${TEMP_DIR}" .

# Check AWS CLI or R2 Credentials
if command -v aws &>/dev/null && [ -n "${AWS_ACCESS_KEY_ID:-}" ] && [ -n "${AWS_SECRET_ACCESS_KEY:-}" ]; then
    echo "Mengunggah ${ARCHIVE_NAME} ke Cloudflare R2..."
    aws s3 cp "${ARCHIVE_PATH}" "s3://${R2_BUCKET}/backups/${ARCHIVE_NAME}" \
        --endpoint-url "${R2_ENDPOINT}" \
        --no-progress

    echo "✅ Backup berhasil diunggah ke s3://${R2_BUCKET}/backups/${ARCHIVE_NAME}"
    rm -f "${ARCHIVE_PATH}"

    # Prune remote backups older than 7 days
    echo "🧹 Membersihkan cadangan lama di Cloudflare R2 (> ${RETENTION_DAYS} hari)..."
    CUTOFF_DATE=$(date -d "${RETENTION_DAYS} days ago" +%Y%m%d 2>/dev/null || date -v-"${RETENTION_DAYS}"d +%Y%m%d)
    aws s3 ls "s3://${R2_BUCKET}/backups/" --endpoint-url "${R2_ENDPOINT}" | while read -r line; do
        FILE_NAME=$(echo "$line" | awk '{print $4}')
        if [[ "$FILE_NAME" =~ cloud-arch-backup-([0-9]{8})_.*\.tar\.gz ]]; then
            FILE_DATE="${BASH_REMATCH[1]}"
            if [ "$FILE_DATE" -lt "$CUTOFF_DATE" ]; then
                echo "Menghapus cadangan usang: $FILE_NAME"
                aws s3 rm "s3://${R2_BUCKET}/backups/${FILE_NAME}" --endpoint-url "${R2_ENDPOINT}" || true
            fi
        fi
    done
else
    echo "⚠️ AWS CLI atau kredensial R2 tidak terdeteksi. Arsip lokal disimpan di: ${ARCHIVE_PATH}"
fi

echo "================================================================="
echo "🎉 PENCADANGAN CLOUD-ARCH SELESAI DENGAN SUKSES!"
echo "================================================================="
exit 0
