# Current720 retained-source sensor port — 2026-11-01

This is an independent offline preparation for the user's 1280×720 development
phase. No existing VGA or historical 720p source, ROM, manifest, helper or board
state was modified. No PDS or hardware tool was run.

## Added production inputs

- `rtl/experimental/ov5640_current720_init.v`: byte-exact retained initializer
  with only its module name and machine-absolute include path changed. Include
  is now `board/ov5640_rgb565_720_commands.vh`; add the `distortion` root to the
  compiler include search path.
- `rtl/experimental/ov5640_current720_frontend.v`: uses the unchanged
  `dvp_mode_admission_monitor`, with exact 2560 bytes × 720 lines. It requires
  two complete good frames before `raw_authorize`. Default startup grace is
  27,000,000 ref cycles (one second at 27 MHz) to the first complete good frame;
  this is a timeout allowance, not a mandatory one-second admission delay.
  Initialization and monitor diagnostic outputs are exposed.
- `tools/prepare_camera720_sensor.py`: checks four fixed retained-source hashes,
  all 403 ROM words against the retained manifest, and exact initializer edits.
  It explicitly does not reconstruct the missing historical generator proposal.

Caller obligations remain explicit: VS/HREF are already logical active-high;
the board caller binds the physical inversions and RGB565 low-byte-first pixel
packing. `raw_authorize` gates new transactions and must not reset transactions
already accepted by DDR or UART. This frontend stores no pixels. Physical CDC,
timing constraints and sensor behavior still require integration validation.

## Verification completed

`tests/test_camera720_sensor.py`: six CPU tests passed, including four retained
input tamper subcases, initializer logic drift and absolute-include rejection,
and verification without the historical build tree.

`tools/run_camera720_sensor_sim.py` is self-contained and writes to a fresh
directory beneath `distortion/work`. It needs only Vivado simulation binaries,
using `--vivado-bin`, `FPGA_VIVADO_BIN`, or `team-config.local.json`. It imports
no historical builder and invokes no PDS, UART or JTAG tool.

Full run passed:
`work/camera720-sensor-sim-20261101T041857527800Z-0b72f2/camera720-sensor-simulation.json`.

- Six real `reg16_i2c` open-drain line-model cases: complete 403-action sequence
  and unique wake, verified data NACK recovery, pad read-address NACK, default
  clock mismatch, geometry preflight mismatch, post-wake read NACK, and full-byte
  rejection despite a masked RMW match (some checks share the success case).
- Synthetic PCLK approximately 42 MHz and 47.25 MHz: registers alone do not
  authorize; one complete good frame does not authorize; two complete
  2560-byte × 720-line frames authorize; PCLK stop revokes admission; restarting
  PCLK does not clear the sticky fault.
- A 2558-byte first line causes fault `0x12` and prevents admission while
  configuration remains complete.
- Source hashes were unchanged throughout the run. All log and transaction-trace
  hashes are recorded in the JSON report.

Commands from the repository root:

```powershell
.venv/Scripts/python.exe -B -X utf8 distortion/tools/prepare_camera720_sensor.py
.venv/Scripts/python.exe -B -X utf8 -m unittest discover -s distortion/tests -p test_camera720_sensor.py -v
.venv/Scripts/python.exe -B -X utf8 distortion/tools/run_camera720_sensor_sim.py --maximum-seconds 900
```

The retained nominal 24 MHz XVCLK model implies approximately 42 MHz PCLK and
15 frames/s. These are model values, not measured performance. The new tests
verify digital sequencing and timing admission only: no pixel-content/DDR
transport, current-lens 720p calibration, board download or visual acceptance
is claimed.
