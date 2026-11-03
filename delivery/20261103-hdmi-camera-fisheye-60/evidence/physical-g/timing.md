# Native timing: physical-g

BuildID `11037003`, source `7a246494adf458b607d430b9ebc60c13420f7f859352edb82ad6211e0a20eb8b`. Diagnostic scope; external IO, CDC and reset acceptance remain pending.

| Corner/check | Launch | Capture | Worst slack (ns) | Failing endpoints | Domain status |
| --- | --- | --- | ---: | ---: | --- |
| slow_setup | ddrphy_sysclk | input_pixel | -5.159 | 669 | independent_clock_domains_cdc_review_required |
| slow_setup | input_pixel | ddrphy_sysclk | -4.646 | 321 | independent_clock_domains_cdc_review_required |
| slow_setup | board27 | ddrphy_sysclk | -4.450 | 188 | independent_clock_domains_cdc_review_required |
| slow_setup | ddrphy_sysclk | board27 | -4.056 | 3 | independent_clock_domains_cdc_review_required |
| slow_setup | ddrphy_sysclk | ddrphy_sysclk | -1.929 | 2466 | same_clock |
| slow_setup | input_pixel | board27 | -0.906 | 2 | independent_clock_domains_cdc_review_required |
| slow_setup | input_pixel | input_pixel | -0.820 | 639 | same_clock |
| slow_setup | ddrphy_sysclk | phy_dq_sysclk_0 | -0.029 | 2 | core_to_divided_phy_timed |
| slow_setup | ddrphy_sysclk | phy_dq_sysclk_1 | 0.014 | 0 | core_to_divided_phy_timed |
| slow_setup | cfg_clk | board27 | 0.365 | 0 | related_clock_domains_timed |
| slow_setup | phy_dq_sysclk_1 | ddrphy_sysclk | 2.671 | 0 | core_to_divided_phy_timed |
| slow_setup | phy_dq_sysclk_0 | ddrphy_sysclk | 3.644 | 0 | core_to_divided_phy_timed |
| slow_setup | rst_clk | rst_clk | 4.438 | 0 | same_clock |
| slow_setup | board27 | board27 | 31.722 | 0 | same_clock |
| slow_setup | cfg_clk | cfg_clk | 93.804 | 0 | same_clock |
| slow_hold | input_pixel | ddrphy_sysclk | -1.957 | 9 | independent_clock_domains_cdc_review_required |
| slow_hold | board27 | ddrphy_sysclk | -1.811 | 180 | independent_clock_domains_cdc_review_required |
| slow_hold | input_pixel | board27 | -0.092 | 2 | independent_clock_domains_cdc_review_required |
| slow_hold | ddrphy_sysclk | ddrphy_sysclk | 0.020 | 0 | same_clock |
| slow_hold | cfg_clk | cfg_clk | 0.071 | 0 | same_clock |
| slow_hold | input_pixel | input_pixel | 0.218 | 0 | same_clock |
| slow_hold | rst_clk | rst_clk | 0.261 | 0 | same_clock |
| slow_hold | board27 | board27 | 0.279 | 0 | same_clock |
| slow_hold | cfg_clk | board27 | 0.342 | 0 | related_clock_domains_timed |
| slow_hold | ddrphy_sysclk | phy_dq_sysclk_0 | 0.370 | 0 | core_to_divided_phy_timed |
| slow_hold | ddrphy_sysclk | phy_dq_sysclk_1 | 0.386 | 0 | core_to_divided_phy_timed |
| slow_hold | phy_dq_sysclk_1 | ddrphy_sysclk | 0.460 | 0 | core_to_divided_phy_timed |
| slow_hold | ddrphy_sysclk | board27 | 0.615 | 0 | independent_clock_domains_cdc_review_required |
| slow_hold | ddrphy_sysclk | input_pixel | 0.759 | 0 | independent_clock_domains_cdc_review_required |
| slow_hold | phy_dq_sysclk_0 | ddrphy_sysclk | 0.762 | 0 | core_to_divided_phy_timed |
| slow_recovery | board27 | ddrphy_sysclk | -3.106 | 856 | independent_clock_domains_cdc_review_required |
| slow_recovery | board27 | input_pixel | -2.474 | 505 | independent_clock_domains_cdc_review_required |
| slow_recovery | board27 | cfg_clk | -0.694 | 5 | related_clock_domains_timed |
| slow_recovery | ddrphy_sysclk | ddrphy_sysclk | 2.111 | 0 | same_clock |
| slow_recovery | rst_clk | rst_clk | 5.285 | 0 | same_clock |
| slow_recovery | board27 | board27 | 33.399 | 0 | same_clock |
| slow_recovery | cfg_clk | cfg_clk | 96.921 | 0 | same_clock |
| slow_removal | board27 | ddrphy_sysclk | -1.864 | 856 | independent_clock_domains_cdc_review_required |
| slow_removal | board27 | cfg_clk | 0.317 | 0 | related_clock_domains_timed |
| slow_removal | board27 | input_pixel | 0.382 | 0 | independent_clock_domains_cdc_review_required |
| slow_removal | rst_clk | rst_clk | 0.388 | 0 | same_clock |
| slow_removal | cfg_clk | cfg_clk | 0.398 | 0 | same_clock |
| slow_removal | ddrphy_sysclk | ddrphy_sysclk | 0.400 | 0 | same_clock |
| slow_removal | board27 | board27 | 0.714 | 0 | same_clock |
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
| fast_setup | ddrphy_sysclk | input_pixel | -3.516 | 669 | independent_clock_domains_cdc_review_required |
| fast_setup | ddrphy_sysclk | board27 | -3.223 | 3 | independent_clock_domains_cdc_review_required |
| fast_setup | board27 | ddrphy_sysclk | -2.324 | 185 | independent_clock_domains_cdc_review_required |
| fast_setup | input_pixel | ddrphy_sysclk | -2.129 | 316 | independent_clock_domains_cdc_review_required |
| fast_setup | input_pixel | board27 | -0.285 | 2 | independent_clock_domains_cdc_review_required |
| fast_setup | cfg_clk | board27 | 1.445 | 0 | related_clock_domains_timed |
| fast_setup | ddrphy_sysclk | ddrphy_sysclk | 1.787 | 0 | same_clock |
| fast_setup | input_pixel | input_pixel | 2.150 | 0 | same_clock |
| fast_setup | ddrphy_sysclk | phy_dq_sysclk_0 | 2.578 | 0 | core_to_divided_phy_timed |
| fast_setup | ddrphy_sysclk | phy_dq_sysclk_1 | 2.629 | 0 | core_to_divided_phy_timed |
| fast_setup | phy_dq_sysclk_1 | ddrphy_sysclk | 4.163 | 0 | core_to_divided_phy_timed |
| fast_setup | phy_dq_sysclk_0 | ddrphy_sysclk | 4.980 | 0 | core_to_divided_phy_timed |
| fast_setup | rst_clk | rst_clk | 5.878 | 0 | same_clock |
| fast_setup | board27 | board27 | 33.837 | 0 | same_clock |
| fast_setup | cfg_clk | cfg_clk | 96.191 | 0 | same_clock |
| fast_hold | input_pixel | ddrphy_sysclk | -2.048 | 9 | independent_clock_domains_cdc_review_required |
| fast_hold | board27 | ddrphy_sysclk | -1.956 | 188 | independent_clock_domains_cdc_review_required |
| fast_hold | input_pixel | board27 | -0.095 | 2 | independent_clock_domains_cdc_review_required |
| fast_hold | ddrphy_sysclk | ddrphy_sysclk | 0.009 | 0 | same_clock |
| fast_hold | ddrphy_sysclk | phy_dq_sysclk_0 | 0.017 | 0 | core_to_divided_phy_timed |
| fast_hold | ddrphy_sysclk | phy_dq_sysclk_1 | 0.021 | 0 | core_to_divided_phy_timed |
| fast_hold | phy_dq_sysclk_1 | ddrphy_sysclk | 0.022 | 0 | core_to_divided_phy_timed |
| fast_hold | cfg_clk | cfg_clk | 0.042 | 0 | same_clock |
| fast_hold | cfg_clk | board27 | 0.125 | 0 | related_clock_domains_timed |
| fast_hold | input_pixel | input_pixel | 0.147 | 0 | same_clock |
| fast_hold | phy_dq_sysclk_0 | ddrphy_sysclk | 0.176 | 0 | core_to_divided_phy_timed |
| fast_hold | rst_clk | rst_clk | 0.179 | 0 | same_clock |
| fast_hold | board27 | board27 | 0.187 | 0 | same_clock |
| fast_hold | ddrphy_sysclk | board27 | 0.838 | 0 | independent_clock_domains_cdc_review_required |
| fast_hold | ddrphy_sysclk | input_pixel | 0.947 | 0 | independent_clock_domains_cdc_review_required |
| fast_recovery | board27 | ddrphy_sysclk | -1.310 | 856 | independent_clock_domains_cdc_review_required |
| fast_recovery | board27 | input_pixel | -1.255 | 505 | independent_clock_domains_cdc_review_required |
| fast_recovery | board27 | cfg_clk | 0.878 | 0 | related_clock_domains_timed |
| fast_recovery | ddrphy_sysclk | ddrphy_sysclk | 4.097 | 0 | same_clock |
| fast_recovery | rst_clk | rst_clk | 6.350 | 0 | same_clock |
| fast_recovery | board27 | board27 | 34.776 | 0 | same_clock |
| fast_recovery | cfg_clk | cfg_clk | 97.993 | 0 | same_clock |
| fast_removal | board27 | ddrphy_sysclk | -1.965 | 856 | independent_clock_domains_cdc_review_required |
| fast_removal | board27 | cfg_clk | 0.072 | 0 | related_clock_domains_timed |
| fast_removal | board27 | input_pixel | 0.254 | 0 | independent_clock_domains_cdc_review_required |
| fast_removal | rst_clk | rst_clk | 0.264 | 0 | same_clock |
| fast_removal | cfg_clk | cfg_clk | 0.276 | 0 | same_clock |
| fast_removal | ddrphy_sysclk | ddrphy_sysclk | 0.280 | 0 | same_clock |
| fast_removal | board27 | board27 | 0.491 | 0 | same_clock |
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
