"""Audit saved JSON evidence; no candidate execution or model call."""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[4] / 'src'))
from vao.repair.stdin_results import reproduce
if __name__ == '__main__':
    print(reproduce(HERE))
