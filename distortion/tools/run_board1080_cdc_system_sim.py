"""Offline-only reproduction of the CDC-reset System; no device or PDS access.

The same-source small run must pass before a new native run. Frozen historical
receipts are not rewritten or reused to approve a relocated/new source closure.
Create a fresh workdir under distortion/build/board1080-cdc-reproduction first.
"""
from pathlib import Path
import run_board1080_system_sim as system
ROOT=Path(__file__).resolve().parents[1]
system.BASE=ROOT/'build/board1080-cdc-reproduction'
system.COMPILE=tuple('rtl/experimental/hdmi1080_video_system_cdc_reset.v'
    if n=='rtl/experimental/hdmi1080_video_system.v' else n for n in system.COMPILE)
system.HELPERS=(*system.HELPERS,'tools/run_board1080_cdc_system_sim.py')
if __name__=='__main__':
    raise SystemExit(system.main())
