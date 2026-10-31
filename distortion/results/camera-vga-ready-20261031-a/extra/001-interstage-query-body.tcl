# Query fragment only; parent runner must bind final ADF and initialize native STA.
# 1: ddr_ready_ref[0]
report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {ddr_ready_ref[0]/opit_0_L6Q_perm/CLK} -to {system_failed_ref[1]/opit_0_L6Q_LUT6DQL5Q_perm/I4}
# 2: captured_bit_ref[0]
report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {processed_bit_ref[1]/opit_0_L6Q_LUT6DQL5Q_perm/CLK} -to {heartbeat_count[0]/opit_0_L6Q_LUT6DQL5Q_perm/I4}
# 3: system/bank_core/engine/core/reset_sync[0]
report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {system/bank_core/engine/core/reset_sync[0]/opit_0_inv_srl/CLK} -to {system/bank_core/engine/core/reset_sync[1]_1/opit_0_inv/D}
# 4: system/bank_core/engine/core/reset_sync[0]
report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {system/bank_core/engine/core/reset_sync[0]/opit_0_inv_srl/CLK} -to {system/bank_core/engine/core/reset_sync_1_copy[1]/opit_0_inv/D}
# 5: system/bank_core/engine/core/reset_sync[0]
report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {system/bank_core/engine/core/reset_sync[0]/opit_0_inv_srl/CLK} -to {system/bank_core/engine/core/reset_sync_1_copy[1]_1/opit_0_inv/D}
# 6: system/bank_core/engine/core/reset_sync[0]
report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {system/bank_core/engine/core/reset_sync[0]/opit_0_inv_srl/CLK} -to {system/bank_core/engine/core/reset_sync_1_copy[1]_10/opit_0_inv/D}
# 7: system/bank_core/engine/core/reset_sync[0]
report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {system/bank_core/engine/core/reset_sync[0]/opit_0_inv_srl/CLK} -to {system/bank_core/engine/core/reset_sync_1_copy[1]_11/opit_0_inv/D}
# 8: system/bank_core/engine/core/reset_sync[0]
report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {system/bank_core/engine/core/reset_sync[0]/opit_0_inv_srl/CLK} -to {system/bank_core/engine/core/reset_sync_1_copy[1]_12/opit_0_inv/D}
# 9: system/bank_core/engine/core/reset_sync[0]
report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {system/bank_core/engine/core/reset_sync[0]/opit_0_inv_srl/CLK} -to {system/bank_core/engine/core/reset_sync_1_copy[1]_13/opit_0_inv/D}
# 10: system/bank_core/engine/core/reset_sync[0]
report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {system/bank_core/engine/core/reset_sync[0]/opit_0_inv_srl/CLK} -to {system/bank_core/engine/core/reset_sync_1_copy[1]_14/opit_0_inv/D}
# 11: system/bank_core/engine/core/reset_sync[0]
report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {system/bank_core/engine/core/reset_sync[0]/opit_0_inv_srl/CLK} -to {system/bank_core/engine/core/reset_sync_1_copy[1]_15/opit_0_inv/D}
# 12: system/bank_core/engine/core/reset_sync[0]
report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {system/bank_core/engine/core/reset_sync[0]/opit_0_inv_srl/CLK} -to {system/bank_core/engine/core/reset_sync_1_copy[1]_16/opit_0_inv/D}
# 13: system/bank_core/engine/core/reset_sync[0]
report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {system/bank_core/engine/core/reset_sync[0]/opit_0_inv_srl/CLK} -to {system/bank_core/engine/core/reset_sync_1_copy[1]_17/opit_0_inv/D}
# 14: system/bank_core/engine/core/reset_sync[0]
report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {system/bank_core/engine/core/reset_sync[0]/opit_0_inv_srl/CLK} -to {system/bank_core/engine/core/reset_sync_1_copy[1]_18/opit_0_inv/D}
# 15: system/bank_core/engine/core/reset_sync[0]
report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {system/bank_core/engine/core/reset_sync[0]/opit_0_inv_srl/CLK} -to {system/bank_core/engine/core/reset_sync_1_copy[1]_19/opit_0_inv/D}
# 16: system/bank_core/engine/core/reset_sync[0]
report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {system/bank_core/engine/core/reset_sync[0]/opit_0_inv_srl/CLK} -to {system/bank_core/engine/core/reset_sync_1_copy[1]_2/opit_0_inv/D}
# 17: system/bank_core/engine/core/reset_sync[0]
report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {system/bank_core/engine/core/reset_sync[0]/opit_0_inv_srl/CLK} -to {system/bank_core/engine/core/reset_sync_1_copy[1]_20/opit_0_inv/D}
# 18: system/bank_core/engine/core/reset_sync[0]
report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {system/bank_core/engine/core/reset_sync[0]/opit_0_inv_srl/CLK} -to {system/bank_core/engine/core/reset_sync_1_copy[1]_21/opit_0_inv/D}
# 19: system/bank_core/engine/core/reset_sync[0]
report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {system/bank_core/engine/core/reset_sync[0]/opit_0_inv_srl/CLK} -to {system/bank_core/engine/core/reset_sync_1_copy[1]_22/opit_0_inv/D}
# 20: system/bank_core/engine/core/reset_sync[0]
report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {system/bank_core/engine/core/reset_sync[0]/opit_0_inv_srl/CLK} -to {system/bank_core/engine/core/reset_sync_1_copy[1]_23/opit_0_inv/D}
# 21: system/bank_core/engine/core/reset_sync[0]
report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {system/bank_core/engine/core/reset_sync[0]/opit_0_inv_srl/CLK} -to {system/bank_core/engine/core/reset_sync_1_copy[1]_25/opit_0_inv/D}
# 22: system/bank_core/engine/core/reset_sync[0]
report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {system/bank_core/engine/core/reset_sync[0]/opit_0_inv_srl/CLK} -to {system/bank_core/engine/core/reset_sync_1_copy[1]_26/opit_0_inv/D}
# 23: system/bank_core/engine/core/reset_sync[0]
report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {system/bank_core/engine/core/reset_sync[0]/opit_0_inv_srl/CLK} -to {system/bank_core/engine/core/reset_sync_1_copy[1]_3/opit_0_inv/D}
# 24: system/bank_core/engine/core/reset_sync[0]
report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {system/bank_core/engine/core/reset_sync[0]/opit_0_inv_srl/CLK} -to {system/bank_core/engine/core/reset_sync_1_copy[1]_4/opit_0_inv/D}
# 25: system/bank_core/engine/core/reset_sync[0]
report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {system/bank_core/engine/core/reset_sync[0]/opit_0_inv_srl/CLK} -to {system/bank_core/engine/core/reset_sync_1_copy[1]_5/opit_0_inv/D}
# 26: system/bank_core/engine/core/reset_sync[0]
report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {system/bank_core/engine/core/reset_sync[0]/opit_0_inv_srl/CLK} -to {system/bank_core/engine/core/reset_sync_1_copy[1]_6/opit_0_inv/D}
# 27: system/bank_core/engine/core/reset_sync[0]
report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {system/bank_core/engine/core/reset_sync[0]/opit_0_inv_srl/CLK} -to {system/bank_core/engine/core/reset_sync_1_copy[1]_7/opit_0_inv/D}
# 28: system/bank_core/engine/core/reset_sync[0]
report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {system/bank_core/engine/core/reset_sync[0]/opit_0_inv_srl/CLK} -to {system/bank_core/engine/core/reset_sync_1_copy[1]_8/opit_0_inv/D}
# 29: system/bank_core/engine/core/reset_sync[0]
report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {system/bank_core/engine/core/reset_sync[0]/opit_0_inv_srl/CLK} -to {system/bank_core/engine/core/reset_sync_1_copy[1]_9/opit_0_inv/D}
# 30: system/input_link/input_dma/capture/enable_cam[0]
report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {system/input_link/input_dma/capture/enable_cam[0]/opit_0_L6Q_LUT6DL5Q_perm/CLK} -to {system/input_link/input_dma/capture/grant_sync[0]/opit_0_L6Q_LUT6DQL5Q_perm/I1}
# 31: system/input_link/input_dma/capture/grant_sync[0]
report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {system/input_link/input_dma/capture/grant_sync[0]/opit_0_L6Q_LUT6DQL5Q_perm/CLK} -to {system/input_link/input_dma/capture/grant_sync[1]/opit_0_L6Q_LUT6DQL5Q_perm/I4}
# 32: system/input_link/input_dma/capture/ack_sync[0]
report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {system/input_link/input_dma/capture/grant_sync[1]/opit_0_L6Q_LUT6DQL5Q_perm/CLK} -to {system/input_link/input_dma/capture/vs_d/opit_0_L6Q_LUT6DQL5Q_perm/I0}
# 33: processed_bit_ref[0]
report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {system_failed_ref[0]/opit_0_L6Q_LUT6DQL5Q_perm/CLK} -to {processed_bit_ref[1]/opit_0_L6Q_LUT6DQL5Q_perm/I2}
# 34: system_failed_ref[0]
report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {system_failed_ref[0]/opit_0_L6Q_LUT6DQL5Q_perm/CLK} -to {system_failed_ref[1]/opit_0_L6Q_LUT6DQL5Q_perm/I2}
# 35: video_lock_ref[0]
report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {video_lock_ref[0]/opit_0_L6Q_perm/CLK} -to {video_lock_ref[1]/opit_0_L6Q_perm/I3}
