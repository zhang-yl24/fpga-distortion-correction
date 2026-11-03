# Native timing: physical-b

BuildID `11036001`, source `19771fce0efe486aa71a8f874376446a6f9966bdce44e6a03824172403857fa6`. Diagnostic scope; external IO, CDC and reset acceptance remain pending.

| Corner/check | Launch | Capture | Worst slack (ns) | Failing endpoints | Domain status |
| --- | --- | --- | ---: | ---: | --- |
| slow_setup | ddrphy_sysclk | input_pixel | -5.705 | 1660 | independent_clock_domains_cdc_review_required |
| slow_setup | input_pixel | ddrphy_sysclk | -5.060 | 324 | independent_clock_domains_cdc_review_required |
| slow_setup | board27 | ddrphy_sysclk | -4.926 | 188 | independent_clock_domains_cdc_review_required |
| slow_setup | ddrphy_sysclk | board27 | -3.761 | 6 | independent_clock_domains_cdc_review_required |
| slow_setup | ddrphy_sysclk | ddrphy_sysclk | -3.264 | 2457 | same_clock |
| slow_setup | input_pixel | board27 | -2.360 | 4 | independent_clock_domains_cdc_review_required |
| slow_setup | input_pixel | input_pixel | -1.692 | 1479 | same_clock |
| slow_setup | ddrphy_sysclk | phy_dq_sysclk_0 | -0.788 | 58 | core_to_divided_phy_timed |
| slow_setup | ddrphy_sysclk | phy_dq_sysclk_1 | 0.011 | 0 | core_to_divided_phy_timed |
| slow_setup | cfg_clk | board27 | 0.922 | 0 | related_clock_domains_timed |
| slow_setup | phy_dq_sysclk_1 | ddrphy_sysclk | 2.370 | 0 | core_to_divided_phy_timed |
| slow_setup | phy_dq_sysclk_0 | ddrphy_sysclk | 3.797 | 0 | core_to_divided_phy_timed |
| slow_setup | rst_clk | rst_clk | 4.721 | 0 | same_clock |
| slow_setup | board27 | board27 | 31.765 | 0 | same_clock |
| slow_setup | cfg_clk | cfg_clk | 94.364 | 0 | same_clock |
| slow_hold | input_pixel | ddrphy_sysclk | -2.439 | 14 | independent_clock_domains_cdc_review_required |
| slow_hold | board27 | ddrphy_sysclk | -1.586 | 179 | independent_clock_domains_cdc_review_required |
| slow_hold | ddrphy_sysclk | ddrphy_sysclk | 0.016 | 0 | same_clock |
| slow_hold | cfg_clk | cfg_clk | 0.148 | 0 | same_clock |
| slow_hold | input_pixel | input_pixel | 0.158 | 0 | same_clock |
| slow_hold | cfg_clk | board27 | 0.226 | 0 | related_clock_domains_timed |
| slow_hold | rst_clk | rst_clk | 0.265 | 0 | same_clock |
| slow_hold | board27 | board27 | 0.267 | 0 | same_clock |
| slow_hold | ddrphy_sysclk | phy_dq_sysclk_0 | 0.381 | 0 | core_to_divided_phy_timed |
| slow_hold | ddrphy_sysclk | phy_dq_sysclk_1 | 0.392 | 0 | core_to_divided_phy_timed |
| slow_hold | input_pixel | board27 | 0.432 | 0 | independent_clock_domains_cdc_review_required |
| slow_hold | ddrphy_sysclk | board27 | 0.465 | 0 | independent_clock_domains_cdc_review_required |
| slow_hold | phy_dq_sysclk_1 | ddrphy_sysclk | 0.518 | 0 | core_to_divided_phy_timed |
| slow_hold | phy_dq_sysclk_0 | ddrphy_sysclk | 0.589 | 0 | core_to_divided_phy_timed |
| slow_hold | ddrphy_sysclk | input_pixel | 0.778 | 0 | independent_clock_domains_cdc_review_required |
| slow_recovery | board27 | input_pixel | -3.199 | 500 | independent_clock_domains_cdc_review_required |
| slow_recovery | board27 | ddrphy_sysclk | -3.109 | 779 | independent_clock_domains_cdc_review_required |
| slow_recovery | board27 | cfg_clk | 0.364 | 0 | related_clock_domains_timed |
| slow_recovery | ddrphy_sysclk | ddrphy_sysclk | 2.643 | 0 | same_clock |
| slow_recovery | rst_clk | rst_clk | 4.997 | 0 | same_clock |
| slow_recovery | board27 | board27 | 33.539 | 0 | same_clock |
| slow_recovery | cfg_clk | cfg_clk | 96.963 | 0 | same_clock |
| slow_removal | board27 | ddrphy_sysclk | -1.717 | 779 | independent_clock_domains_cdc_review_required |
| slow_removal | ddrphy_sysclk | ddrphy_sysclk | 0.279 | 0 | same_clock |
| slow_removal | board27 | cfg_clk | 0.312 | 0 | related_clock_domains_timed |
| slow_removal | cfg_clk | cfg_clk | 0.424 | 0 | same_clock |
| slow_removal | rst_clk | rst_clk | 0.435 | 0 | same_clock |
| slow_removal | board27 | input_pixel | 0.443 | 0 | independent_clock_domains_cdc_review_required |
| slow_removal | board27 | board27 | 0.465 | 0 | same_clock |
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
| fast_setup | ddrphy_sysclk | input_pixel | -3.822 | 1660 | independent_clock_domains_cdc_review_required |
| fast_setup | ddrphy_sysclk | board27 | -3.099 | 6 | independent_clock_domains_cdc_review_required |
| fast_setup | board27 | ddrphy_sysclk | -2.644 | 188 | independent_clock_domains_cdc_review_required |
| fast_setup | input_pixel | ddrphy_sysclk | -2.370 | 324 | independent_clock_domains_cdc_review_required |
| fast_setup | input_pixel | board27 | -1.108 | 4 | independent_clock_domains_cdc_review_required |
| fast_setup | ddrphy_sysclk | ddrphy_sysclk | 0.891 | 0 | same_clock |
| fast_setup | input_pixel | input_pixel | 1.487 | 0 | same_clock |
| fast_setup | cfg_clk | board27 | 1.789 | 0 | related_clock_domains_timed |
| fast_setup | ddrphy_sysclk | phy_dq_sysclk_0 | 2.133 | 0 | core_to_divided_phy_timed |
| fast_setup | ddrphy_sysclk | phy_dq_sysclk_1 | 2.627 | 0 | core_to_divided_phy_timed |
| fast_setup | phy_dq_sysclk_1 | ddrphy_sysclk | 4.120 | 0 | core_to_divided_phy_timed |
| fast_setup | phy_dq_sysclk_0 | ddrphy_sysclk | 5.085 | 0 | core_to_divided_phy_timed |
| fast_setup | rst_clk | rst_clk | 5.898 | 0 | same_clock |
| fast_setup | board27 | board27 | 33.812 | 0 | same_clock |
| fast_setup | cfg_clk | cfg_clk | 96.503 | 0 | same_clock |
| fast_hold | input_pixel | ddrphy_sysclk | -2.377 | 14 | independent_clock_domains_cdc_review_required |
| fast_hold | board27 | ddrphy_sysclk | -1.754 | 188 | independent_clock_domains_cdc_review_required |
| fast_hold | ddrphy_sysclk | ddrphy_sysclk | 0.010 | 0 | same_clock |
| fast_hold | phy_dq_sysclk_1 | ddrphy_sysclk | 0.014 | 0 | core_to_divided_phy_timed |
| fast_hold | ddrphy_sysclk | phy_dq_sysclk_1 | 0.021 | 0 | core_to_divided_phy_timed |
| fast_hold | ddrphy_sysclk | phy_dq_sysclk_0 | 0.021 | 0 | core_to_divided_phy_timed |
| fast_hold | cfg_clk | board27 | 0.049 | 0 | related_clock_domains_timed |
| fast_hold | input_pixel | input_pixel | 0.100 | 0 | same_clock |
| fast_hold | cfg_clk | cfg_clk | 0.101 | 0 | same_clock |
| fast_hold | phy_dq_sysclk_0 | ddrphy_sysclk | 0.123 | 0 | core_to_divided_phy_timed |
| fast_hold | rst_clk | rst_clk | 0.175 | 0 | same_clock |
| fast_hold | board27 | board27 | 0.183 | 0 | same_clock |
| fast_hold | input_pixel | board27 | 0.236 | 0 | independent_clock_domains_cdc_review_required |
| fast_hold | ddrphy_sysclk | board27 | 0.741 | 0 | independent_clock_domains_cdc_review_required |
| fast_hold | ddrphy_sysclk | input_pixel | 0.961 | 0 | independent_clock_domains_cdc_review_required |
| fast_recovery | board27 | input_pixel | -1.684 | 500 | independent_clock_domains_cdc_review_required |
| fast_recovery | board27 | ddrphy_sysclk | -1.293 | 779 | independent_clock_domains_cdc_review_required |
| fast_recovery | board27 | cfg_clk | 1.498 | 0 | related_clock_domains_timed |
| fast_recovery | ddrphy_sysclk | ddrphy_sysclk | 4.429 | 0 | same_clock |
| fast_recovery | rst_clk | rst_clk | 6.090 | 0 | same_clock |
| fast_recovery | board27 | board27 | 34.878 | 0 | same_clock |
| fast_recovery | cfg_clk | cfg_clk | 98.098 | 0 | same_clock |
| fast_removal | board27 | ddrphy_sysclk | -1.864 | 779 | independent_clock_domains_cdc_review_required |
| fast_removal | board27 | cfg_clk | 0.009 | 0 | related_clock_domains_timed |
| fast_removal | ddrphy_sysclk | ddrphy_sysclk | 0.189 | 0 | same_clock |
| fast_removal | board27 | input_pixel | 0.291 | 0 | independent_clock_domains_cdc_review_required |
| fast_removal | cfg_clk | cfg_clk | 0.294 | 0 | same_clock |
| fast_removal | rst_clk | rst_clk | 0.305 | 0 | same_clock |
| fast_removal | board27 | board27 | 0.310 | 0 | same_clock |
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
