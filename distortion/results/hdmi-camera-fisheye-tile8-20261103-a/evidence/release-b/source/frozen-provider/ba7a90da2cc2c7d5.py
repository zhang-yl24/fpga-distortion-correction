"""Run the retained 323 contracts against the closed seven-module revision."""
from pathlib import Path
import sys
WORK=Path(__file__).resolve().parent;ROOT=WORK.parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT.parent/'.venv/Lib/site-packages')]
import pytest
raise SystemExit(pytest.main([*[str(p)for p in sorted((WORK/'root-adapter-tests-v2-a').glob('*.py'))],
    '-q','--junitxml='+str(WORK/'root-adapter-tests-v2-a/results.xml')]))
