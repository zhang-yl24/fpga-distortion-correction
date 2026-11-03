"""Run retained contracts against the closed tile8 proof/release adapters."""
from pathlib import Path
import sys
WORK=Path(__file__).resolve().parent;ROOT=WORK.parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT.parent/'.venv/Lib/site-packages')]
import pytest
raise SystemExit(pytest.main([*[str(p)for p in sorted((WORK/'physical-release-tests-a').glob('*.py'))],'-q',
    '--junitxml='+str(WORK/'physical-release-tests-a/results.xml')]))
