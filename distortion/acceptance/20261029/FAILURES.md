# Preserved failures and unmeasured scope

These are separate evidence layers, never rewritten as a first-pass success:

| Layer | Actual result |
|---|---|
| Realframe directed A/B | Passed targeted RTL; B adds legitimate first-query waiting counterexample |
| Realframe native A | Compile failed on bench literal syntax; no simulation |
| Realframe native B | Native tool stages completed; checker fatal before accepted first query; CLI1 |
| Realframe native C | CLI0,2073600 pixels,actual scan CRC2aee1c42; DUT/golden not changed to accommodate checker |
| Board control | RTL CLI0,9.7576996s,79cycles; limited control unit coverage |
| Board frontend | compile/synth/map each successful once; surrounding CLI1 due unsupported Tcl clock |
| First mapped-DB PNR | CLI1,Place-0006; generated PCF not consumed |
| Authorized PCF-only PNR |145/145 commands consumed,two gates/CPD fixed,Place-0006 absent,native0 |
| PNR wrapper | HOST_OR_AUDIT_FAILED/CLI1 due optional CPD slot parser; raw record retained |
| Independent native exit/post-assessment | Windows owned-process exit0 and post-assessment PASS; no PNR rerun to repair receipt |
| Final saved DB STA | UNRUN_DEADLINE; no final independent clock-pair/CDC/coverage pass |

The PNR built-in summary still reports245 recovery checks failing per corner (do not add corners into a unique-FF count) and3 cross-SRB paths below tool200ps hold margin (example fast156ps). MPW empty rows are not PASS. Resource fitting/PNR0 does not release hardware.

Whole-system active-frame reset,new-angle/Gamma native throughput,continuous real footage,physical HDMI/DDR/CDC,external latency,long stability and formal calibration/optical acceptance remain unmeasured. Old synthetic three-frame ABA original3600s CLI1/false and later5400s authorized functional assessment remain distinct; this delivery never converts the original receipt to true.
