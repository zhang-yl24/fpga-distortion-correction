# Real system contention regression

Snapshot scope: the receipts below precede the registered-metadata cache and
the later writer/output timing repairs. They use cache SHA-256
`76e273555590d7ed81655098df4eed65033de5814ad3e30a7af266811c8264fb`.
The final combined RTL needs a new system run after those repairs are frozen.

Both tile configurations, 8×8 and 32×8, passed Vivado XSim 2017.4 with the real
64×64 system. The DUT includes capture CDC, three source slots, the descriptor
queue, two mapper/cache/writer lanes, both levels of DDR arbitration, the full
registered read-return bundle, display reader/FIFO, and pixel scanout. No engine
stub, internal force, or prefilled source image is used.

The core clock is 125 MHz. Input and output clocks are 148.5 MHz, generated with
integer-picosecond remainder accumulation and distinct phase. The model permits
one shared read or write data beat per core cycle, with variable read latency,
AW/AR/W stalls, response gaps and refresh bubbles. Input raster is 80×72 and
output raster is 96×96; their intentionally different scaled frame periods
exercise all source slots and descriptor backpressure. These results establish
functional integrity and ownership under this model. Native 1080p60 throughput,
DDR-controller behavior, physical timing and board stability require separate
evidence.

Each configuration passes two reset epochs and checks:

- 34 accepted source frames, 33 published results, 32 uniquely displayed frames
  (12 raw and 20 corrected), plus 5 repeated displays.
- 139,264 source pixels checked on DDR writes and again in committed memory;
  135,168 result pixels checked on writes and again at publication;
  151,552 displayed pixels checked against independent expected RGB values.
- Source CRC, per-frame result CRC including the two-lane combination, and an
  independently accumulated displayed CRC. The external `cfg_corrected` value
  is captured on source acceptance and remains the expected mode for that frame.
- All three source slots reused at least five times per epoch; simultaneous
  source reservations, capture/result write competition, display/sample read
  competition, read/write service competition, and all backpressure counters
  are nonzero.
- An asserted common reset during actual processing with a DDR transaction
  outstanding. Memory retains its contents across reset; the second epoch uses
  different image textures and reset frame IDs, detecting stale data or state.
- Zero underflow, checksum mismatch or malformed-input-frame drops. Each epoch
  deliberately encounters 8 input frames without a source reservation; these
  are whole-frame skips, tracked separately from accepted or unique frames.

Before the first reset, the initial stream is fully drained and repeated. Two
additional inputs then create the interrupted transaction: one published frame
has not yet been displayed and one processing frame is cancelled by common
reset. The final epoch drains every accepted frame and verifies repeated display.

The corrected reference uses the released C profile at the actual test size,
including scaled pixel centers/focal lengths, integer overflow/sentinel rules,
per-neighbor black borders, RGB565 expansion, one final bilinear rounding and
RGB565 quantization. Cache/mapper directed tests separately cover corner cases
that this small calibrated image does not reach.

Receipts and tool logs are in `system-contention-8/` and
`system-contention-32/`. Each receipt records the compiled source hashes,
candidate snapshot identity, reference hashes, exact commands and per-epoch
coverage. Final testbench SHA-256:
`992da1dd4b24464a616dcda030d94e2f11923e5446f72bff5165cad95e57649f`.

Reproduce from this package's `tools` directory with Python plus NumPy:

```powershell
python run_system_contention.py --work D:/f60-work/new-system-8 --tile-width 8
python run_system_contention.py --work D:/f60-work/new-system-32 --tile-width 32
```

Each work directory must be new. Override `--vivado-bin` when Vivado is installed
outside `D:/Vicado/Vivado/2017.4/bin`.
