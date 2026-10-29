set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676
add_design {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/build/hdmi-uart-diagnostic/input-cdc-chain-delay-1030-c/dummy.v}
if {[info script] ne {}} {
 mpnr -input {D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/build/hdmi-uart-diagnostic/input-cdc-chain-delay-1030-c/input.adf}
 puts {CDC_CHAIN_BEGIN 0}
 get_path_delay -from {input_status/geometry/edge_meta[0]/opit_0/Q} -to {input_status/geometry/edge_sync[0]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 0}
 puts {CDC_CHAIN_BEGIN 1}
 get_path_delay -from {input_status/geometry/edge_meta[1]/opit_0/Q} -to {input_status/geometry/edge_sync[1]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 1}
 puts {CDC_CHAIN_BEGIN 2}
 get_path_delay -from {input_status/geometry/edge_meta[2]/opit_0/Q} -to {input_status/geometry/edge_sync[2]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 2}
 puts {CDC_CHAIN_BEGIN 3}
 get_path_delay -from {input_status/geometry/edge_meta[3]/opit_0/Q} -to {input_status/geometry/edge_sync[3]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 3}
 puts {CDC_CHAIN_BEGIN 4}
 get_path_delay -from {input_status/geometry/edge_meta[4]/opit_0/Q} -to {input_status/geometry/edge_sync[4]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 4}
 puts {CDC_CHAIN_BEGIN 5}
 get_path_delay -from {input_status/geometry/edge_meta[5]/opit_0/Q} -to {input_status/geometry/edge_sync[5]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 5}
 puts {CDC_CHAIN_BEGIN 6}
 get_path_delay -from {input_status/geometry/edge_meta[6]/opit_0/Q} -to {input_status/geometry/edge_sync[6]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 6}
 puts {CDC_CHAIN_BEGIN 7}
 get_path_delay -from {input_status/geometry/edge_meta[7]/opit_0/Q} -to {input_status/geometry/edge_sync[7]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 7}
 puts {CDC_CHAIN_BEGIN 8}
 get_path_delay -from {input_status/geometry/edge_meta[8]/opit_0/Q} -to {input_status/geometry/edge_sync[8]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 8}
 puts {CDC_CHAIN_BEGIN 9}
 get_path_delay -from {input_status/geometry/edge_meta[9]/opit_0/Q} -to {input_status/geometry/edge_sync[9]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 9}
 puts {CDC_CHAIN_BEGIN 10}
 get_path_delay -from {input_status/geometry/edge_meta[10]/opit_0/Q} -to {input_status/geometry/edge_sync[10]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 10}
 puts {CDC_CHAIN_BEGIN 11}
 get_path_delay -from {input_status/geometry/edge_meta[11]/opit_0/Q} -to {input_status/geometry/edge_sync[11]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 11}
 puts {CDC_CHAIN_BEGIN 12}
 get_path_delay -from {input_status/geometry/edge_meta[12]/opit_0/Q} -to {input_status/geometry/edge_sync[12]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 12}
 puts {CDC_CHAIN_BEGIN 13}
 get_path_delay -from {input_status/geometry/edge_meta[13]/opit_0/Q} -to {input_status/geometry/edge_sync[13]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 13}
 puts {CDC_CHAIN_BEGIN 14}
 get_path_delay -from {input_status/geometry/edge_meta[14]/opit_0/Q} -to {input_status/geometry/edge_sync[14]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 14}
 puts {CDC_CHAIN_BEGIN 15}
 get_path_delay -from {input_status/geometry/edge_meta[15]/opit_0/Q} -to {input_status/geometry/edge_sync[15]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 15}
 puts {CDC_CHAIN_BEGIN 16}
 get_path_delay -from {input_status/geometry/edge_meta[16]/opit_0/Q} -to {input_status/geometry/edge_sync[16]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 16}
 puts {CDC_CHAIN_BEGIN 17}
 get_path_delay -from {input_status/geometry/edge_meta[17]/opit_0/Q} -to {input_status/geometry/edge_sync[17]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 17}
 puts {CDC_CHAIN_BEGIN 18}
 get_path_delay -from {input_status/geometry/edge_meta[18]/opit_0/Q} -to {input_status/geometry/edge_sync[18]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 18}
 puts {CDC_CHAIN_BEGIN 19}
 get_path_delay -from {input_status/geometry/edge_meta[19]/opit_0/Q} -to {input_status/geometry/edge_sync[19]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 19}
 puts {CDC_CHAIN_BEGIN 20}
 get_path_delay -from {input_status/geometry/edge_meta[20]/opit_0/Q} -to {input_status/geometry/edge_sync[20]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 20}
 puts {CDC_CHAIN_BEGIN 21}
 get_path_delay -from {input_status/geometry/edge_meta[21]/opit_0/Q} -to {input_status/geometry/edge_sync[21]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 21}
 puts {CDC_CHAIN_BEGIN 22}
 get_path_delay -from {input_status/geometry/edge_meta[22]/opit_0/Q} -to {input_status/geometry/edge_sync[22]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 22}
 puts {CDC_CHAIN_BEGIN 23}
 get_path_delay -from {input_status/geometry/edge_meta[23]/opit_0/Q} -to {input_status/geometry/edge_sync[23]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 23}
 puts {CDC_CHAIN_BEGIN 24}
 get_path_delay -from {input_status/geometry/edge_meta[24]/opit_0/Q} -to {input_status/geometry/edge_sync[24]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 24}
 puts {CDC_CHAIN_BEGIN 25}
 get_path_delay -from {input_status/geometry/edge_meta[25]/opit_0/Q} -to {input_status/geometry/edge_sync[25]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 25}
 puts {CDC_CHAIN_BEGIN 26}
 get_path_delay -from {input_status/geometry/edge_meta[26]/opit_0/Q} -to {input_status/geometry/edge_sync[26]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 26}
 puts {CDC_CHAIN_BEGIN 27}
 get_path_delay -from {input_status/geometry/edge_meta[27]/opit_0/Q} -to {input_status/geometry/edge_sync[27]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 27}
 puts {CDC_CHAIN_BEGIN 28}
 get_path_delay -from {input_status/geometry/edge_meta[28]/opit_0/Q} -to {input_status/geometry/edge_sync[28]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 28}
 puts {CDC_CHAIN_BEGIN 29}
 get_path_delay -from {input_status/geometry/edge_meta[29]/opit_0/Q} -to {input_status/geometry/edge_sync[29]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 29}
 puts {CDC_CHAIN_BEGIN 30}
 get_path_delay -from {input_status/geometry/edge_meta[30]/opit_0/Q} -to {input_status/geometry/edge_sync[30]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 30}
 puts {CDC_CHAIN_BEGIN 31}
 get_path_delay -from {input_status/geometry/edge_meta[31]/opit_0/Q} -to {input_status/geometry/edge_sync[31]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 31}
 puts {CDC_CHAIN_BEGIN 32}
 get_path_delay -from {input_status/geometry/href_meta[0]/opit_0/Q} -to {input_status/geometry/href_sync[0]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 32}
 puts {CDC_CHAIN_BEGIN 33}
 get_path_delay -from {input_status/geometry/href_meta[1]/opit_0/Q} -to {input_status/geometry/href_sync[1]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 33}
 puts {CDC_CHAIN_BEGIN 34}
 get_path_delay -from {input_status/geometry/href_meta[2]/opit_0/Q} -to {input_status/geometry/href_sync[2]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 34}
 puts {CDC_CHAIN_BEGIN 35}
 get_path_delay -from {input_status/geometry/href_meta[3]/opit_0/Q} -to {input_status/geometry/href_sync[3]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 35}
 puts {CDC_CHAIN_BEGIN 36}
 get_path_delay -from {input_status/geometry/href_meta[4]/opit_0/Q} -to {input_status/geometry/href_sync[4]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 36}
 puts {CDC_CHAIN_BEGIN 37}
 get_path_delay -from {input_status/geometry/href_meta[5]/opit_0/Q} -to {input_status/geometry/href_sync[5]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 37}
 puts {CDC_CHAIN_BEGIN 38}
 get_path_delay -from {input_status/geometry/href_meta[6]/opit_0/Q} -to {input_status/geometry/href_sync[6]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 38}
 puts {CDC_CHAIN_BEGIN 39}
 get_path_delay -from {input_status/geometry/href_meta[7]/opit_0/Q} -to {input_status/geometry/href_sync[7]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 39}
 puts {CDC_CHAIN_BEGIN 40}
 get_path_delay -from {input_status/geometry/href_meta[8]/opit_0/Q} -to {input_status/geometry/href_sync[8]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 40}
 puts {CDC_CHAIN_BEGIN 41}
 get_path_delay -from {input_status/geometry/href_meta[9]/opit_0/Q} -to {input_status/geometry/href_sync[9]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 41}
 puts {CDC_CHAIN_BEGIN 42}
 get_path_delay -from {input_status/geometry/href_meta[10]/opit_0/Q} -to {input_status/geometry/href_sync[10]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 42}
 puts {CDC_CHAIN_BEGIN 43}
 get_path_delay -from {input_status/geometry/href_meta[11]/opit_0/Q} -to {input_status/geometry/href_sync[11]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 43}
 puts {CDC_CHAIN_BEGIN 44}
 get_path_delay -from {input_status/geometry/href_meta[12]/opit_0/Q} -to {input_status/geometry/href_sync[12]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 44}
 puts {CDC_CHAIN_BEGIN 45}
 get_path_delay -from {input_status/geometry/href_meta[13]/opit_0/Q} -to {input_status/geometry/href_sync[13]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 45}
 puts {CDC_CHAIN_BEGIN 46}
 get_path_delay -from {input_status/geometry/href_meta[14]/opit_0/Q} -to {input_status/geometry/href_sync[14]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 46}
 puts {CDC_CHAIN_BEGIN 47}
 get_path_delay -from {input_status/geometry/href_meta[15]/opit_0/Q} -to {input_status/geometry/href_sync[15]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 47}
 puts {CDC_CHAIN_BEGIN 48}
 get_path_delay -from {input_status/geometry/vs_meta[0]/opit_0/Q} -to {input_status/geometry/vs_sync[0]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 48}
 puts {CDC_CHAIN_BEGIN 49}
 get_path_delay -from {input_status/geometry/vs_meta[1]/opit_0/Q} -to {input_status/geometry/vs_sync[1]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 49}
 puts {CDC_CHAIN_BEGIN 50}
 get_path_delay -from {input_status/geometry/vs_meta[2]/opit_0/Q} -to {input_status/geometry/vs_sync[2]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 50}
 puts {CDC_CHAIN_BEGIN 51}
 get_path_delay -from {input_status/geometry/vs_meta[3]/opit_0/Q} -to {input_status/geometry/vs_sync[3]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 51}
 puts {CDC_CHAIN_BEGIN 52}
 get_path_delay -from {input_status/geometry/vs_meta[4]/opit_0/Q} -to {input_status/geometry/vs_sync[4]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 52}
 puts {CDC_CHAIN_BEGIN 53}
 get_path_delay -from {input_status/geometry/vs_meta[5]/opit_0/Q} -to {input_status/geometry/vs_sync[5]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 53}
 puts {CDC_CHAIN_BEGIN 54}
 get_path_delay -from {input_status/geometry/vs_meta[6]/opit_0/Q} -to {input_status/geometry/vs_sync[6]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 54}
 puts {CDC_CHAIN_BEGIN 55}
 get_path_delay -from {input_status/geometry/vs_meta[7]/opit_0/Q} -to {input_status/geometry/vs_sync[7]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 55}
 puts {CDC_CHAIN_BEGIN 56}
 get_path_delay -from {input_status/geometry/vs_meta[8]/opit_0/Q} -to {input_status/geometry/vs_sync[8]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 56}
 puts {CDC_CHAIN_BEGIN 57}
 get_path_delay -from {input_status/geometry/vs_meta[9]/opit_0/Q} -to {input_status/geometry/vs_sync[9]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 57}
 puts {CDC_CHAIN_BEGIN 58}
 get_path_delay -from {input_status/geometry/vs_meta[10]/opit_0/Q} -to {input_status/geometry/vs_sync[10]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 58}
 puts {CDC_CHAIN_BEGIN 59}
 get_path_delay -from {input_status/geometry/vs_meta[11]/opit_0/Q} -to {input_status/geometry/vs_sync[11]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 59}
 puts {CDC_CHAIN_BEGIN 60}
 get_path_delay -from {input_status/geometry/vs_meta[12]/opit_0/Q} -to {input_status/geometry/vs_sync[12]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 60}
 puts {CDC_CHAIN_BEGIN 61}
 get_path_delay -from {input_status/geometry/vs_meta[13]/opit_0/Q} -to {input_status/geometry/vs_sync[13]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 61}
 puts {CDC_CHAIN_BEGIN 62}
 get_path_delay -from {input_status/geometry/vs_meta[14]/opit_0/Q} -to {input_status/geometry/vs_sync[14]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 62}
 puts {CDC_CHAIN_BEGIN 63}
 get_path_delay -from {input_status/geometry/vs_meta[15]/opit_0/Q} -to {input_status/geometry/vs_sync[15]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 63}
 puts {CDC_CHAIN_BEGIN 64}
 get_path_delay -from {input_status/p_reset[0]/opit_0/Q} -to {input_status/p_reset[1]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 64}
 puts {CDC_CHAIN_BEGIN 65}
 get_path_delay -from {input_status/r_reset[0]/opit_0/Q} -to {input_status/r_reset[1]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 65}
 puts {CDC_CHAIN_BEGIN 66}
 get_path_delay -from {input_status/polarity_sync[0]/opit_0_inv/Q} -to {input_status/polarity_sync[1]/opit_0_inv/D} -max_path 1
 puts {CDC_CHAIN_END 66}
 puts {CDC_CHAIN_BEGIN 67}
 get_path_delay -from {input_status/polarity_sync[1]/opit_0_inv/Q} -to {input_status/polarity_sync[2]/opit_0_inv/D} -max_path 1
 puts {CDC_CHAIN_END 67}
 puts {CDC_CHAIN_BEGIN 68}
 get_path_delay -from {input_status/hs_level_sync[0]/opit_0_inv/Q} -to {input_status/hs_level_sync[1]/opit_0_inv/D} -max_path 1
 puts {CDC_CHAIN_END 68}
 puts {CDC_CHAIN_BEGIN 69}
 get_path_delay -from {input_status/vs_level_sync[0]/opit_0_inv/Q} -to {input_status/vs_level_sync[1]/opit_0_inv/D} -max_path 1
 puts {CDC_CHAIN_END 69}
 puts {CDC_CHAIN_BEGIN 70}
 get_path_delay -from {input_status/timing_good_sync[0]/opit_0_inv/Q} -to {input_status/timing_good_sync[1]/opit_0_inv/D} -max_path 1
 puts {CDC_CHAIN_END 70}
 puts {CDC_CHAIN_BEGIN 71}
 get_path_delay -from {input_status/timing_bad_sync[0]/opit_0_inv/Q} -to {input_status/timing_bad_sync[1]/opit_0_inv/D} -max_path 1
 puts {CDC_CHAIN_END 71}
 puts {CDC_CHAIN_BEGIN 72}
 get_path_delay -from {input_status/geometry/ack_sync[0]/opit_0/Q} -to {input_status/geometry/ack_sync[1]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 72}
 puts {CDC_CHAIN_BEGIN 73}
 get_path_delay -from {input_status/geometry/failed_sync[0]/opit_0/Q} -to {input_status/geometry/failed_sync[1]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 73}
 puts {CDC_CHAIN_BEGIN 74}
 get_path_delay -from {input_status/geometry/healthy_sync[0]/opit_0/Q} -to {input_status/geometry/healthy_sync[1]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 74}
 puts {CDC_CHAIN_BEGIN 75}
 get_path_delay -from {input_status/geometry/p_enable[0]/opit_0_inv/Q} -to {input_status/geometry/p_enable[1]/opit_0_inv/D} -max_path 1
 puts {CDC_CHAIN_END 75}
 puts {CDC_CHAIN_BEGIN 76}
 get_path_delay -from {input_status/geometry/p_reset[0]/opit_0/Q} -to {input_status/geometry/p_reset[1]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 76}
 puts {CDC_CHAIN_BEGIN 77}
 get_path_delay -from {input_status/geometry/r_enable[0]/opit_0_inv/Q} -to {input_status/geometry/r_enable[1]/opit_0_inv/D} -max_path 1
 puts {CDC_CHAIN_END 77}
 puts {CDC_CHAIN_BEGIN 78}
 get_path_delay -from {input_status/geometry/r_reset[0]/opit_0/Q} -to {input_status/geometry/r_reset[1]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 78}
 puts {CDC_CHAIN_BEGIN 79}
 get_path_delay -from {input_status/geometry/request_sync[0]/opit_0/Q} -to {input_status/geometry/request_sync[1]/opit_0/D} -max_path 1
 puts {CDC_CHAIN_END 79}
 puts {CDC_CHAIN_BEGIN 80}
 get_path_delay -from {input_status/geometry/source_running_sync[0]/opit_0_inv/Q} -to {input_status/geometry/source_running_sync[1]/opit_0_inv/D} -max_path 1
 puts {CDC_CHAIN_END 80}
 puts {CDC_CHAIN_QUERY_COMPLETE}
 flush stdout
}
