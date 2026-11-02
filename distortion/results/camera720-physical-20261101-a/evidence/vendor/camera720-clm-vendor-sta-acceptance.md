# 720p physical CLM STA acceptance basis

Use the vendor's production physical sequential-boundary STA model, together with complete actual launch-qualified boundary coverage, final-candidate full STA and the complete structural source-FF/target-FF mapping. This is normal vendor-model reliance; no independent mathematical proof of the vendor's worst-over-internal-FF implementation is claimed or required.

The basis is concrete:

- PDS User Guide, physical 218 / printed 217 states that datapath-only includes source CLK→Q, combinational delay and receiving FF setup, and suppresses hold analysis for that path.
- PDS User Guide, physical 229 / printed 228 defines sequential data pins and sequential cells as valid destination selectors.
- Tcl Command User Guide, physical 81 / printed 80 gives an official packed `sum[4]/opit_0_AQ_perm.CIN` timing-query example.
- Actual final-candidate full STA and through-probe reports identify CLM CIN/I as sequential timing paths with library setup checks. Both requested packed launch outputs are separately observed at CIN12; this is not an invented combinational stopping point.
- Hash-bound audit `camera720-clm-vendor-sta-basis.json` preserves all 976 base logical relationships and checks every one of the 640 merged physical queries: all grouped target FFs share one actual physical site, one CK net and identical FF primitive/parameters. Every query retains the actual logical target list and structural boundary dependency.

Allowed final claim **after actual coverage closes**: all inventoried logical relationships are represented by complete, valid physical sequential-boundary timing checks under the vendor STA model. Ordinary paths still require setup and hold in both corners; crossing paths retain the explicit datapath-only maximum/hold-suppression policy. Full STA and all other release conditions remain independently required.

Do not claim independently enumerated timing results for each internal FF or proof of a specific internal aggregation formula. `PhysicalTimingAggregationProved=false` and `IndependentWorstOverInternalFFFormulaClaimed=false` document that limit; they do not negate the normal vendor STA acceptance basis. This note/audit alone is not timing acceptance and authorizes no hardware action. No extra PDS probe is required solely to rediscover the documented physical timing abstraction.

Artifacts:

- Audit SHA256: `7507a8262d7fa61ccf2334e05e5d282cc1b005f86f41c607343f8728f193010b`.
- Actual physical mapping B SHA256: `84c66dffc42fa4b84fc32e92dc0a93f38e5d239972096a72634905873f1ddf23`.
- Manual extract SHA256: `1d86f0682e8df259efd30000daf3660c7ccc544b382a3cba4e4fb6d4b1096524`.
- Exact PDS manual: `D:/pango/PDS_2023.2/doc/Pango_Design_Suite_User_Guide.pdf`, SHA256 `4b49b329809fa5dd4998213e715c2996c92cba26fbed74a8b9f43cb711943bb1`.
- Exact Tcl manual: `D:/pango/PDS_2023.2/doc/Tcl_Command_User_Guide.pdf`, SHA256 `7be74cf2d0fba752cc7016a47b994d9bfb05805f4c7b19fb4d15266033de9ba4`.
- Supplementary Timing Analyzer manual: `D:/pango/PDS_2023.2/doc/Timing_Analyzer_User_Guide.pdf`, SHA256 `9d04d214d74f95348ce292b3c244e6ee880dd7095014209db243f8b8c1b2b420`.
- Through receipt SHA256: `f449ee328da1fd59d78a83c1ccc5d1952f5ea2b633c8aba3aeb46bd43d8b404e`.

The exact canonical external manual files may be allowlisted by path plus digest; this evidence does not justify allowing their directory generally.
