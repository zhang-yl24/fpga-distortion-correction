# Native timing: physical-e

BuildID `11037003`, source `49ada7d5a4a1f0ce67bd83a6aef88dcf00f84eda3f92d3fda9aabcc4de74bc3d`. Diagnostic scope; external IO, CDC and reset acceptance remain pending.

| Corner/check | Launch | Capture | Worst slack (ns) | Failing endpoints | Domain status |
| --- | --- | --- | ---: | ---: | --- |
| slow_setup | ddrphy_sysclk | input_pixel | -5.312 | 679 | independent_clock_domains_cdc_review_required |
| slow_setup | input_pixel | ddrphy_sysclk | -4.556 | 330 | independent_clock_domains_cdc_review_required |
| slow_setup | board27 | ddrphy_sysclk | -4.427 | 188 | independent_clock_domains_cdc_review_required |
| slow_setup | ddrphy_sysclk | board27 | -3.691 | 6 | independent_clock_domains_cdc_review_required |
| slow_setup | ddrphy_sysclk | ddrphy_sysclk | -2.728 | 3643 | same_clock |
| slow_setup | input_pixel | input_pixel | -2.672 | 801 | same_clock |
| slow_setup | input_pixel | board27 | -1.698 | 4 | independent_clock_domains_cdc_review_required |
| slow_setup | ddrphy_sysclk | phy_dq_sysclk_0 | 0.007 | 0 | core_to_divided_phy_timed |
| slow_setup | ddrphy_sysclk | phy_dq_sysclk_1 | 0.338 | 0 | core_to_divided_phy_timed |
| slow_setup | cfg_clk | board27 | 0.951 | 0 | related_clock_domains_timed |
| slow_setup | phy_dq_sysclk_1 | ddrphy_sysclk | 2.621 | 0 | core_to_divided_phy_timed |
| slow_setup | phy_dq_sysclk_0 | ddrphy_sysclk | 3.137 | 0 | core_to_divided_phy_timed |
| slow_setup | rst_clk | rst_clk | 3.914 | 0 | same_clock |
| slow_setup | board27 | board27 | 31.783 | 0 | same_clock |
| slow_setup | cfg_clk | cfg_clk | 94.963 | 0 | same_clock |
| slow_hold | input_pixel | ddrphy_sysclk | -1.797 | 14 | independent_clock_domains_cdc_review_required |
| slow_hold | board27 | ddrphy_sysclk | -1.675 | 180 | independent_clock_domains_cdc_review_required |
| slow_hold | ddrphy_sysclk | ddrphy_sysclk | 0.019 | 0 | same_clock |
| slow_hold | input_pixel | input_pixel | 0.148 | 0 | same_clock |
| slow_hold | cfg_clk | cfg_clk | 0.149 | 0 | same_clock |
| slow_hold | input_pixel | board27 | 0.154 | 0 | independent_clock_domains_cdc_review_required |
| slow_hold | rst_clk | rst_clk | 0.159 | 0 | same_clock |
| slow_hold | cfg_clk | board27 | 0.195 | 0 | related_clock_domains_timed |
| slow_hold | board27 | board27 | 0.224 | 0 | same_clock |
| slow_hold | ddrphy_sysclk | phy_dq_sysclk_0 | 0.399 | 0 | core_to_divided_phy_timed |
| slow_hold | ddrphy_sysclk | phy_dq_sysclk_1 | 0.416 | 0 | core_to_divided_phy_timed |
| slow_hold | phy_dq_sysclk_1 | ddrphy_sysclk | 0.476 | 0 | core_to_divided_phy_timed |
| slow_hold | ddrphy_sysclk | board27 | 0.485 | 0 | independent_clock_domains_cdc_review_required |
| slow_hold | ddrphy_sysclk | input_pixel | 0.779 | 0 | independent_clock_domains_cdc_review_required |
| slow_hold | phy_dq_sysclk_0 | ddrphy_sysclk | 1.319 | 0 | core_to_divided_phy_timed |
| slow_recovery | board27 | ddrphy_sysclk | -3.518 | 834 | independent_clock_domains_cdc_review_required |
| slow_recovery | board27 | input_pixel | -3.139 | 500 | independent_clock_domains_cdc_review_required |
| slow_recovery | board27 | cfg_clk | -1.506 | 5 | related_clock_domains_timed |
| slow_recovery | ddrphy_sysclk | ddrphy_sysclk | 0.643 | 0 | same_clock |
| slow_recovery | rst_clk | rst_clk | 3.638 | 0 | same_clock |
| slow_recovery | board27 | board27 | 32.456 | 0 | same_clock |
| slow_recovery | cfg_clk | cfg_clk | 96.391 | 0 | same_clock |
| slow_removal | board27 | ddrphy_sysclk | -1.853 | 834 | independent_clock_domains_cdc_review_required |
| slow_removal | board27 | cfg_clk | 0.302 | 0 | related_clock_domains_timed |
| slow_removal | rst_clk | rst_clk | 0.337 | 0 | same_clock |
| slow_removal | board27 | input_pixel | 0.378 | 0 | independent_clock_domains_cdc_review_required |
| slow_removal | ddrphy_sysclk | ddrphy_sysclk | 0.410 | 0 | same_clock |
| slow_removal | board27 | board27 | 0.545 | 0 | same_clock |
| slow_removal | cfg_clk | cfg_clk | 0.654 | 0 | same_clock |
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
| fast_setup | ddrphy_sysclk | input_pixel | -3.587 | 679 | independent_clock_domains_cdc_review_required |
| fast_setup | ddrphy_sysclk | board27 | -2.964 | 6 | independent_clock_domains_cdc_review_required |
| fast_setup | board27 | ddrphy_sysclk | -2.336 | 188 | independent_clock_domains_cdc_review_required |
| fast_setup | input_pixel | ddrphy_sysclk | -2.065 | 324 | independent_clock_domains_cdc_review_required |
| fast_setup | input_pixel | board27 | -0.760 | 4 | independent_clock_domains_cdc_review_required |
| fast_setup | input_pixel | input_pixel | 0.949 | 0 | same_clock |
| fast_setup | ddrphy_sysclk | ddrphy_sysclk | 1.117 | 0 | same_clock |
| fast_setup | cfg_clk | board27 | 1.744 | 0 | related_clock_domains_timed |
| fast_setup | ddrphy_sysclk | phy_dq_sysclk_0 | 2.474 | 0 | core_to_divided_phy_timed |
| fast_setup | ddrphy_sysclk | phy_dq_sysclk_1 | 2.955 | 0 | core_to_divided_phy_timed |
| fast_setup | phy_dq_sysclk_1 | ddrphy_sysclk | 4.223 | 0 | core_to_divided_phy_timed |
| fast_setup | phy_dq_sysclk_0 | ddrphy_sysclk | 4.534 | 0 | core_to_divided_phy_timed |
| fast_setup | rst_clk | rst_clk | 5.350 | 0 | same_clock |
| fast_setup | board27 | board27 | 33.805 | 0 | same_clock |
| fast_setup | cfg_clk | cfg_clk | 96.839 | 0 | same_clock |
| fast_hold | input_pixel | ddrphy_sysclk | -1.958 | 14 | independent_clock_domains_cdc_review_required |
| fast_hold | board27 | ddrphy_sysclk | -1.831 | 188 | independent_clock_domains_cdc_review_required |
| fast_hold | ddrphy_sysclk | ddrphy_sysclk | 0.013 | 0 | same_clock |
| fast_hold | phy_dq_sysclk_1 | ddrphy_sysclk | 0.017 | 0 | core_to_divided_phy_timed |
| fast_hold | ddrphy_sysclk | phy_dq_sysclk_0 | 0.018 | 0 | core_to_divided_phy_timed |
| fast_hold | ddrphy_sysclk | phy_dq_sysclk_1 | 0.021 | 0 | core_to_divided_phy_timed |
| fast_hold | cfg_clk | board27 | 0.033 | 0 | related_clock_domains_timed |
| fast_hold | input_pixel | board27 | 0.067 | 0 | independent_clock_domains_cdc_review_required |
| fast_hold | input_pixel | input_pixel | 0.093 | 0 | same_clock |
| fast_hold | cfg_clk | cfg_clk | 0.101 | 0 | same_clock |
| fast_hold | rst_clk | rst_clk | 0.118 | 0 | same_clock |
| fast_hold | board27 | board27 | 0.148 | 0 | same_clock |
| fast_hold | phy_dq_sysclk_0 | ddrphy_sysclk | 0.395 | 0 | core_to_divided_phy_timed |
| fast_hold | ddrphy_sysclk | board27 | 0.756 | 0 | independent_clock_domains_cdc_review_required |
| fast_hold | ddrphy_sysclk | input_pixel | 0.957 | 0 | independent_clock_domains_cdc_review_required |
| fast_recovery | board27 | input_pixel | -1.705 | 500 | independent_clock_domains_cdc_review_required |
| fast_recovery | board27 | ddrphy_sysclk | -1.554 | 834 | independent_clock_domains_cdc_review_required |
| fast_recovery | board27 | cfg_clk | 0.319 | 0 | related_clock_domains_timed |
| fast_recovery | ddrphy_sysclk | ddrphy_sysclk | 3.223 | 0 | same_clock |
| fast_recovery | rst_clk | rst_clk | 5.163 | 0 | same_clock |
| fast_recovery | board27 | board27 | 34.180 | 0 | same_clock |
| fast_recovery | cfg_clk | cfg_clk | 97.695 | 0 | same_clock |
| fast_removal | board27 | ddrphy_sysclk | -1.957 | 834 | independent_clock_domains_cdc_review_required |
| fast_removal | board27 | cfg_clk | 0.053 | 0 | related_clock_domains_timed |
| fast_removal | rst_clk | rst_clk | 0.228 | 0 | same_clock |
| fast_removal | board27 | input_pixel | 0.251 | 0 | independent_clock_domains_cdc_review_required |
| fast_removal | ddrphy_sysclk | ddrphy_sysclk | 0.285 | 0 | same_clock |
| fast_removal | board27 | board27 | 0.372 | 0 | same_clock |
| fast_removal | cfg_clk | cfg_clk | 0.462 | 0 | same_clock |
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
