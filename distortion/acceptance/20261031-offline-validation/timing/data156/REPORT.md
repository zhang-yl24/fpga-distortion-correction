# Data156 physical closure: bounded scope and complete capture model audit

Current final ADF `e94ae54311ea4e8aa4c2f416ae41ca1a208341b61e248c153646af95cea9c9cb`. Source synthesis `215ee759ccab2f272f5072ba800dcd79e417347b91f282c50489f0fdf7f17ce5`. Map/PNR/independent STA all native exit0; total190.946s within630s;22 owned processes exited, Job closed, ActiveProcesses=0, all frozen inputs unchanged.

312 two-corner max paths all explicitly retain sequential capture setup; worst+5.652ns, snapshot184 worst+17.272ns. Gray128 and snapshot184 are unique corresponding bit pairs. Six Gray skew groups/256 branch rows are complete.

324 internal checks worst+0.132ns;736 capture CE/synchronous-RS checks worst+0.281ns;368 capture-to-apply checks worst+0.161ns.

Fresh capture types:{'gopQ': 92}; data ports:{'D': 92}. Every bit is bound to its actual data endpoint, macro CLK/CE/RS and registered Q/TCO into its corresponding apply register. For LUT6L5Q the registered output must beL5Q, never combinationalL6.312 max formulas check required=max_delay+signed aggregate setup, slack=required-arrival. Datapath_only omits clock propagation in exception text, so companion normal CE/RS paths independently identify the same captureCLK. No bare I-arrival-only closure is claimed. Separate hidden internal D characterization is not exposed; this is PDS native sequential-macro evidence.

All32 asynchronous reset checks remain, including8 negative records. Key four p-reset recovery:{'Slow': [-1.765, -1.765, -1.765, -1.765], 'Fast': [-1.13, -1.13, -1.13, -1.13]}. All44 control-first checks remain unexempted. Normal negative counts:{'Slow/max': 15, 'Slow/min': 10, 'Fast/max': 15, 'Fast/min': 10}. These unresolved negatives are not hidden by data bounds.

R/2 andP/2 remain engineering targets under the original guarded R0..R4 settled-data/Gray epoch contracts, not measured jitter or MTBF. Only incoming bounded data traditional holds are replaced; capture controls, later stages and reset are preserved. This is a noDDR diagnostic candidate and cannot be inherited by the full CE/DDR video main design. No control false_path, permit, production change, seed sweep, bitstream, board action or global/hardware signoff occurred.

Evidence: MAX312/INTERNAL324/CAPTURE_CONTROL736/CAPTURE_TO_APPLY368/RESET_ALL32/CONTROL_FIRST44/SKEW256 CSVs, CAPTURE_BINDING92.json, SKEW6.json, execution and native report identities in EVIDENCE_MANIFEST.json.
