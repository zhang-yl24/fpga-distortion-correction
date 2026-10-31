# MS7200 stable-ready counterexample

Native Vivado 2017.4 compile, elaboration and simulation completed with exit 0.
The unchanged current MS7200 source was compiled directly from the workspace;
`counterexample-result.json` binds source, testbench, runner and raw evidence.
`reference-equivalence.json` independently confirms that the selected controller
differs from the vendor source only in its EDID bytes.

The transaction stub returns 0x02 for register 0x209E from its first read. After
64 such reads, 300 initial writes have completed but no final setting write has
started and init_over remains 0. Both previous and current sampled readiness
fields are 2'b10, so the original 00-to-10 edge predicate never passes. Without
resetting the controller, returning 0x00 for two reads and then 0x02 completes all
seven setting writes and raises init_over. The conventional initial-00-then-02
stimulus also completes.

This is a bounded transaction-level controller counterexample. It does not
emulate electrical I2C, prove what register 0x209E means on real silicon, or by
itself establish the complete cause of the current board observation. No shared
RTL/helper was edited, no bitstream was generated and no hardware was accessed.

For a fresh rerun, copy `run.py` and `tb_ms7200_ready_level.sv` into a new writable
directory and run that copy of `run.py` with the workspace .venv Python. The
runner reads the existing workspace tool configuration. Preserve the original
directory: the result writer deliberately refuses to overwrite its receipt.
