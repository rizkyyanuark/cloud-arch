"""
scripts/seed_gitlab.py - Automated GitLab Groups & Repositories Seeder
Uses GitLab REST API to automatically create groups: 'infrastructure' and 'research'.
"""

import urllib.request
import json
import os
import sys

GITLAB_URL = os.getenv("GITLAB_URL", "http://127.0.0.1:8080")
PRIVATE_TOKEN = os.getenv("GITLAB_ROOT_TOKEN", "glpat-secret-root-token")

def make_request(endpoint, data=None):
    url = f"{GITLAB_URL}/api/v4/{endpoint}"
    headers = {"PRIVATE-TOKEN": PRIVATE_TOKEN, "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8") if data else None, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        print(f"Request failed for {endpoint}: {e}")
        return None

def seed_groups():
    print("🌱 Seeding GitLab Groups...")
    groups = ["infrastructure", "research"]
    for g in groups:
        res = make_request("groups", {"name": g.capitalize(), "path": g, "visibility": "private"})
        if res:
            print(f"✓ Group '{g}' created successfully (ID: {res.get('id')})")

if __name__ == "__main__":
    seed_groups()
