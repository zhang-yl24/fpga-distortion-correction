# Native timing: physical-c

BuildID `11037002`, source `71d234151bbe7cf3a0c70b75f8b8f36ff8cc285aa87147658d577b4cd069d904`. Diagnostic scope; external IO, CDC and reset acceptance remain pending.

| Corner/check | Launch | Capture | Worst slack (ns) | Failing endpoints | Domain status |
| --- | --- | --- | ---: | ---: | --- |
| slow_setup | ddrphy_sysclk | input_pixel | -5.955 | 1660 | independent_clock_domains_cdc_review_required |
| slow_setup | input_pixel | ddrphy_sysclk | -5.171 | 329 | independent_clock_domains_cdc_review_required |
| slow_setup | board27 | ddrphy_sysclk | -5.056 | 188 | independent_clock_domains_cdc_review_required |
| slow_setup | ddrphy_sysclk | board27 | -3.926 | 6 | independent_clock_domains_cdc_review_required |
| slow_setup | ddrphy_sysclk | ddrphy_sysclk | -3.675 | 4785 | same_clock |
| slow_setup | input_pixel | input_pixel | -3.031 | 1483 | same_clock |
| slow_setup | input_pixel | board27 | -1.833 | 4 | independent_clock_domains_cdc_review_required |
| slow_setup | ddrphy_sysclk | phy_dq_sysclk_0 | 0.008 | 0 | core_to_divided_phy_timed |
| slow_setup | ddrphy_sysclk | phy_dq_sysclk_1 | 0.011 | 0 | core_to_divided_phy_timed |
| slow_setup | cfg_clk | board27 | 0.421 | 0 | related_clock_domains_timed |
| slow_setup | phy_dq_sysclk_1 | ddrphy_sysclk | 2.291 | 0 | core_to_divided_phy_timed |
| slow_setup | phy_dq_sysclk_0 | ddrphy_sysclk | 3.824 | 0 | core_to_divided_phy_timed |
| slow_setup | rst_clk | rst_clk | 4.395 | 0 | same_clock |
| slow_setup | board27 | board27 | 31.870 | 0 | same_clock |
| slow_setup | cfg_clk | cfg_clk | 94.242 | 0 | same_clock |
| slow_hold | input_pixel | ddrphy_sysclk | -2.051 | 15 | independent_clock_domains_cdc_review_required |
| slow_hold | board27 | ddrphy_sysclk | -1.758 | 179 | independent_clock_domains_cdc_review_required |
| slow_hold | ddrphy_sysclk | ddrphy_sysclk | 0.010 | 0 | same_clock |
| slow_hold | input_pixel | input_pixel | 0.130 | 0 | same_clock |
| slow_hold | cfg_clk | cfg_clk | 0.148 | 0 | same_clock |
| slow_hold | cfg_clk | board27 | 0.176 | 0 | related_clock_domains_timed |
| slow_hold | rst_clk | rst_clk | 0.257 | 0 | same_clock |
| slow_hold | board27 | board27 | 0.284 | 0 | same_clock |
| slow_hold | ddrphy_sysclk | phy_dq_sysclk_0 | 0.376 | 0 | core_to_divided_phy_timed |
| slow_hold | ddrphy_sysclk | phy_dq_sysclk_1 | 0.395 | 0 | core_to_divided_phy_timed |
| slow_hold | input_pixel | board27 | 0.453 | 0 | independent_clock_domains_cdc_review_required |
| slow_hold | phy_dq_sysclk_1 | ddrphy_sysclk | 0.478 | 0 | core_to_divided_phy_timed |
| slow_hold | ddrphy_sysclk | board27 | 0.498 | 0 | independent_clock_domains_cdc_review_required |
| slow_hold | phy_dq_sysclk_0 | ddrphy_sysclk | 0.633 | 0 | core_to_divided_phy_timed |
| slow_hold | ddrphy_sysclk | input_pixel | 0.775 | 0 | independent_clock_domains_cdc_review_required |
| slow_recovery | board27 | input_pixel | -3.264 | 500 | independent_clock_domains_cdc_review_required |
| slow_recovery | board27 | ddrphy_sysclk | -2.964 | 784 | independent_clock_domains_cdc_review_required |
| slow_recovery | board27 | cfg_clk | 0.045 | 0 | related_clock_domains_timed |
| slow_recovery | ddrphy_sysclk | ddrphy_sysclk | 0.103 | 0 | same_clock |
| slow_recovery | rst_clk | rst_clk | 5.740 | 0 | same_clock |
| slow_recovery | board27 | board27 | 33.232 | 0 | same_clock |
| slow_recovery | cfg_clk | cfg_clk | 97.245 | 0 | same_clock |
| slow_removal | board27 | ddrphy_sysclk | -1.852 | 784 | independent_clock_domains_cdc_review_required |
| slow_removal | board27 | cfg_clk | 0.323 | 0 | related_clock_domains_timed |
| slow_removal | board27 | input_pixel | 0.369 | 0 | independent_clock_domains_cdc_review_required |
| slow_removal | ddrphy_sysclk | ddrphy_sysclk | 0.436 | 0 | same_clock |
| slow_removal | cfg_clk | cfg_clk | 0.465 | 0 | same_clock |
| slow_removal | rst_clk | rst_clk | 0.547 | 0 | same_clock |
| slow_removal | board27 | board27 | 0.779 | 0 | same_clock |
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
| fast_setup | ddrphy_sysclk | input_pixel | -3.975 | 1660 | independent_clock_domains_cdc_review_required |
| fast_setup | ddrphy_sysclk | board27 | -3.124 | 6 | independent_clock_domains_cdc_review_required |
| fast_setup | board27 | ddrphy_sysclk | -2.683 | 188 | independent_clock_domains_cdc_review_required |
| fast_setup | input_pixel | ddrphy_sysclk | -2.486 | 323 | independent_clock_domains_cdc_review_required |
| fast_setup | input_pixel | board27 | -0.857 | 4 | independent_clock_domains_cdc_review_required |
| fast_setup | ddrphy_sysclk | ddrphy_sysclk | 0.607 | 0 | same_clock |
| fast_setup | input_pixel | input_pixel | 0.636 | 0 | same_clock |
| fast_setup | cfg_clk | board27 | 1.447 | 0 | related_clock_domains_timed |
| fast_setup | ddrphy_sysclk | phy_dq_sysclk_0 | 2.486 | 0 | core_to_divided_phy_timed |
| fast_setup | ddrphy_sysclk | phy_dq_sysclk_1 | 2.585 | 0 | core_to_divided_phy_timed |
| fast_setup | phy_dq_sysclk_1 | ddrphy_sysclk | 3.958 | 0 | core_to_divided_phy_timed |
| fast_setup | phy_dq_sysclk_0 | ddrphy_sysclk | 5.012 | 0 | core_to_divided_phy_timed |
| fast_setup | rst_clk | rst_clk | 5.876 | 0 | same_clock |
| fast_setup | board27 | board27 | 33.696 | 0 | same_clock |
| fast_setup | cfg_clk | cfg_clk | 96.452 | 0 | same_clock |
| fast_hold | input_pixel | ddrphy_sysclk | -2.118 | 15 | independent_clock_domains_cdc_review_required |
| fast_hold | board27 | ddrphy_sysclk | -1.877 | 185 | independent_clock_domains_cdc_review_required |
| fast_hold | ddrphy_sysclk | ddrphy_sysclk | 0.010 | 0 | same_clock |
| fast_hold | phy_dq_sysclk_1 | ddrphy_sysclk | 0.013 | 0 | core_to_divided_phy_timed |
| fast_hold | cfg_clk | board27 | 0.019 | 0 | related_clock_domains_timed |
| fast_hold | ddrphy_sysclk | phy_dq_sysclk_0 | 0.020 | 0 | core_to_divided_phy_timed |
| fast_hold | ddrphy_sysclk | phy_dq_sysclk_1 | 0.021 | 0 | core_to_divided_phy_timed |
| fast_hold | input_pixel | input_pixel | 0.084 | 0 | same_clock |
| fast_hold | cfg_clk | cfg_clk | 0.101 | 0 | same_clock |
| fast_hold | phy_dq_sysclk_0 | ddrphy_sysclk | 0.115 | 0 | core_to_divided_phy_timed |
| fast_hold | rst_clk | rst_clk | 0.168 | 0 | same_clock |
| fast_hold | board27 | board27 | 0.180 | 0 | same_clock |
| fast_hold | input_pixel | board27 | 0.209 | 0 | independent_clock_domains_cdc_review_required |
| fast_hold | ddrphy_sysclk | board27 | 0.745 | 0 | independent_clock_domains_cdc_review_required |
| fast_hold | ddrphy_sysclk | input_pixel | 0.967 | 0 | independent_clock_domains_cdc_review_required |
| fast_recovery | board27 | input_pixel | -1.791 | 500 | independent_clock_domains_cdc_review_required |
| fast_recovery | board27 | ddrphy_sysclk | -1.259 | 784 | independent_clock_domains_cdc_review_required |
| fast_recovery | board27 | cfg_clk | 1.375 | 0 | related_clock_domains_timed |
| fast_recovery | ddrphy_sysclk | ddrphy_sysclk | 2.840 | 0 | same_clock |
| fast_recovery | rst_clk | rst_clk | 6.497 | 0 | same_clock |
| fast_recovery | board27 | board27 | 34.658 | 0 | same_clock |
| fast_recovery | cfg_clk | cfg_clk | 98.149 | 0 | same_clock |
| fast_removal | board27 | ddrphy_sysclk | -1.960 | 784 | independent_clock_domains_cdc_review_required |
| fast_removal | board27 | cfg_clk | 0.046 | 0 | related_clock_domains_timed |
| fast_removal | board27 | input_pixel | 0.246 | 0 | independent_clock_domains_cdc_review_required |
| fast_removal | ddrphy_sysclk | ddrphy_sysclk | 0.300 | 0 | same_clock |
| fast_removal | cfg_clk | cfg_clk | 0.322 | 0 | same_clock |
| fast_removal | rst_clk | rst_clk | 0.382 | 0 | same_clock |
| fast_removal | board27 | board27 | 0.537 | 0 | same_clock |
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
