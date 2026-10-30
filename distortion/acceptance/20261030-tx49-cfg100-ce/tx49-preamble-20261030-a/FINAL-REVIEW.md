# Final independent readback

Sealed delivery: delivery-receipt.json (e74497abfc2796cd340951b1cafdfbafcf4aca0b0abde7cefa040ec68418fbbe). Original receipt and handoff remain unchanged.

Independent actual-run review: a-wire-review/actual-run-review.json. Both epochs: RX_DONE→first TX START2601ns; final TX STOP→DONE2499ns; DONE→first resumed RX START2501ns.36 original run-result evidence hashes and18 directly classified simulation/control inputs matched; full root admission also protects421 original inputs.

Bench v2 clarification: after normalizing LF/CRLF, only the exact monitor instance is moved below declarations. The new text file also uses CRLF, so it is NOT byte-identical to v1 with only a block move. Both versions, first compiler failure, and exact file hashes remain preserved. DUT/guard/stimulus/assertions unchanged by this repair.

Scope remains real RTL wire protocol with SYNTHETIC slave behavior; no physical I2C/PC-HDMI/STA/hardware acceptance. Next board compile Tcl is prepared only. All formal/hardware gates false; no PDS, board, Git, GUI or power-policy action in this milestone.
