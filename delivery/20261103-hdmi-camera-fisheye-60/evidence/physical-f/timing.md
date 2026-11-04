# Native timing: physical-f

BuildID `11037003`, source `1dab7ebbed5e5f61cba1d53c1e53294375280edcf8bdedc53289bd3c56c17a61`. Diagnostic scope; external IO, CDC and reset acceptance remain pending.

| Corner/check | Launch | Capture | Worst slack (ns) | Failing endpoints | Domain status |
| --- | --- | --- | ---: | ---: | --- |
| slow_setup | ddrphy_sysclk | input_pixel | -5.298 | 671 | independent_clock_domains_cdc_review_required |
| slow_setup | input_pixel | ddrphy_sysclk | -4.702 | 326 | independent_clock_domains_cdc_review_required |
| slow_setup | board27 | ddrphy_sysclk | -4.496 | 188 | independent_clock_domains_cdc_review_required |
| slow_setup | ddrphy_sysclk | board27 | -3.674 | 6 | independent_clock_domains_cdc_review_required |
| slow_setup | ddrphy_sysclk | ddrphy_sysclk | -2.170 | 1144 | same_clock |
| slow_setup | input_pixel | board27 | -1.968 | 4 | independent_clock_domains_cdc_review_required |
| slow_setup | input_pixel | input_pixel | -0.810 | 287 | same_clock |
| slow_setup | ddrphy_sysclk | phy_dq_sysclk_0 | -0.034 | 6 | core_to_divided_phy_timed |
| slow_setup | ddrphy_sysclk | phy_dq_sysclk_1 | 0.080 | 0 | core_to_divided_phy_timed |
| slow_setup | cfg_clk | board27 | 0.113 | 0 | related_clock_domains_timed |
| slow_setup | phy_dq_sysclk_1 | ddrphy_sysclk | 2.477 | 0 | core_to_divided_phy_timed |
| slow_setup | phy_dq_sysclk_0 | ddrphy_sysclk | 3.582 | 0 | core_to_divided_phy_timed |
| slow_setup | rst_clk | rst_clk | 4.545 | 0 | same_clock |
| slow_setup | board27 | board27 | 31.141 | 0 | same_clock |
| slow_setup | cfg_clk | cfg_clk | 93.781 | 0 | same_clock |
| slow_hold | board27 | ddrphy_sysclk | -1.781 | 181 | independent_clock_domains_cdc_review_required |
| slow_hold | input_pixel | ddrphy_sysclk | -1.638 | 7 | independent_clock_domains_cdc_review_required |
| slow_hold | ddrphy_sysclk | ddrphy_sysclk | 0.019 | 0 | same_clock |
| slow_hold | input_pixel | board27 | 0.057 | 0 | independent_clock_domains_cdc_review_required |
| slow_hold | input_pixel | input_pixel | 0.137 | 0 | same_clock |
| slow_hold | cfg_clk | cfg_clk | 0.150 | 0 | same_clock |
| slow_hold | cfg_clk | board27 | 0.185 | 0 | related_clock_domains_timed |
| slow_hold | rst_clk | rst_clk | 0.233 | 0 | same_clock |
| slow_hold | board27 | board27 | 0.275 | 0 | same_clock |
| slow_hold | ddrphy_sysclk | phy_dq_sysclk_0 | 0.349 | 0 | core_to_divided_phy_timed |
| slow_hold | ddrphy_sysclk | phy_dq_sysclk_1 | 0.378 | 0 | core_to_divided_phy_timed |
| slow_hold | ddrphy_sysclk | board27 | 0.464 | 0 | independent_clock_domains_cdc_review_required |
| slow_hold | phy_dq_sysclk_1 | ddrphy_sysclk | 0.468 | 0 | core_to_divided_phy_timed |
| slow_hold | ddrphy_sysclk | input_pixel | 0.774 | 0 | independent_clock_domains_cdc_review_required |
| slow_hold | phy_dq_sysclk_0 | ddrphy_sysclk | 0.917 | 0 | core_to_divided_phy_timed |
| slow_recovery | board27 | ddrphy_sysclk | -3.649 | 868 | independent_clock_domains_cdc_review_required |
| slow_recovery | board27 | input_pixel | -3.036 | 500 | independent_clock_domains_cdc_review_required |
| slow_recovery | board27 | cfg_clk | -0.420 | 5 | related_clock_domains_timed |
| slow_recovery | ddrphy_sysclk | ddrphy_sysclk | 0.171 | 0 | same_clock |
| slow_recovery | rst_clk | rst_clk | 4.746 | 0 | same_clock |
| slow_recovery | board27 | board27 | 33.274 | 0 | same_clock |
| slow_recovery | cfg_clk | cfg_clk | 97.328 | 0 | same_clock |
| slow_removal | board27 | ddrphy_sysclk | -1.794 | 868 | independent_clock_domains_cdc_review_required |
| slow_removal | board27 | cfg_clk | 0.333 | 0 | related_clock_domains_timed |
| slow_removal | board27 | input_pixel | 0.347 | 0 | independent_clock_domains_cdc_review_required |
| slow_removal | ddrphy_sysclk | ddrphy_sysclk | 0.396 | 0 | same_clock |
| slow_removal | cfg_clk | cfg_clk | 0.430 | 0 | same_clock |
| slow_removal | rst_clk | rst_clk | 0.515 | 0 | same_clock |
| slow_removal | board27 | board27 | 0.795 | 0 | same_clock |
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
| fast_setup | ddrphy_sysclk | input_pixel | -3.626 | 671 | independent_clock_domains_cdc_review_required |
| fast_setup | ddrphy_sysclk | board27 | -2.965 | 6 | independent_clock_domains_cdc_review_required |
| fast_setup | board27 | ddrphy_sysclk | -2.322 | 187 | independent_clock_domains_cdc_review_required |
| fast_setup | input_pixel | ddrphy_sysclk | -2.158 | 323 | independent_clock_domains_cdc_review_required |
| fast_setup | input_pixel | board27 | -0.876 | 4 | independent_clock_domains_cdc_review_required |
| fast_setup | cfg_clk | board27 | 1.341 | 0 | related_clock_domains_timed |
| fast_setup | ddrphy_sysclk | ddrphy_sysclk | 1.657 | 0 | same_clock |
| fast_setup | input_pixel | input_pixel | 1.958 | 0 | same_clock |
| fast_setup | ddrphy_sysclk | phy_dq_sysclk_0 | 2.547 | 0 | core_to_divided_phy_timed |
| fast_setup | ddrphy_sysclk | phy_dq_sysclk_1 | 2.626 | 0 | core_to_divided_phy_timed |
| fast_setup | phy_dq_sysclk_1 | ddrphy_sysclk | 4.150 | 0 | core_to_divided_phy_timed |
| fast_setup | phy_dq_sysclk_0 | ddrphy_sysclk | 4.792 | 0 | core_to_divided_phy_timed |
| fast_setup | rst_clk | rst_clk | 5.734 | 0 | same_clock |
| fast_setup | board27 | board27 | 33.398 | 0 | same_clock |
| fast_setup | cfg_clk | cfg_clk | 96.116 | 0 | same_clock |
| fast_hold | board27 | ddrphy_sysclk | -1.905 | 188 | independent_clock_domains_cdc_review_required |
| fast_hold | input_pixel | ddrphy_sysclk | -1.798 | 7 | independent_clock_domains_cdc_review_required |
| fast_hold | input_pixel | board27 | 0.004 | 0 | independent_clock_domains_cdc_review_required |
| fast_hold | ddrphy_sysclk | ddrphy_sysclk | 0.012 | 0 | same_clock |
| fast_hold | phy_dq_sysclk_1 | ddrphy_sysclk | 0.013 | 0 | core_to_divided_phy_timed |
| fast_hold | cfg_clk | board27 | 0.016 | 0 | related_clock_domains_timed |
| fast_hold | ddrphy_sysclk | phy_dq_sysclk_1 | 0.021 | 0 | core_to_divided_phy_timed |
| fast_hold | ddrphy_sysclk | phy_dq_sysclk_0 | 0.021 | 0 | core_to_divided_phy_timed |
| fast_hold | input_pixel | input_pixel | 0.081 | 0 | same_clock |
| fast_hold | cfg_clk | cfg_clk | 0.097 | 0 | same_clock |
| fast_hold | rst_clk | rst_clk | 0.157 | 0 | same_clock |
| fast_hold | board27 | board27 | 0.174 | 0 | same_clock |
| fast_hold | phy_dq_sysclk_0 | ddrphy_sysclk | 0.179 | 0 | core_to_divided_phy_timed |
| fast_hold | ddrphy_sysclk | board27 | 0.740 | 0 | independent_clock_domains_cdc_review_required |
| fast_hold | ddrphy_sysclk | input_pixel | 0.958 | 0 | independent_clock_domains_cdc_review_required |
| fast_recovery | board27 | ddrphy_sysclk | -1.623 | 868 | independent_clock_domains_cdc_review_required |
| fast_recovery | board27 | input_pixel | -1.619 | 500 | independent_clock_domains_cdc_review_required |
| fast_recovery | board27 | cfg_clk | 1.007 | 0 | related_clock_domains_timed |
| fast_recovery | ddrphy_sysclk | ddrphy_sysclk | 3.104 | 0 | same_clock |
| fast_recovery | rst_clk | rst_clk | 5.920 | 0 | same_clock |
| fast_recovery | board27 | board27 | 34.661 | 0 | same_clock |
| fast_recovery | cfg_clk | cfg_clk | 98.294 | 0 | same_clock |
| fast_removal | board27 | ddrphy_sysclk | -1.927 | 868 | independent_clock_domains_cdc_review_required |
| fast_removal | board27 | cfg_clk | 0.018 | 0 | related_clock_domains_timed |
| fast_removal | board27 | input_pixel | 0.224 | 0 | independent_clock_domains_cdc_review_required |
| fast_removal | ddrphy_sysclk | ddrphy_sysclk | 0.276 | 0 | same_clock |
| fast_removal | cfg_clk | cfg_clk | 0.294 | 0 | same_clock |
| fast_removal | rst_clk | rst_clk | 0.361 | 0 | same_clock |
| fast_removal | board27 | board27 | 0.550 | 0 | same_clock |
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
