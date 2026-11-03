# Native PDS FIFO synchronizer preservation

The new `rtl/video_async_fifo.v` overlay replaces the ignored `async_reg`
attribute on the reset chains and both Gray-pointer synchronization banks with:

```verilog
(* PAP_ASYNC_REG=1, syn_srlstyle="registers" *)
```

Only those three declarations and an explanatory comment change. A token
comparison after removing attributes/comments proves that all functional RTL,
ports and cycle behavior match the FIFO used in the passing implementation-f
system regression. The original `distortion/` FIFO and sealed C package are
unchanged. No clock groups, false paths or CDC timing exceptions are added.

Overlay SHA-256:
`143400186f0549f30007e64cd7dbcc6b82395099f7c2dd85e92725cb06943a16`.
Original/F-system FIFO SHA-256:
`140e97b7de1c3718d75f6bd0c657c9df602d724c5162a26386b053deafa07e36`.

The physical-e audit found all 34 two-stage Gray chains converted into
`gopSRL2` after device mapping, despite their synthesis netlist retaining DFFs.
The compiler explicitly rejected `async_reg`, and its CDC report classified
the chains as synchronized without the recognized property. Those findings
motivated the native-property probe; synthesis output alone was insufficient.

The isolated `fifo_cdc_probe` instantiates pointer widths seven and ten, matching
the capture/display FIFOs. Eight-bit payloads keep the probe small. PDS 2025.2
ADS build 211867 completed compile, synthesis, device map, place, route and
timing reporting on PG2L100H-6 FBG676. The verification checks the final
`fifo_cdc_probe_route_optimize.netlist`:

- All 68 Gray synchronizer registers are separately named `gopQ` instances.
- Each local reset synchronizer retains two independent `gopQ` stages. Because
  both probe instances use the same clocks and common reset, synthesis shares
  the two identical reset chains: four physical reset FFs serve eight logical
  declarations. The second-stage connections into `display_size` are verified.
- No SRL primitive remains in the probe netlist.
- All 72 physical synchronizer/reset FFs carry recognized
  `PAP_ASYNC_REG="TRUE"` and `PAP_SRL_STYLE="registers"` in the synthesis netlist.
- The eight internal Gray CDC groups are CDC-3/CDC-6 with ASYNC_REG, category
  Safe. External probe IO is unconstrained and is outside this structural check.

`syn_preserve` was unnecessary for the verified two-stage structure. The exact
per-register map, shared-reset bindings, source hashes and implementation-f
functional-token comparison are in `cdc-fifo-native/probe-verification.json`.
The directory also preserves native probe source/Tcl, compilation logs,
synthesized Verilog, mapped netlist and CDC report. Absolute work paths in the
probe Tcl and helper record the original run; update them when replaying it.

This verifies that the native properties survive device mapping and routing in
the probe. The complete design still needs its own mapped-chain audit and
per-bit Gray source-to-first-stage maximum-delay/skew bounds. The existing
full-system functional regression does not establish metastability margin.
