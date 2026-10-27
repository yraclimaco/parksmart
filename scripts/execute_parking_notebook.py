"""Execute Issue #11 with the current Python environment, retaining outputs locally."""

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import nbformat
from jupyter_client import AsyncKernelManager
from jupyter_client.kernelspec import KernelSpecManager
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks/11_parking_patterns.ipynb"
CELL_TIMEOUT_SECONDS = 600


def main():
    """Execute the issue notebook with sys.executable and save successful output.

    No arguments or return value. A temporary kernel spec avoids changing user
    Jupyter settings or accidentally executing in a different Python environment.
    """
    with TemporaryDirectory(prefix="parksmart-kernel-") as temporary:
        kernel_dir = Path(temporary) / "parksmart"
        kernel_dir.mkdir()
        spec = {
            "argv": [sys.executable, "-m", "ipykernel_launcher", "-f",
                     "{connection_file}"],
            "display_name": "ParkSmart current Python", "language": "python",
        }
        (kernel_dir / "kernel.json").write_text(json.dumps(spec), encoding="utf-8")
        notebook = nbformat.read(NOTEBOOK, as_version=4)
        manager = KernelSpecManager(kernel_dirs=[temporary])
        kernel = AsyncKernelManager(
            kernel_name="parksmart", kernel_spec_manager=manager
        )
        client = NotebookClient(
            notebook, km=kernel, timeout=CELL_TIMEOUT_SECONDS,
            resources={"metadata": {"path": str(ROOT)}},
        )
        client.execute()
        nbformat.write(notebook, NOTEBOOK)
    print(f"Executed {NOTEBOOK.name} successfully using {sys.executable}")


if __name__ == "__main__":
    main()
