# Native timing: physical-i

BuildID `11037003`, source `d931793d62bc852c25be57f16528ac7d18dc70fc5760138dcf05e6f443ee8bd5`. Diagnostic scope; external IO, CDC and reset acceptance remain pending.

| Corner/check | Launch | Capture | Worst slack (ns) | Failing endpoints | Domain status |
| --- | --- | --- | ---: | ---: | --- |
| slow_setup | ddrphy_sysclk | input_pixel | -5.344 | 543 | independent_clock_domains_cdc_review_required |
| slow_setup | input_pixel | ddrphy_sysclk | -4.866 | 304 | independent_clock_domains_cdc_review_required |
| slow_setup | board27 | ddrphy_sysclk | -4.630 | 188 | independent_clock_domains_cdc_review_required |
| slow_setup | ddrphy_sysclk | board27 | -4.253 | 3 | independent_clock_domains_cdc_review_required |
| slow_setup | ddrphy_sysclk | ddrphy_sysclk | -2.886 | 3601 | same_clock |
| slow_setup | input_pixel | input_pixel | -2.414 | 433 | same_clock |
| slow_setup | input_pixel | board27 | -1.108 | 2 | independent_clock_domains_cdc_review_required |
| slow_setup | cfg_clk | board27 | -0.331 | 1 | related_clock_domains_timed |
| slow_setup | ddrphy_sysclk | phy_dq_sysclk_0 | -0.012 | 3 | core_to_divided_phy_timed |
| slow_setup | ddrphy_sysclk | phy_dq_sysclk_1 | 0.163 | 0 | core_to_divided_phy_timed |
| slow_setup | phy_dq_sysclk_1 | ddrphy_sysclk | 2.434 | 0 | core_to_divided_phy_timed |
| slow_setup | phy_dq_sysclk_0 | ddrphy_sysclk | 3.532 | 0 | core_to_divided_phy_timed |
| slow_setup | rst_clk | rst_clk | 4.485 | 0 | same_clock |
| slow_setup | board27 | board27 | 30.770 | 0 | same_clock |
| slow_setup | cfg_clk | cfg_clk | 94.115 | 0 | same_clock |
| slow_hold | input_pixel | ddrphy_sysclk | -2.048 | 8 | independent_clock_domains_cdc_review_required |
| slow_hold | board27 | ddrphy_sysclk | -1.808 | 181 | independent_clock_domains_cdc_review_required |
| slow_hold | input_pixel | board27 | -0.207 | 1 | independent_clock_domains_cdc_review_required |
| slow_hold | ddrphy_sysclk | ddrphy_sysclk | 0.017 | 0 | same_clock |
| slow_hold | cfg_clk | cfg_clk | 0.157 | 0 | same_clock |
| slow_hold | cfg_clk | board27 | 0.209 | 0 | related_clock_domains_timed |
| slow_hold | input_pixel | input_pixel | 0.229 | 0 | same_clock |
| slow_hold | rst_clk | rst_clk | 0.251 | 0 | same_clock |
| slow_hold | board27 | board27 | 0.260 | 0 | same_clock |
| slow_hold | ddrphy_sysclk | phy_dq_sysclk_0 | 0.371 | 0 | core_to_divided_phy_timed |
| slow_hold | ddrphy_sysclk | phy_dq_sysclk_1 | 0.384 | 0 | core_to_divided_phy_timed |
| slow_hold | phy_dq_sysclk_1 | ddrphy_sysclk | 0.458 | 0 | core_to_divided_phy_timed |
| slow_hold | ddrphy_sysclk | board27 | 0.616 | 0 | independent_clock_domains_cdc_review_required |
| slow_hold | ddrphy_sysclk | input_pixel | 0.776 | 0 | independent_clock_domains_cdc_review_required |
| slow_hold | phy_dq_sysclk_0 | ddrphy_sysclk | 0.817 | 0 | core_to_divided_phy_timed |
| slow_recovery | board27 | ddrphy_sysclk | -3.069 | 864 | independent_clock_domains_cdc_review_required |
| slow_recovery | board27 | input_pixel | -2.689 | 505 | independent_clock_domains_cdc_review_required |
| slow_recovery | board27 | cfg_clk | -0.403 | 7 | related_clock_domains_timed |
| slow_recovery | ddrphy_sysclk | ddrphy_sysclk | 2.964 | 0 | same_clock |
| slow_recovery | rst_clk | rst_clk | 5.896 | 0 | same_clock |
| slow_recovery | board27 | board27 | 32.877 | 0 | same_clock |
| slow_recovery | cfg_clk | cfg_clk | 97.113 | 0 | same_clock |
| slow_removal | board27 | ddrphy_sysclk | -1.817 | 864 | independent_clock_domains_cdc_review_required |
| slow_removal | board27 | cfg_clk | 0.279 | 0 | related_clock_domains_timed |
| slow_removal | rst_clk | rst_clk | 0.392 | 0 | same_clock |
| slow_removal | board27 | input_pixel | 0.419 | 0 | independent_clock_domains_cdc_review_required |
| slow_removal | ddrphy_sysclk | ddrphy_sysclk | 0.438 | 0 | same_clock |
| slow_removal | cfg_clk | cfg_clk | 0.506 | 0 | same_clock |
| slow_removal | board27 | board27 | 0.729 | 0 | same_clock |
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
| fast_setup | ddrphy_sysclk | input_pixel | -3.617 | 543 | independent_clock_domains_cdc_review_required |
| fast_setup | ddrphy_sysclk | board27 | -3.357 | 3 | independent_clock_domains_cdc_review_required |
| fast_setup | board27 | ddrphy_sysclk | -2.367 | 188 | independent_clock_domains_cdc_review_required |
| fast_setup | input_pixel | ddrphy_sysclk | -2.205 | 299 | independent_clock_domains_cdc_review_required |
| fast_setup | input_pixel | board27 | -0.414 | 2 | independent_clock_domains_cdc_review_required |
| fast_setup | cfg_clk | board27 | 0.996 | 0 | related_clock_domains_timed |
| fast_setup | ddrphy_sysclk | ddrphy_sysclk | 0.996 | 0 | same_clock |
| fast_setup | input_pixel | input_pixel | 1.016 | 0 | same_clock |
| fast_setup | ddrphy_sysclk | phy_dq_sysclk_0 | 2.526 | 0 | core_to_divided_phy_timed |
| fast_setup | ddrphy_sysclk | phy_dq_sysclk_1 | 2.735 | 0 | core_to_divided_phy_timed |
| fast_setup | phy_dq_sysclk_1 | ddrphy_sysclk | 4.080 | 0 | core_to_divided_phy_timed |
| fast_setup | phy_dq_sysclk_0 | ddrphy_sysclk | 4.822 | 0 | core_to_divided_phy_timed |
| fast_setup | rst_clk | rst_clk | 5.939 | 0 | same_clock |
| fast_setup | board27 | board27 | 33.222 | 0 | same_clock |
| fast_setup | cfg_clk | cfg_clk | 96.326 | 0 | same_clock |
| fast_hold | input_pixel | ddrphy_sysclk | -2.103 | 9 | independent_clock_domains_cdc_review_required |
| fast_hold | board27 | ddrphy_sysclk | -1.920 | 188 | independent_clock_domains_cdc_review_required |
| fast_hold | input_pixel | board27 | -0.185 | 1 | independent_clock_domains_cdc_review_required |
| fast_hold | ddrphy_sysclk | ddrphy_sysclk | 0.009 | 0 | same_clock |
| fast_hold | phy_dq_sysclk_1 | ddrphy_sysclk | 0.018 | 0 | core_to_divided_phy_timed |
| fast_hold | ddrphy_sysclk | phy_dq_sysclk_0 | 0.019 | 0 | core_to_divided_phy_timed |
| fast_hold | ddrphy_sysclk | phy_dq_sysclk_1 | 0.021 | 0 | core_to_divided_phy_timed |
| fast_hold | cfg_clk | board27 | 0.026 | 0 | related_clock_domains_timed |
| fast_hold | cfg_clk | cfg_clk | 0.104 | 0 | same_clock |
| fast_hold | input_pixel | input_pixel | 0.156 | 0 | same_clock |
| fast_hold | rst_clk | rst_clk | 0.163 | 0 | same_clock |
| fast_hold | board27 | board27 | 0.171 | 0 | same_clock |
| fast_hold | phy_dq_sysclk_0 | ddrphy_sysclk | 0.237 | 0 | core_to_divided_phy_timed |
| fast_hold | ddrphy_sysclk | board27 | 0.845 | 0 | independent_clock_domains_cdc_review_required |
| fast_hold | ddrphy_sysclk | input_pixel | 0.961 | 0 | independent_clock_domains_cdc_review_required |
| fast_recovery | board27 | input_pixel | -1.360 | 505 | independent_clock_domains_cdc_review_required |
| fast_recovery | board27 | ddrphy_sysclk | -1.314 | 841 | independent_clock_domains_cdc_review_required |
| fast_recovery | board27 | cfg_clk | 1.043 | 0 | related_clock_domains_timed |
| fast_recovery | ddrphy_sysclk | ddrphy_sysclk | 4.763 | 0 | same_clock |
| fast_recovery | rst_clk | rst_clk | 6.709 | 0 | same_clock |
| fast_recovery | board27 | board27 | 34.458 | 0 | same_clock |
| fast_recovery | cfg_clk | cfg_clk | 98.176 | 0 | same_clock |
| fast_removal | board27 | ddrphy_sysclk | -1.937 | 864 | independent_clock_domains_cdc_review_required |
| fast_removal | board27 | cfg_clk | 0.036 | 0 | related_clock_domains_timed |
| fast_removal | rst_clk | rst_clk | 0.269 | 0 | same_clock |
| fast_removal | board27 | input_pixel | 0.276 | 0 | independent_clock_domains_cdc_review_required |
| fast_removal | ddrphy_sysclk | ddrphy_sysclk | 0.301 | 0 | same_clock |
| fast_removal | cfg_clk | cfg_clk | 0.354 | 0 | same_clock |
| fast_removal | board27 | board27 | 0.497 | 0 | same_clock |
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
