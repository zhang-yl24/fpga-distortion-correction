# 720p preparation and executor review — 2026-11-01

Status: review PASS for independent offline compile/map/route/STA; 19 CPU tests passed with zero failures/errors. No EDA or hardware was launched by this reviewer.

- 111 manifest sources, 112 compiled files including RCF, 31 explicit designs (30 Verilog + one DDR IDF). The 74 IDF-expanded files are copied but not explicitly added again. Headers are not compiled as design units.
- All locally imported Python helpers are bound by InputSHA256. build-a has 138 watched inputs; the original prepared compiled paths have maximum length 244 characters.
- Deterministic validation recomputes source closure, exact include rewrites, Tcl, command, native tool hash, inventory and all copied bytes before execution. Tcl contains only compile/synthesize/map/route/STA and the pre-STA snapshot. It has no programming or bitstream command.
- Plan flags explicitly deny timing, optical-correction, bitstream and hardware acceptance. Success of the native process is kept separate from timing acceptance.
- Control test runs the actual board top/warmup against six explicitly bound status stubs. Its passed report checks eight startup cases, seven runtime faults, 17 resets, LEDs and readiness chatter. It does not execute the sensor/frontend body, physical input delay, DDR transactions or real image pipeline; separate sensor/capture/output tests remain necessary.
- Follow-up observation: parent corrected the inherited Headers metadata to enumerate the actual new source closure; old build-a is therefore stale for execution. Use a freshly prepared plan such as build-b/run-a.

Non-blocking executor evidence limitation: Cleanup.Complete directly proves only the launched parent is gone. On a still-live parent, timeout cleanup invokes taskkill on that PID tree. A parent that exits before cleanup is not followed by an orphan-child inventory. Therefore do not use that field alone as proof that every owned native child exited; verify the process inventory after native execution. This is inherited behavior, not a new physical acceptance claim.

New tests: distortion/tests/test_camera720_output_prepare.py. All file mutations are private copies under a verified distortion/work/camera720-output scratch root; Popen is mocked and the test executable is inert. The first test-fixture layout exceeded Windows MAX_PATH and was shortened. One path-escape assertion was then corrected because the shortened test PROJECT equals the scratch root. No production file was modified by the reviewer.

Final regression: 19 tests passed, zero failures/errors, 63.525 seconds. The unchanged VGA predecessor is verified once using its real validator and snapshotted as the unit-test dependency; new 720p source files, recipe, native-tool binding, compiled bytes and exact Tcl are still re-read and validated in each case. Mocked successful execution never sets timing/hardware acceptance; timeout calls only the owned-process cleanup hook. The two earlier fixture-only issues were corrected and the entire final 19-test suite then passed.

Reproduce:

```powershell
.venv/Scripts/python.exe -B -X utf8 -m unittest discover -s distortion/tests -p test_camera720_output_prepare.py -v
```

Evidence: `work/camera720-prepare-tests-20261101.json` and matching `.log`.


Reviewed file SHA256 (final source state):

- `tools/prepare_camera720_output.py`: `dda5db3443830e1da06952e5f8c3c747b12730c7798f8ab1b43df7217a161376`
- `tools/run_camera720_output_diagnostic.py`: `f508edf357c3560d0ebf31bbe6e96f1f6cf07ef35bbc4a604594b64438e04d83`
- `tools/run_camera720_control_sim.py`: `4bb162be03012671cb09e09ca7ff6159e5bedd1785657056144729c5cae8e564`
- `tests/test_camera720_output_prepare.py`: `28ca1e0f198bd26773e685cadc3680686b0d10f597ddee8fe03644f5022f0fdc`
- `board/camera720-output-sources.json`: `a4f6257c8614b43ebe8d09beef764a8d0f06c31d2d474755b8e5865a55009be5`
