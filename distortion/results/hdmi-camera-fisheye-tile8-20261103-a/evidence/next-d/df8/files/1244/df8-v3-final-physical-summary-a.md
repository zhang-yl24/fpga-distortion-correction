# INDEX8 v3 physical sign-off summary

The complete saved physical proof passed. This summary independently reparsed all ten native timing tables with the exact frozen public summary parser and passed all_ten_pass. It did not rerun the full physical provider.

| Corner | Check | Worst slack (ns) | TNS (ns) | Failures | Clock rows | Worst clock pair(s) |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| slow | setup | 0.092 | 0.000 | 0 | 21 | ddrphy_sysclk to ddrphy_sysclk |
| slow | hold | 0.076 | 0.000 | 0 | 14 | ddrphy_sysclk to ddrphy_sysclk |
| slow | recovery | 1.019 | 0.000 | 0 | 6 | board27 to cfg_clk |
| slow | removal | 0.257 | 0.000 | 0 | 6 | board27 to cfg_clk |
| slow | mpw | 0.035 | 0.000 | 0 | 10 | phy_dq_clk_0; phy_dq_clk_1 |
| fast | setup | 1.606 | 0.000 | 0 | 21 | cfg_clk to board27 |
| fast | hold | 0.020 | 0.000 | 0 | 14 | ddrphy_sysclk to phy_dq_sysclk_0; ddrphy_sysclk to phy_dq_sysclk_1 |
| fast | recovery | 2.184 | 0.000 | 0 | 6 | board27 to cfg_clk |
| fast | removal | 0.030 | 0.000 | 0 | 6 | board27 to cfg_clk |
| fast | mpw | 0.035 | 0.000 | 0 | 10 | phy_dq_clk_0; phy_dq_clk_1 |

All 114 clock rows have zero failures and zero TNS. Native reports retain max_path=10000.

Full proof: 91,336,236 bytes; SHA256 903741272bd2529ca9bc72dec2a333d44a0b74760442f8705906c6d92adb6ada.
Fresh STA report: 840,398,979 bytes; SHA256 b5459c1c94bd42014b53d5c88d10959ffe0a82cb06b60cfc3d216614e7d9ddf2.

All 144 declared/routed/active ports are bound. CDC has 37,157 data scopes, 60 ordinary interstage records, and no missing or violating entries. Saved proof flags accept reset, protocol/source sampling, vendor DDR clock/reset, frame-boundary selection, profile, native warnings, graph/FF placement and unchanged routes.

The current generated-clock/PLL timing basis is 125 MHz (125,000,000 Hz), 8 ns in ddrphy_sysclk. This summary does not measure physical board frequency or FPS.

Actual application ADF SHA256: 2b6e662fb25cfb774a494743947c80325fd4796b423b3e0756a0f877117ae430. The full proof binds the fresh complete checks-scoped-v3-b-00 query. Recovery worker13392 completed public final_facts + final.verify, released its owned alias after native exit and exited0; root observation confirms P: free. Original worker43412/check PID2336 timed out and is not claimed successful. Its partial query remains failed and was not accepted.

Raw resource draft only: LUT 13875.0, FF 14397.0, DRM 43.5, APM 54.0; draft SHA256 7213392961edb3cf6083966fe4835f57568fb88fa03665bef36ab6f25c8cebe4. These counts are not yet bound to a generated bit or programmed board.

The 91MB proof and large native report stay local and are indexed by path/SHA256/size. The small JSON records concrete clock rows, proof/reference identity and interpretation limits. It can become a D attachment after the final publication chain is complete. No bit generation, programming, COM access, new FPS, analog MTBF, external AC or real-pixel acceptance is conferred here.
