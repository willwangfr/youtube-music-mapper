import sys
from pathlib import Path

# Backend modules are flat imports; make them importable when pytest is run
# from the repo root as well as from backend/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
