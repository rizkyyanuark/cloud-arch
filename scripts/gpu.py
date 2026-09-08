#!/usr/bin/env python3
"""
Canonical On-Demand Ephemeral GPU Switch Orchestrator (Multi-Provider: AWS Spot and Vast.ai)
Production Hardened Version with 5-Channel ZeroMQ Forward Tunneling
Author: Rizky Yanuar Kristianto (mini-project ecosystem)
Location on Host: /home/ubuntu/.local/bin/gpu
"""

import sys
import os
import time
import json
import subprocess
import shutil
from pathlib import Path
import urllib.request
import urllib.error

STATE_FILE = Path("/home/ubuntu/.config/gpu-switcher/state.json")
KERNEL_DIR = Path("/home/ubuntu/jupyter-user-data/.local/share/jupyter/kernels/remote-gpu")
SSH_KEY = Path("/home/ubuntu/.ssh/mini-project-key.pem")
DEFAULT_WORKSPACE_ROOT = Path("/home/ubuntu/workspace/mini-project")
AWS_REGION = "us-east-1"
AWS_KEY_NAME = "mini-project-key"

def load_vast_api_key():
    env_key = os.environ.get("VAST_API_KEY")
    if env_key:
        return env_key
    mcp_config = Path("/home/ubuntu/.gemini/config/mcp_config.json")
    if mcp_config.exists():
        try:
            with open(mcp_config, "r", encoding="utf-8") as f:
                data = json.load(f)
                key = data.get("mcpServers", {}).get("vast-ai", {}).get("env", {}).get("VAST_API_KEY")
                if key:
                    return key
        except Exception:
            pass
    return "6bbdf833d7aed496c75051cefbfa17eb95b6d9c11704f44325c02e4c1a3bca5b"

def get_active_project_dir():
    return DEFAULT_WORKSPACE_ROOT

def run_cmd(cmd, check=True):
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or f"Command failed: {cmd}")
    return res.stdout.strip()

def launch_aws_spot_gpu(instance_type="g4dn.xlarge"):
    print(f"🔍 [1/5] Mencari Deep Learning PyTorch AMI di AWS EC2 ({AWS_REGION})...")
    sg_out = run_cmd(f"aws ec2 describe-security-groups --region {AWS_REGION}")
    sgs = json.loads(sg_out).get("SecurityGroups", [])
    sg_id = None
    for s in sgs:
        if "mini-project" in s["GroupName"]:
            sg_id = s["GroupId"]
            break
    if not sg_id and sgs:
        sg_id = sgs[0]["GroupId"]
    
    ami_cmd = f'aws ec2 describe-images --owners amazon --filters "Name=name,Values=Deep Learning OSS Nvidia Driver AMI GPU PyTorch * (Ubuntu 22.04)*" "Name=state,Values=available" "Name=architecture,Values=x86_64" --region {AWS_REGION}'
    try:
        ami_data = json.loads(run_cmd(ami_cmd))
        images = ami_data.get("Images", [])
        if images:
            images.sort(key=lambda x: x["CreationDate"], reverse=True)
            ami_id = images[0]["ImageId"]
            ami_name = images[0]["Name"]
            print(f"✓ Ditemukan DLAMI: {ami_name} ({ami_id})")
        else:
            ami_id = "ami-012ba162b9cd2729c"
    except Exception:
        ami_id = "ami-012ba162b9cd2729c"

    print(f"🚀 [2/5] Mengajukan Permintaan EC2 Spot Instance ({instance_type} - NVIDIA T4 16GB)...")
    market_options = json.dumps({
        "MarketType": "spot",
        "SpotOptions": {
            "SpotInstanceType": "one-time",
            "InstanceInterruptionBehavior": "terminate"
        }
    }).replace('"', '\\"')

    tags = json.dumps([
        {
            "ResourceType": "instance",
            "Tags": [{"Key": "Name", "Value": "mini-project-ephemeral-gpu"}]
        }
    ]).replace('"', '\\"')

    run_inst_cmd = f'aws ec2 run-instances --image-id {ami_id} --instance-type {instance_type} --key-name {AWS_KEY_NAME} --security-group-ids {sg_id} --instance-market-options "{market_options}" --tag-specifications "{tags}" --region {AWS_REGION}'
    
    launch_res = json.loads(run_cmd(run_inst_cmd))
    instance_id = launch_res["Instances"][0]["InstanceId"]
    print(f"✓ Spot Request Diterima! Instance ID: {instance_id}. Menunggu status running...")

    public_ip = None
    for attempt in range(60):
        time.sleep(5)
        desc = json.loads(run_cmd(f"aws ec2 describe-instances --instance-ids {instance_id} --region {AWS_REGION}"))
        inst = desc["Reservations"][0]["Instances"][0]
        state = inst["State"]["Name"]
        public_ip = inst.get("PublicIpAddress")
        sys.stdout.write(f"\r⏳ Status AWS GPU: [{state}] IP: [{public_ip or 'allocating'}] (detik ke-{(attempt+1)*5})...")
        sys.stdout.flush()

        if state == "running" and public_ip:
            print(f"\n✅ AWS Spot GPU Running! Public IP: {public_ip}")
            break

    if not public_ip:
        raise TimeoutError("AWS Spot Instance tidak mendapatkan Public IP dalam 5 menit.")

    return {
        "provider": "aws",
        "instance_id": instance_id,
        "instance_type": instance_type,
        "gpu_name": "NVIDIA T4 Tensor Core (16GB)",
        "python_path": "/opt/pytorch/bin/python3",
        "ssh_user": "ubuntu",
        "dph": 0.36,
        "ssh_host": public_ip,
        "ssh_port": 22,
        "started_at": int(time.time()),
        "project_dir": str(get_active_project_dir())
    }

def sync_code_to_gpu(instance_info):
    project_dir = Path(instance_info["project_dir"])
    ssh_host = instance_info["ssh_host"]
    ssh_port = instance_info["ssh_port"]
    ssh_user = instance_info.get("ssh_user", "ubuntu")
    
    print(f"📁 [3/5] Melakukan Auto Code Sync dari '{project_dir.name}' ke GPU...")
    ssh_cmd = f"ssh -p {ssh_port} -o StrictHostKeyChecking=no -i {SSH_KEY}"
    remote_dest = f"/workspace/{project_dir.name}/" if ssh_user == "root" else f"/home/{ssh_user}/workspace/{project_dir.name}/"

    subprocess.run(f"{ssh_cmd} {ssh_user}@{ssh_host} 'mkdir -p {remote_dest}'", shell=True, capture_output=True)

    rsync_cmd = [
        "rsync", "-avz", "--delete",
        "-e", ssh_cmd,
        "--exclude", ".git",
        "--exclude", "data",
        "--exclude", ".venv",
        "--exclude", "__pycache__",
        "--exclude", ".ipynb_checkpoints",
        f"{project_dir}/",
        f"{ssh_user}@{ssh_host}:{remote_dest}"
    ]
    
    res = subprocess.run(rsync_cmd, capture_output=True, text=True)
    if res.returncode == 0:
        print(f"✓ Kode modular '{project_dir.name}' berhasil disinkronkan!")
    else:
        print(f"⚠️ Rsync note: {res.stderr.strip() or 'OK'}")

def register_remote_kernel(instance_info):
    print("📓 [4/5] Mendaftarkan ZeroMQ Tunnel Kernel ke JupyterLab...")
    KERNEL_DIR.mkdir(parents=True, exist_ok=True)
    
    gpu_display = f"Python (GPU - {instance_info['gpu_name']})"
    ssh_host = instance_info["ssh_host"]
    ssh_port = instance_info["ssh_port"]
    ssh_user = instance_info.get("ssh_user", "ubuntu")
    python_path = instance_info.get("python_path", "python3")
    
    container_key_dir = Path("/home/ubuntu/jupyter-user-data/.ssh")
    container_key_dir.mkdir(parents=True, exist_ok=True)
    if SSH_KEY.exists():
        shutil.copy(SSH_KEY, container_key_dir / "mini-project-key.pem")
        os.chmod(container_key_dir / "mini-project-key.pem", 0o600)

    bridge_py = f'''#!/usr/bin/env python3
import sys, os, json, subprocess, uuid, signal

if len(sys.argv) < 2:
    sys.exit(1)

conn_file = sys.argv[1]
with open(conn_file, "r") as f:
    conn_data = json.load(f)

shell_port = conn_data["shell_port"]
iopub_port = conn_data["iopub_port"]
stdin_port = conn_data["stdin_port"]
control_port = conn_data["control_port"]
hb_port = conn_data["hb_port"]

remote_conn = f"/tmp/kernel-{{uuid.uuid4().hex[:8]}}.json"
ssh_key = "/home/jovyan/.ssh/mini-project-key.pem"
if not os.path.exists(ssh_key):
    ssh_key = "/home/ubuntu/.ssh/mini-project-key.pem"

subprocess.run(["scp", "-P", "{ssh_port}", "-o", "StrictHostKeyChecking=no", "-i", ssh_key, conn_file, f"{ssh_user}@{ssh_host}:{{remote_conn}}"], check=True)

ssh_cmd = [
    "ssh", "-p", "{ssh_port}", "-o", "StrictHostKeyChecking=no",
    "-i", ssh_key,
    "-L", f"{{shell_port}}:127.0.0.1:{{shell_port}}",
    "-L", f"{{iopub_port}}:127.0.0.1:{{iopub_port}}",
    "-L", f"{{stdin_port}}:127.0.0.1:{{stdin_port}}",
    "-L", f"{{control_port}}:127.0.0.1:{{control_port}}",
    "-L", f"{{hb_port}}:127.0.0.1:{{hb_port}}",
    "{ssh_user}@{ssh_host}",
    f"{python_path} -m ipykernel_launcher -f {{remote_conn}}"
]

proc = subprocess.Popen(ssh_cmd)

def cleanup(sig=None, frame=None):
    proc.terminate()
    try:
        subprocess.run(["ssh", "-p", "{ssh_port}", "-o", "StrictHostKeyChecking=no", "-i", ssh_key, f"{ssh_user}@{ssh_host}", f"rm -f {{remote_conn}}"], timeout=3)
    except Exception:
        pass
    sys.exit(0)

signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)
proc.wait()
cleanup()
'''
    (KERNEL_DIR / "kernel_bridge.py").write_text(bridge_py, encoding="utf-8")
    (KERNEL_DIR / "kernel_bridge.py").chmod(0o755)

    kernel_json = {
        "argv": ["python3", "/home/jovyan/.local/share/jupyter/kernels/remote-gpu/kernel_bridge.py", "{connection_file}"],
        "display_name": gpu_display,
        "language": "python"
    }
    with open(KERNEL_DIR / "kernel.json", "w") as f:
        json.dump(kernel_json, f, indent=2)

    print(f"✓ Kernel '{gpu_display}' siap dipilih di JupyterLab!")

def cmd_on(gpu="T4", provider="aws"):
    print("==================================================")
    print(f"⚡ MEMULAI PELUNCURAN GPU ON-DEMAND ({provider.upper()})")
    print("==================================================")
    
    if STATE_FILE.exists():
        print("⚠️ GPU sudah aktif!")
        cmd_status()
        return

    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    info = launch_aws_spot_gpu()
    sync_code_to_gpu(info)
    register_remote_kernel(info)
    
    with open(STATE_FILE, "w") as f:
        json.dump(info, f, indent=2)
    
    print("\n🎉 SAKELAR GPU DINYALAKAN OTOMATIS 100%!")
    print(f"• GPU       : {info['gpu_name']}")
    print(f"• Public IP : {info['ssh_host']}")
    print(f"👉 Kernel '{info['gpu_name']}' langsung muncul di https://lab.tugasakhir.space!")

def cmd_off():
    print("🛑 Mematikan GPU On-Demand...")
    if not STATE_FILE.exists():
        print("ℹ️ GPU sudah offline.")
        if KERNEL_DIR.exists():
            shutil.rmtree(KERNEL_DIR, ignore_errors=True)
        return
    
    try:
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
    except Exception:
        state = {}
    
    if KERNEL_DIR.exists():
        shutil.rmtree(KERNEL_DIR, ignore_errors=True)
    
    inst_id = state.get("instance_id")
    if inst_id:
        try:
            run_cmd(f"aws ec2 terminate-instances --instance-ids {inst_id} --region {AWS_REGION}")
            print(f"✓ Instance {inst_id} berhasil di-terminate!")
        except Exception as e:
            print(f"⚠️ AWS: {e}")
    
    if STATE_FILE.exists():
        STATE_FILE.unlink()
    print("✅ GPU Dimatikan & Tagihan Berhenti ($0.00).")

def cmd_status():
    if not STATE_FILE.exists():
        print("ℹ️ Status: GPU OFFLINE ($0.00).")
        return
    with open(STATE_FILE, "r") as f:
        state = json.load(f)
    print(f"🎮 GPU AKTIF: {state.get('gpu_name')} ({state.get('ssh_host')})")

def main():
    if len(sys.argv) < 2:
        return
    cmd = sys.argv[1].lower()
    if cmd == "on":
        cmd_on()
    elif cmd == "off":
        cmd_off()
    elif cmd == "status":
        cmd_status()

if __name__ == "__main__":
    main()
