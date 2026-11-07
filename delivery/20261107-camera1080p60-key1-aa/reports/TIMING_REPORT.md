# AA routed timing report

These are actual independent post-route STA summaries, after hold optimization. All 12 summaries have nonzero endpoint coverage, zero failing endpoints and zero reported total negative slack. These statements apply to the analyzed internal timing model and existing constraints.

| Check | Slow minimum | Fast minimum | Unit |
|---|---:|---:|---|
| Setup | +0.003 | +2.535 | ns |
| Hold | +0.062 | +0.044 | ns |
| Recovery | +1.600 | +3.856 | ns |
| Removal | +0.312 | +0.214 | ns |
| Minimum pulse width | +0.035 | +0.035 | raw report value; header does not specify unit |
| Skew | +0.223 | +0.240 | ns |

The 12 original XML summary files use the vendor `.db` extension. The accompanying text contains both actual slow setup paths below 0.010 ns, including the +3 ps and +5 ps endpoints, full printed numerical path tables, RTL hierarchy, and the existing multicycle-2 exception at `board1080-diagnostic.fdc:817`.

The +3 ps path runs from `ddrphy_sysclk` to `phy_dq_sysclk_0`, through DDR PHY command/address logic. Data delay is 6.349 ns: logic 0.643 ns and routing 5.706 ns (89.9%), with two logic levels and maximum data-path fanout 63. Printed arrival/required times are 11.960/11.963 ns. The 0.001 ns display step is not a statement of physical or model accuracy; 3 ps provides very little reported margin. The +44 ps fast hold summary does not identify a unique endpoint in these selected detailed reports.

Final post-hold-optimization resource counts shared by the utilization reports are 30,652 physical LUTs, 26,452 flip-flops, 582 constant LUTs, 30 DRM grid units (4 DRM18K and 28 DRM36K operations), 37 APM grid units (70 operations), and 145 IOs. The two final utilization representations disagree on CLMA/CLMS: text 6,118/2,477; XML 6,126/2,482. The cause is unresolved; no unique final CLM count is claimed.

Limits: 11 clocks were reviewed and no-clock count was zero. The reports still list 56 entries without input delay and 111 without output delay (134 unique ports, with bidirectional overlap). External device/PCB min/max delay budgets, CDC correctness, physical reset release and the three asynchronous clock-group exceptions have not been signed off. Nineteen reported HDMI input registers and matching 145 pin assignments do not establish external IO timing. Standalone exception tables were absent from the original final STA inventory; the selected setup-path supplement explicitly shows the existing multicycle exception, not a complete exception audit. No board test, hardware frequency measurement, or hardware/PVT qualification has been performed.
