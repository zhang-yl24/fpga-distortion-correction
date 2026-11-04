# V4 first-pass reuse and camera observation

This child records actual native bit generation, fresh STA acceptance, volatile SRAM programming and one independently decoded 30-second camera observation.

Measured unique presented frames/s: 30.000652. Scan refreshes are a separate counter; the exact rate dictionary and measured duration are in actual-summary.json.

Requested 30 FPS counter criterion: MET.

Only the recorded 30-second observation is claimed. No 600-second stability test or visual pixel acceptance is claimed by this package. The comparison report states whether the observed values satisfy its 30 FPS criterion; the goal is not assumed.

The completed first physical proof is reused at the user’s request. Original release worker 24952 was also interrupted with actual exit -1 before hardware access when it repeated already completed bit verification. A separately recorded continuation reused the successful bit verification and performed real SRAM programming and the camera observation. Its redundant second verification was interrupted with actual worker exit -1. The first-pass proof and interruption records remain separate. Earlier disk-full exit1, unknown wrapper exit and export timeout remain preserved.

The bit provider performed one full source SHA pass, then reused exact saved file-identity witnesses for unchanged inputs. Fresh bit-stage STA, exceptions, bit identity and real device/DONE programming checks remained active. No Flash was written.

The simulation accepted four frames by an explicit testbench cap and observed three new-frame intervals near 33.333 ms. This is finite cadence evidence, not a sustained 30 FPS claim over all sixteen source frames.

The package includes selected evidence bytes and the actual sbit. Large historical native artifacts remain exact references in native-reference-index.json and original receipts; they are not repackaged as a complete native build archive.

The original 1,063 research payloads and prior deliveries are outside this append-only child. Run python verify_saved_bundle_a.py --bundle . to verify the packaged bytes only.
