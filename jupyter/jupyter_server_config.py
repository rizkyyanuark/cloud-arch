import os
import sys

# Inject /etc/jupyter into python sys.path
sys.path.insert(0, '/etc/jupyter')

from dynamic_kernels import DynamicVenvKernelSpecManager

c = get_config()

# Enable Dynamic Kernel Spec Manager
c.ServerApp.kernel_spec_manager_class = DynamicVenvKernelSpecManager

# Real-Time Collaboration (RTC) & Yjs settings
c.LabApp.collaborative = True
c.FileContentsManager.autosave_interval = 5

# Networking & Security
c.ServerApp.ip = '0.0.0.0'
c.ServerApp.port = 8888
c.ServerApp.allow_origin = '*'
c.ServerApp.allow_remote_access = True
c.ServerApp.token = os.environ.get('JUPYTER_TOKEN', 'admin')
c.ServerApp.root_dir = '/home/jovyan/work'

# Allow iframe and WebSocket proxy upgrades
c.ServerApp.tornado_settings = {
    'headers': {
        'Content-Security-Policy': "frame-ancestors 'self' *"
    }
}
