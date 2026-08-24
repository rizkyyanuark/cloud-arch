#!/bin/bash
# End-to-end health probe for all cloud-arch subdomains
echo "=== 🔍 TESTING ALL CLOUD-ARCH SUBDOMAINS ==="

domains=("gitlab.tugasakhir.space" "lab.tugasakhir.space" "mlflow.tugasakhir.space")

for d in "${domains[@]}"; do
    code=$(curl -s -o /dev/null -w "%{http_code}" -L "https://$d")
    echo "• Domain https://$d -> HTTP Status: $code"
done
