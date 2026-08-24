"""
dynamic_kernels.py - Dynamic Venv Kernel Auto-Discovery Manager
Scans all folders in /home/jovyan/work/ and automatically exposes virtual environments (.venv)
as independent, zero-restart Jupyter kernels: Python (<folder_name>).
"""

import os
from jupyter_client.kernelspec import KernelSpecManager, NoSuchKernel

class DynamicVenvKernelSpecManager(KernelSpecManager):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.work_dir = os.environ.get("JUPYTER_WORK_DIR", "/home/jovyan/work")

    def _discover_venvs(self):
        venvs = {}
        if not os.path.exists(self.work_dir):
            return venvs

        for entry in os.listdir(self.work_dir):
            entry_path = os.path.join(self.work_dir, entry)
            if os.path.isdir(entry_path) and not entry.startswith('.'):
                venv_python = os.path.join(entry_path, ".venv", "bin", "python")
                if os.path.isfile(venv_python) and os.access(venv_python, os.X_OK):
                    kernel_name = f"auto-venv-{entry.lower().replace('_', '-')}"
                    venvs[kernel_name] = {
                        "display_name": f"Python ({entry})",
                        "language": "python",
                        "argv": [venv_python, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
                        "metadata": {"project_path": entry_path}
                    }
        return venvs

    def get_all_specs(self):
        specs = super().get_all_specs()
        for name, spec_data in self._discover_venvs().items():
            specs[name] = {"spec": spec_data, "resource_dir": ""}
        return specs

    def get_kernel_spec(self, kernel_name):
        venvs = self._discover_venvs()
        if kernel_name in venvs:
            from jupyter_client.kernelspec import KernelSpec
            return KernelSpec(**venvs[kernel_name])
        return super().get_kernel_spec(kernel_name)
