# Native timing: physical-h

BuildID `11037003`, source `fe756ccb51cbbf1ea30a337eec0c22d5419fd4cdb5cd34dad2097bcde880e44d`. Diagnostic scope; external IO, CDC and reset acceptance remain pending.

| Corner/check | Launch | Capture | Worst slack (ns) | Failing endpoints | Domain status |
| --- | --- | --- | ---: | ---: | --- |
| slow_setup | ddrphy_sysclk | input_pixel | -5.274 | 635 | independent_clock_domains_cdc_review_required |
| slow_setup | input_pixel | ddrphy_sysclk | -4.701 | 306 | independent_clock_domains_cdc_review_required |
| slow_setup | board27 | ddrphy_sysclk | -4.559 | 188 | independent_clock_domains_cdc_review_required |
| slow_setup | ddrphy_sysclk | board27 | -3.984 | 3 | independent_clock_domains_cdc_review_required |
| slow_setup | ddrphy_sysclk | ddrphy_sysclk | -1.977 | 2054 | same_clock |
| slow_setup | input_pixel | input_pixel | -1.872 | 688 | same_clock |
| slow_setup | input_pixel | board27 | -1.010 | 2 | independent_clock_domains_cdc_review_required |
| slow_setup | ddrphy_sysclk | phy_dq_sysclk_0 | 0.003 | 0 | core_to_divided_phy_timed |
| slow_setup | cfg_clk | board27 | 0.089 | 0 | related_clock_domains_timed |
| slow_setup | ddrphy_sysclk | phy_dq_sysclk_1 | 0.250 | 0 | core_to_divided_phy_timed |
| slow_setup | phy_dq_sysclk_1 | ddrphy_sysclk | 2.431 | 0 | core_to_divided_phy_timed |
| slow_setup | phy_dq_sysclk_0 | ddrphy_sysclk | 3.668 | 0 | core_to_divided_phy_timed |
| slow_setup | rst_clk | rst_clk | 4.234 | 0 | same_clock |
| slow_setup | board27 | board27 | 29.899 | 0 | same_clock |
| slow_setup | cfg_clk | cfg_clk | 94.116 | 0 | same_clock |
| slow_hold | input_pixel | ddrphy_sysclk | -2.179 | 9 | independent_clock_domains_cdc_review_required |
| slow_hold | board27 | ddrphy_sysclk | -1.807 | 182 | independent_clock_domains_cdc_review_required |
| slow_hold | input_pixel | board27 | -0.223 | 1 | independent_clock_domains_cdc_review_required |
| slow_hold | ddrphy_sysclk | ddrphy_sysclk | 0.021 | 0 | same_clock |
| slow_hold | input_pixel | input_pixel | 0.145 | 0 | same_clock |
| slow_hold | rst_clk | rst_clk | 0.210 | 0 | same_clock |
| slow_hold | cfg_clk | cfg_clk | 0.231 | 0 | same_clock |
| slow_hold | board27 | board27 | 0.299 | 0 | same_clock |
| slow_hold | ddrphy_sysclk | phy_dq_sysclk_0 | 0.368 | 0 | core_to_divided_phy_timed |
| slow_hold | cfg_clk | board27 | 0.371 | 0 | related_clock_domains_timed |
| slow_hold | ddrphy_sysclk | phy_dq_sysclk_1 | 0.396 | 0 | core_to_divided_phy_timed |
| slow_hold | phy_dq_sysclk_1 | ddrphy_sysclk | 0.444 | 0 | core_to_divided_phy_timed |
| slow_hold | ddrphy_sysclk | board27 | 0.618 | 0 | independent_clock_domains_cdc_review_required |
| slow_hold | phy_dq_sysclk_0 | ddrphy_sysclk | 0.748 | 0 | core_to_divided_phy_timed |
| slow_hold | ddrphy_sysclk | input_pixel | 0.778 | 0 | independent_clock_domains_cdc_review_required |
| slow_recovery | board27 | ddrphy_sysclk | -3.421 | 852 | independent_clock_domains_cdc_review_required |
| slow_recovery | board27 | input_pixel | -2.263 | 505 | independent_clock_domains_cdc_review_required |
| slow_recovery | board27 | cfg_clk | -0.953 | 7 | related_clock_domains_timed |
| slow_recovery | ddrphy_sysclk | ddrphy_sysclk | 2.126 | 0 | same_clock |
| slow_recovery | rst_clk | rst_clk | 5.612 | 0 | same_clock |
| slow_recovery | board27 | board27 | 31.376 | 0 | same_clock |
| slow_recovery | cfg_clk | cfg_clk | 96.472 | 0 | same_clock |
| slow_removal | board27 | ddrphy_sysclk | -1.762 | 852 | independent_clock_domains_cdc_review_required |
| slow_removal | ddrphy_sysclk | ddrphy_sysclk | 0.348 | 0 | same_clock |
| slow_removal | cfg_clk | cfg_clk | 0.391 | 0 | same_clock |
| slow_removal | rst_clk | rst_clk | 0.414 | 0 | same_clock |
| slow_removal | board27 | input_pixel | 0.431 | 0 | independent_clock_domains_cdc_review_required |
| slow_removal | board27 | cfg_clk | 0.537 | 0 | related_clock_domains_timed |
| slow_removal | board27 | board27 | 0.657 | 0 | same_clock |
| slow_mpw | phy_dq_clk_1 | phy_dq_clk_1 | 0.035 | 0 | same_clock |
| slow_mpw | phy_dq_clk_0 | phy_dq_clk_0 | 0.035 | 0 | same_clock |
| slow_mpw | phy_dq_sysclk_0 | phy_dq_sysclk_0 | 1.850 | 0 | same_clock |
| slow_mpw | input_pixel | input_pixel | 2.373 | 0 | same_clock |
| slow_mpw | phy_dq_sysclk_1 | phy_dq_sysclk_1 | 2.400 | 0 | same_clock |
| slow_mpw | ddrphy_sysclk | ddrphy_sysclk | 2.655 | 0 | same_clock |
| slow_mpw | rst_clk | rst_clk | 3.800 | 0 | same_clock |
| slow_mpw | board27 | board27 | 18.318 | 0 | same_clock |
| slow_mpw | cfg_clk | cfg_clk | 49.038 | 0 | same_clock |
| slow_skew |  |  | 0.223 | 0 | external_or_unclocked_requires_review |
| slow_skew |  |  | 0.223 | 0 | external_or_unclocked_requires_review |
| slow_skew |  |  | 0.397 | 0 | external_or_unclocked_requires_review |
| slow_skew |  |  | 0.397 | 0 | external_or_unclocked_requires_review |
| fast_setup | ddrphy_sysclk | input_pixel | -3.566 | 635 | independent_clock_domains_cdc_review_required |
| fast_setup | ddrphy_sysclk | board27 | -3.178 | 3 | independent_clock_domains_cdc_review_required |
| fast_setup | board27 | ddrphy_sysclk | -2.318 | 187 | independent_clock_domains_cdc_review_required |
| fast_setup | input_pixel | ddrphy_sysclk | -2.151 | 304 | independent_clock_domains_cdc_review_required |
| fast_setup | input_pixel | board27 | -0.319 | 2 | independent_clock_domains_cdc_review_required |
| fast_setup | cfg_clk | board27 | 1.337 | 0 | related_clock_domains_timed |
| fast_setup | input_pixel | input_pixel | 1.420 | 0 | same_clock |
| fast_setup | ddrphy_sysclk | ddrphy_sysclk | 1.455 | 0 | same_clock |
| fast_setup | ddrphy_sysclk | phy_dq_sysclk_0 | 2.579 | 0 | core_to_divided_phy_timed |
| fast_setup | ddrphy_sysclk | phy_dq_sysclk_1 | 2.902 | 0 | core_to_divided_phy_timed |
| fast_setup | phy_dq_sysclk_1 | ddrphy_sysclk | 4.157 | 0 | core_to_divided_phy_timed |
| fast_setup | phy_dq_sysclk_0 | ddrphy_sysclk | 4.895 | 0 | core_to_divided_phy_timed |
| fast_setup | rst_clk | rst_clk | 5.783 | 0 | same_clock |
| fast_setup | board27 | board27 | 32.494 | 0 | same_clock |
| fast_setup | cfg_clk | cfg_clk | 96.222 | 0 | same_clock |
| fast_hold | input_pixel | ddrphy_sysclk | -2.195 | 9 | independent_clock_domains_cdc_review_required |
| fast_hold | board27 | ddrphy_sysclk | -1.937 | 188 | independent_clock_domains_cdc_review_required |
| fast_hold | input_pixel | board27 | -0.192 | 2 | independent_clock_domains_cdc_review_required |
| fast_hold | phy_dq_sysclk_1 | ddrphy_sysclk | 0.009 | 0 | core_to_divided_phy_timed |
| fast_hold | ddrphy_sysclk | ddrphy_sysclk | 0.013 | 0 | same_clock |
| fast_hold | ddrphy_sysclk | phy_dq_sysclk_0 | 0.019 | 0 | core_to_divided_phy_timed |
| fast_hold | ddrphy_sysclk | phy_dq_sysclk_1 | 0.020 | 0 | core_to_divided_phy_timed |
| fast_hold | input_pixel | input_pixel | 0.091 | 0 | same_clock |
| fast_hold | cfg_clk | board27 | 0.142 | 0 | related_clock_domains_timed |
| fast_hold | rst_clk | rst_clk | 0.151 | 0 | same_clock |
| fast_hold | cfg_clk | cfg_clk | 0.159 | 0 | same_clock |
| fast_hold | phy_dq_sysclk_0 | ddrphy_sysclk | 0.195 | 0 | core_to_divided_phy_timed |
| fast_hold | board27 | board27 | 0.199 | 0 | same_clock |
| fast_hold | ddrphy_sysclk | board27 | 0.847 | 0 | independent_clock_domains_cdc_review_required |
| fast_hold | ddrphy_sysclk | input_pixel | 0.956 | 0 | independent_clock_domains_cdc_review_required |
| fast_recovery | board27 | ddrphy_sysclk | -1.528 | 852 | independent_clock_domains_cdc_review_required |
| fast_recovery | board27 | input_pixel | -1.163 | 505 | independent_clock_domains_cdc_review_required |
| fast_recovery | board27 | cfg_clk | 0.750 | 0 | related_clock_domains_timed |
| fast_recovery | ddrphy_sysclk | ddrphy_sysclk | 4.179 | 0 | same_clock |
| fast_recovery | rst_clk | rst_clk | 6.545 | 0 | same_clock |
| fast_recovery | board27 | board27 | 33.554 | 0 | same_clock |
| fast_recovery | cfg_clk | cfg_clk | 97.808 | 0 | same_clock |
| fast_removal | board27 | ddrphy_sysclk | -1.900 | 852 | independent_clock_domains_cdc_review_required |
| fast_removal | board27 | cfg_clk | 0.189 | 0 | related_clock_domains_timed |
| fast_removal | ddrphy_sysclk | ddrphy_sysclk | 0.237 | 0 | same_clock |
| fast_removal | cfg_clk | cfg_clk | 0.268 | 0 | same_clock |
| fast_removal | board27 | input_pixel | 0.282 | 0 | independent_clock_domains_cdc_review_required |
| fast_removal | rst_clk | rst_clk | 0.289 | 0 | same_clock |
| fast_removal | board27 | board27 | 0.455 | 0 | same_clock |
| fast_mpw | phy_dq_clk_1 | phy_dq_clk_1 | 0.035 | 0 | same_clock |
| fast_mpw | phy_dq_clk_0 | phy_dq_clk_0 | 0.035 | 0 | same_clock |
| fast_mpw | phy_dq_sysclk_0 | phy_dq_sysclk_0 | 1.850 | 0 | same_clock |
| fast_mpw | phy_dq_sysclk_1 | phy_dq_sysclk_1 | 2.400 | 0 | same_clock |
| fast_mpw | input_pixel | input_pixel | 2.763 | 0 | same_clock |
| fast_mpw | ddrphy_sysclk | ddrphy_sysclk | 3.202 | 0 | same_clock |
| fast_mpw | rst_clk | rst_clk | 3.800 | 0 | same_clock |
| fast_mpw | board27 | board27 | 18.318 | 0 | same_clock |
| fast_mpw | cfg_clk | cfg_clk | 49.428 | 0 | same_clock |
| fast_skew |  |  | 0.240 | 0 | external_or_unclocked_requires_review |
| fast_skew |  |  | 0.240 | 0 | external_or_unclocked_requires_review |
| fast_skew |  |  | 0.527 | 0 | external_or_unclocked_requires_review |
| fast_skew |  |  | 0.527 | 0 | external_or_unclocked_requires_review |
