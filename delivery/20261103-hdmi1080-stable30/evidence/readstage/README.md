# DDR read-return register boundary

`sources/ddr_read_return_register.v` inserts one clock of latency into the complete unbackpressurable DDR read bundle: 256-bit data, valid, last and 4-bit ID. It observes the existing raw `arvalid/arready` handshake without changing AR behavior.

## Integration

Instantiate the module before the complete video system/read arbiter. Connect raw DDR read outputs to `in_r*`, existing raw AR handshake to `arvalid/arready`, and registered outputs to the system `r*` inputs. Use the same synchronous active-low transaction reset as arbiter and clients. Append the exact source bytes to the top compilation unit if the 49-design closure must remain unchanged.

Connect `protocol_fault` into the system external-fault and top failure status. Preserve `fault_code` for diagnosis: `0x40` means a raw return without any outstanding/raw same-edge AR; `0x41` means a second accepted raw AR before the current transaction's final raw beat. Neither error resets the transaction domain automatically. Once a protocol fault occurs the module suppresses further valid delivery until explicit reset; the system must keep its normal sticky failure/quarantine policy.

All payload registers run without reset/enable muxes; `out_rvalid` qualifies every field. Reset clears valid, raw ownership and sticky fault. The parent reset must cover DDR, stage, arbiter and clients together. A one-bit guard cannot identify a stale physical DDR beat after an incomplete reset that happens to coincide with a newly accepted address; complete transaction-domain reset remains required.

The raw owner guard is essential: delaying only R could turn an unsolicited response observed while idle into a seemingly legitimate first response on the next AR handshake. This implementation records the raw-time violation before adding latency and suppresses that beat. Legitimate same-edge AR/first return, including one-beat bursts, are allowed. Continuous responses are captured every clock; the arbiter retains its owner until the delayed final beat, so legitimate return data never changes owner.

RID and RLAST pass unchanged. The existing arbiter still diagnoses bad metadata as fault `0x03`. For an early RLAST followed by further DDR beats, the stage can additionally diagnose those trailing beats as unsolicited `0x40`; retain both fault sources, or give an existing arbiter metadata fault precedence when presenting one code.

## Verification

Actual frozen `ddr_read_arbiter.v` is byte-bound (SHA256 `59283dd5d5d292cf8dd6d1bff51b565c13357ce94bdead0d467421604c5f72be`). Three simulator tests use that source:

- Adapted original regression: simultaneous two clients, 1/2/8/16-beat bursts, exclusive response routing, fairness, urgency, address/response stalls, malformed RID/RLAST, timeout, unsolicited data and reset recovery.
- Expanded integration: 24 raw same-edge AR/first responses with 162 checked beats in continuous mode (138 consecutive beat pairs), another 24 same-edge responses with 162 checked gapped beats, missing final RLAST, reset during active returns, and unsolicited data before a next AR. All data, last and ID are checked at the real client outputs.
- Independent guard: 11 directed checks including reset with raw and staged valid, same-edge AR/one-beat completion, all metadata capture, sticky unsolicited error across a later AR, overlapping raw requests and final-old-beat/new-request ownership conservation.

Run `python -B run_tests.py --work <fresh-output-directory>` with Vivado XSim. `--vivado-bin` overrides the default installed path. Final source-bound report is `validated/results.json`; previous run directories retain development test results. No hardware or physical implementation was accessed.

## Performance scope

This is a timing-isolation change. It adds one return clock and can add one turnaround cycle per serialized burst. It captures one beat every clock with no response backpressure. Full geometry-engine and board scheduling tests must measure the resulting frame cycles; no board FPS or post-route timing claim is made here.
