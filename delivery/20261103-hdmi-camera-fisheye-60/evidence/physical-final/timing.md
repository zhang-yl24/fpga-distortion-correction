# Native timing: physical-d

BuildID `11037003`, source `1cfc559ec1ad25018f691d85febb2a222dc30cbd38a3371a786c8d951b597ed4`. Diagnostic scope; external IO, CDC and reset acceptance remain pending.

| Corner/check | Launch | Capture | Worst slack (ns) | Failing endpoints | Domain status |
| --- | --- | --- | ---: | ---: | --- |
| slow_setup | input_pixel | ddrphy_sysclk | -6.273 | 330 | independent_clock_domains_cdc_review_required |
| slow_setup | ddrphy_sysclk | input_pixel | -5.700 | 1663 | independent_clock_domains_cdc_review_required |
| slow_setup | board27 | ddrphy_sysclk | -5.601 | 188 | independent_clock_domains_cdc_review_required |
| slow_setup | ddrphy_sysclk | board27 | -4.039 | 6 | independent_clock_domains_cdc_review_required |
| slow_setup | ddrphy_sysclk | ddrphy_sysclk | -3.954 | 7453 | same_clock |
| slow_setup | input_pixel | input_pixel | -2.762 | 1548 | same_clock |
| slow_setup | input_pixel | board27 | -1.829 | 4 | independent_clock_domains_cdc_review_required |
| slow_setup | ddrphy_sysclk | phy_dq_sysclk_0 | -0.012 | 2 | core_to_divided_phy_timed |
| slow_setup | ddrphy_sysclk | phy_dq_sysclk_1 | 0.076 | 0 | core_to_divided_phy_timed |
| slow_setup | cfg_clk | board27 | 0.814 | 0 | related_clock_domains_timed |
| slow_setup | phy_dq_sysclk_1 | ddrphy_sysclk | 2.495 | 0 | core_to_divided_phy_timed |
| slow_setup | phy_dq_sysclk_0 | ddrphy_sysclk | 3.654 | 0 | core_to_divided_phy_timed |
| slow_setup | rst_clk | rst_clk | 4.892 | 0 | same_clock |
| slow_setup | board27 | board27 | 32.378 | 0 | same_clock |
| slow_setup | cfg_clk | cfg_clk | 94.692 | 0 | same_clock |
| slow_hold | input_pixel | ddrphy_sysclk | -2.044 | 15 | independent_clock_domains_cdc_review_required |
| slow_hold | board27 | ddrphy_sysclk | -1.543 | 180 | independent_clock_domains_cdc_review_required |
| slow_hold | ddrphy_sysclk | ddrphy_sysclk | 0.019 | 0 | same_clock |
| slow_hold | cfg_clk | cfg_clk | 0.111 | 0 | same_clock |
| slow_hold | input_pixel | input_pixel | 0.186 | 0 | same_clock |
| slow_hold | rst_clk | rst_clk | 0.201 | 0 | same_clock |
| slow_hold | cfg_clk | board27 | 0.205 | 0 | related_clock_domains_timed |
| slow_hold | input_pixel | board27 | 0.250 | 0 | independent_clock_domains_cdc_review_required |
| slow_hold | board27 | board27 | 0.270 | 0 | same_clock |
| slow_hold | ddrphy_sysclk | phy_dq_sysclk_1 | 0.402 | 0 | core_to_divided_phy_timed |
| slow_hold | ddrphy_sysclk | phy_dq_sysclk_0 | 0.403 | 0 | core_to_divided_phy_timed |
| slow_hold | phy_dq_sysclk_1 | ddrphy_sysclk | 0.457 | 0 | core_to_divided_phy_timed |
| slow_hold | ddrphy_sysclk | board27 | 0.472 | 0 | independent_clock_domains_cdc_review_required |
| slow_hold | phy_dq_sysclk_0 | ddrphy_sysclk | 0.761 | 0 | core_to_divided_phy_timed |
| slow_hold | ddrphy_sysclk | input_pixel | 0.772 | 0 | independent_clock_domains_cdc_review_required |
| slow_recovery | board27 | ddrphy_sysclk | -4.215 | 709 | independent_clock_domains_cdc_review_required |
| slow_recovery | board27 | input_pixel | -3.335 | 500 | independent_clock_domains_cdc_review_required |
| slow_recovery | board27 | cfg_clk | -0.978 | 5 | related_clock_domains_timed |
| slow_recovery | ddrphy_sysclk | ddrphy_sysclk | 1.673 | 0 | same_clock |
| slow_recovery | rst_clk | rst_clk | 5.523 | 0 | same_clock |
| slow_recovery | board27 | board27 | 31.432 | 0 | same_clock |
| slow_recovery | cfg_clk | cfg_clk | 97.606 | 0 | same_clock |
| slow_removal | board27 | ddrphy_sysclk | -1.741 | 696 | independent_clock_domains_cdc_review_required |
| slow_removal | ddrphy_sysclk | ddrphy_sysclk | 0.389 | 0 | same_clock |
| slow_removal | rst_clk | rst_clk | 0.409 | 0 | same_clock |
| slow_removal | board27 | cfg_clk | 0.461 | 0 | related_clock_domains_timed |
| slow_removal | cfg_clk | cfg_clk | 0.473 | 0 | same_clock |
| slow_removal | board27 | input_pixel | 0.611 | 0 | independent_clock_domains_cdc_review_required |
| slow_removal | board27 | board27 | 0.638 | 0 | same_clock |
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
| fast_setup | ddrphy_sysclk | input_pixel | -3.853 | 1663 | independent_clock_domains_cdc_review_required |
| fast_setup | ddrphy_sysclk | board27 | -3.213 | 6 | independent_clock_domains_cdc_review_required |
| fast_setup | board27 | ddrphy_sysclk | -3.010 | 188 | independent_clock_domains_cdc_review_required |
| fast_setup | input_pixel | ddrphy_sysclk | -2.963 | 323 | independent_clock_domains_cdc_review_required |
| fast_setup | input_pixel | board27 | -0.803 | 4 | independent_clock_domains_cdc_review_required |
| fast_setup | ddrphy_sysclk | ddrphy_sysclk | 0.593 | 0 | same_clock |
| fast_setup | input_pixel | input_pixel | 0.809 | 0 | same_clock |
| fast_setup | cfg_clk | board27 | 1.755 | 0 | related_clock_domains_timed |
| fast_setup | ddrphy_sysclk | phy_dq_sysclk_0 | 2.621 | 0 | core_to_divided_phy_timed |
| fast_setup | ddrphy_sysclk | phy_dq_sysclk_1 | 2.703 | 0 | core_to_divided_phy_timed |
| fast_setup | phy_dq_sysclk_1 | ddrphy_sysclk | 4.146 | 0 | core_to_divided_phy_timed |
| fast_setup | phy_dq_sysclk_0 | ddrphy_sysclk | 4.881 | 0 | core_to_divided_phy_timed |
| fast_setup | rst_clk | rst_clk | 6.083 | 0 | same_clock |
| fast_setup | board27 | board27 | 34.052 | 0 | same_clock |
| fast_setup | cfg_clk | cfg_clk | 96.700 | 0 | same_clock |
| fast_hold | input_pixel | ddrphy_sysclk | -2.090 | 15 | independent_clock_domains_cdc_review_required |
| fast_hold | board27 | ddrphy_sysclk | -1.738 | 181 | independent_clock_domains_cdc_review_required |
| fast_hold | ddrphy_sysclk | ddrphy_sysclk | 0.012 | 0 | same_clock |
| fast_hold | ddrphy_sysclk | phy_dq_sysclk_0 | 0.020 | 0 | core_to_divided_phy_timed |
| fast_hold | ddrphy_sysclk | phy_dq_sysclk_1 | 0.022 | 0 | core_to_divided_phy_timed |
| fast_hold | phy_dq_sysclk_1 | ddrphy_sysclk | 0.025 | 0 | core_to_divided_phy_timed |
| fast_hold | cfg_clk | board27 | 0.032 | 0 | related_clock_domains_timed |
| fast_hold | cfg_clk | cfg_clk | 0.074 | 0 | same_clock |
| fast_hold | input_pixel | input_pixel | 0.114 | 0 | same_clock |
| fast_hold | input_pixel | board27 | 0.134 | 0 | independent_clock_domains_cdc_review_required |
| fast_hold | rst_clk | rst_clk | 0.149 | 0 | same_clock |
| fast_hold | board27 | board27 | 0.174 | 0 | same_clock |
| fast_hold | phy_dq_sysclk_0 | ddrphy_sysclk | 0.179 | 0 | core_to_divided_phy_timed |
| fast_hold | ddrphy_sysclk | board27 | 0.743 | 0 | independent_clock_domains_cdc_review_required |
| fast_hold | ddrphy_sysclk | input_pixel | 0.958 | 0 | independent_clock_domains_cdc_review_required |
| fast_recovery | board27 | ddrphy_sysclk | -1.973 | 709 | independent_clock_domains_cdc_review_required |
| fast_recovery | board27 | input_pixel | -1.850 | 500 | independent_clock_domains_cdc_review_required |
| fast_recovery | board27 | cfg_clk | 0.711 | 0 | related_clock_domains_timed |
| fast_recovery | ddrphy_sysclk | ddrphy_sysclk | 3.915 | 0 | same_clock |
| fast_recovery | rst_clk | rst_clk | 6.454 | 0 | same_clock |
| fast_recovery | board27 | board27 | 33.477 | 0 | same_clock |
| fast_recovery | cfg_clk | cfg_clk | 98.400 | 0 | same_clock |
| fast_removal | board27 | ddrphy_sysclk | -1.885 | 709 | independent_clock_domains_cdc_review_required |
| fast_removal | board27 | cfg_clk | 0.114 | 0 | related_clock_domains_timed |
| fast_removal | ddrphy_sysclk | ddrphy_sysclk | 0.264 | 0 | same_clock |
| fast_removal | rst_clk | rst_clk | 0.283 | 0 | same_clock |
| fast_removal | cfg_clk | cfg_clk | 0.328 | 0 | same_clock |
| fast_removal | board27 | input_pixel | 0.409 | 0 | independent_clock_domains_cdc_review_required |
| fast_removal | board27 | board27 | 0.434 | 0 | same_clock |
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
