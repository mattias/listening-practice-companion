"""Builds the Windows program: python build.py  ->  dist/ListeningPracticeCompanion.exe

Needs the dev extras (pip install -e ".[dev]"). The program is one file with Python and everything it needs inside."""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

cmd = [
    sys.executable, "-m", "PyInstaller",
    "--noconfirm", "--clean", "--onefile", "--windowed",
    "--name", "ListeningPracticeCompanion",
    # The dictionary is Python files that Janome reads by path, so the whole package goes in as it is.
    "--collect-all", "janome",
    "--collect-submodules", "uvicorn",
    "--collect-submodules", "companion",
    "--distpath", os.path.join(HERE, "dist"),
    "--workpath", os.path.join(HERE, "build"),
    "--specpath", os.path.join(HERE, "build"),
    os.path.join(HERE, "run_companion.py"),
]
subprocess.run(cmd, check=True, cwd=HERE)
print("built", os.path.join(HERE, "dist", "ListeningPracticeCompanion.exe"))
