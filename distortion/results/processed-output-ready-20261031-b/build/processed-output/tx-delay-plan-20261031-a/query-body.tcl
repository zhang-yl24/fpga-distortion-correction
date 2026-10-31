puts {TX_DELAY_0000_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/b[0]/opit_0_L8Q_perm/CLK} -min -max_path 8
puts {TX_DELAY_0000_END}
puts {TX_DELAY_0001_BEGIN}
get_path_delay -rise_from {system/output_video/b[0]/opit_0_L8Q_perm/CLK} -rise_to {b_out[0]} -min -max_path 8
puts {TX_DELAY_0001_END}
puts {TX_DELAY_0002_BEGIN}
get_path_delay -rise_from {system/output_video/b[0]/opit_0_L8Q_perm/CLK} -fall_to {b_out[0]} -min -max_path 8
puts {TX_DELAY_0002_END}
puts {TX_DELAY_0003_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/b[1]/opit_0_L8Q_perm/CLK} -min -max_path 8
puts {TX_DELAY_0003_END}
puts {TX_DELAY_0004_BEGIN}
get_path_delay -rise_from {system/output_video/b[1]/opit_0_L8Q_perm/CLK} -rise_to {b_out[1]} -min -max_path 8
puts {TX_DELAY_0004_END}
puts {TX_DELAY_0005_BEGIN}
get_path_delay -rise_from {system/output_video/b[1]/opit_0_L8Q_perm/CLK} -fall_to {b_out[1]} -min -max_path 8
puts {TX_DELAY_0005_END}
puts {TX_DELAY_0006_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/b[2]/opit_0_L8Q_perm/CLK} -min -max_path 8
puts {TX_DELAY_0006_END}
puts {TX_DELAY_0007_BEGIN}
get_path_delay -rise_from {system/output_video/b[2]/opit_0_L8Q_perm/CLK} -rise_to {b_out[2]} -min -max_path 8
puts {TX_DELAY_0007_END}
puts {TX_DELAY_0008_BEGIN}
get_path_delay -rise_from {system/output_video/b[2]/opit_0_L8Q_perm/CLK} -fall_to {b_out[2]} -min -max_path 8
puts {TX_DELAY_0008_END}
puts {TX_DELAY_0009_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/b[3]/opit_0_L8Q_perm/CLK} -min -max_path 8
puts {TX_DELAY_0009_END}
puts {TX_DELAY_0010_BEGIN}
get_path_delay -rise_from {system/output_video/b[3]/opit_0_L8Q_perm/CLK} -rise_to {b_out[3]} -min -max_path 8
puts {TX_DELAY_0010_END}
puts {TX_DELAY_0011_BEGIN}
get_path_delay -rise_from {system/output_video/b[3]/opit_0_L8Q_perm/CLK} -fall_to {b_out[3]} -min -max_path 8
puts {TX_DELAY_0011_END}
puts {TX_DELAY_0012_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/b[4]/opit_0_L8Q_perm/CLK} -min -max_path 8
puts {TX_DELAY_0012_END}
puts {TX_DELAY_0013_BEGIN}
get_path_delay -rise_from {system/output_video/b[4]/opit_0_L8Q_perm/CLK} -rise_to {b_out[4]} -min -max_path 8
puts {TX_DELAY_0013_END}
puts {TX_DELAY_0014_BEGIN}
get_path_delay -rise_from {system/output_video/b[4]/opit_0_L8Q_perm/CLK} -fall_to {b_out[4]} -min -max_path 8
puts {TX_DELAY_0014_END}
puts {TX_DELAY_0015_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/b[0]/opit_0_L8Q_perm/CLK} -min -max_path 8
puts {TX_DELAY_0015_END}
puts {TX_DELAY_0016_BEGIN}
get_path_delay -rise_from {system/output_video/b[0]/opit_0_L8Q_perm/CLK} -rise_to {b_out[5]} -min -max_path 8
puts {TX_DELAY_0016_END}
puts {TX_DELAY_0017_BEGIN}
get_path_delay -rise_from {system/output_video/b[0]/opit_0_L8Q_perm/CLK} -fall_to {b_out[5]} -min -max_path 8
puts {TX_DELAY_0017_END}
puts {TX_DELAY_0018_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/b[1]/opit_0_L8Q_perm/CLK} -min -max_path 8
puts {TX_DELAY_0018_END}
puts {TX_DELAY_0019_BEGIN}
get_path_delay -rise_from {system/output_video/b[1]/opit_0_L8Q_perm/CLK} -rise_to {b_out[6]} -min -max_path 8
puts {TX_DELAY_0019_END}
puts {TX_DELAY_0020_BEGIN}
get_path_delay -rise_from {system/output_video/b[1]/opit_0_L8Q_perm/CLK} -fall_to {b_out[6]} -min -max_path 8
puts {TX_DELAY_0020_END}
puts {TX_DELAY_0021_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/b[2]/opit_0_L8Q_perm/CLK} -min -max_path 8
puts {TX_DELAY_0021_END}
puts {TX_DELAY_0022_BEGIN}
get_path_delay -rise_from {system/output_video/b[2]/opit_0_L8Q_perm/CLK} -rise_to {b_out[7]} -min -max_path 8
puts {TX_DELAY_0022_END}
puts {TX_DELAY_0023_BEGIN}
get_path_delay -rise_from {system/output_video/b[2]/opit_0_L8Q_perm/CLK} -fall_to {b_out[7]} -min -max_path 8
puts {TX_DELAY_0023_END}
puts {TX_DELAY_0024_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/de/opit_0_inv_L6Q_perm/CLK} -min -max_path 8
puts {TX_DELAY_0024_END}
puts {TX_DELAY_0025_BEGIN}
get_path_delay -rise_from {system/output_video/de/opit_0_inv_L6Q_perm/CLK} -rise_to {de_out} -min -max_path 8
puts {TX_DELAY_0025_END}
puts {TX_DELAY_0026_BEGIN}
get_path_delay -rise_from {system/output_video/de/opit_0_inv_L6Q_perm/CLK} -fall_to {de_out} -min -max_path 8
puts {TX_DELAY_0026_END}
puts {TX_DELAY_0027_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/g[0]/opit_0_L8Q_perm/CLK} -min -max_path 8
puts {TX_DELAY_0027_END}
puts {TX_DELAY_0028_BEGIN}
get_path_delay -rise_from {system/output_video/g[0]/opit_0_L8Q_perm/CLK} -rise_to {g_out[0]} -min -max_path 8
puts {TX_DELAY_0028_END}
puts {TX_DELAY_0029_BEGIN}
get_path_delay -rise_from {system/output_video/g[0]/opit_0_L8Q_perm/CLK} -fall_to {g_out[0]} -min -max_path 8
puts {TX_DELAY_0029_END}
puts {TX_DELAY_0030_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/g[1]/opit_0_L8Q_perm/CLK} -min -max_path 8
puts {TX_DELAY_0030_END}
puts {TX_DELAY_0031_BEGIN}
get_path_delay -rise_from {system/output_video/g[1]/opit_0_L8Q_perm/CLK} -rise_to {g_out[1]} -min -max_path 8
puts {TX_DELAY_0031_END}
puts {TX_DELAY_0032_BEGIN}
get_path_delay -rise_from {system/output_video/g[1]/opit_0_L8Q_perm/CLK} -fall_to {g_out[1]} -min -max_path 8
puts {TX_DELAY_0032_END}
puts {TX_DELAY_0033_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/g[2]/opit_0_L8Q_perm/CLK} -min -max_path 8
puts {TX_DELAY_0033_END}
puts {TX_DELAY_0034_BEGIN}
get_path_delay -rise_from {system/output_video/g[2]/opit_0_L8Q_perm/CLK} -rise_to {g_out[2]} -min -max_path 8
puts {TX_DELAY_0034_END}
puts {TX_DELAY_0035_BEGIN}
get_path_delay -rise_from {system/output_video/g[2]/opit_0_L8Q_perm/CLK} -fall_to {g_out[2]} -min -max_path 8
puts {TX_DELAY_0035_END}
puts {TX_DELAY_0036_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/g[3]/opit_0_L8Q_perm/CLK} -min -max_path 8
puts {TX_DELAY_0036_END}
puts {TX_DELAY_0037_BEGIN}
get_path_delay -rise_from {system/output_video/g[3]/opit_0_L8Q_perm/CLK} -rise_to {g_out[3]} -min -max_path 8
puts {TX_DELAY_0037_END}
puts {TX_DELAY_0038_BEGIN}
get_path_delay -rise_from {system/output_video/g[3]/opit_0_L8Q_perm/CLK} -fall_to {g_out[3]} -min -max_path 8
puts {TX_DELAY_0038_END}
puts {TX_DELAY_0039_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/g[4]/opit_0_L8Q_perm/CLK} -min -max_path 8
puts {TX_DELAY_0039_END}
puts {TX_DELAY_0040_BEGIN}
get_path_delay -rise_from {system/output_video/g[4]/opit_0_L8Q_perm/CLK} -rise_to {g_out[4]} -min -max_path 8
puts {TX_DELAY_0040_END}
puts {TX_DELAY_0041_BEGIN}
get_path_delay -rise_from {system/output_video/g[4]/opit_0_L8Q_perm/CLK} -fall_to {g_out[4]} -min -max_path 8
puts {TX_DELAY_0041_END}
puts {TX_DELAY_0042_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/g[5]/opit_0_L8Q_perm/CLK} -min -max_path 8
puts {TX_DELAY_0042_END}
puts {TX_DELAY_0043_BEGIN}
get_path_delay -rise_from {system/output_video/g[5]/opit_0_L8Q_perm/CLK} -rise_to {g_out[5]} -min -max_path 8
puts {TX_DELAY_0043_END}
puts {TX_DELAY_0044_BEGIN}
get_path_delay -rise_from {system/output_video/g[5]/opit_0_L8Q_perm/CLK} -fall_to {g_out[5]} -min -max_path 8
puts {TX_DELAY_0044_END}
puts {TX_DELAY_0045_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/g[0]/opit_0_L8Q_perm/CLK} -min -max_path 8
puts {TX_DELAY_0045_END}
puts {TX_DELAY_0046_BEGIN}
get_path_delay -rise_from {system/output_video/g[0]/opit_0_L8Q_perm/CLK} -rise_to {g_out[6]} -min -max_path 8
puts {TX_DELAY_0046_END}
puts {TX_DELAY_0047_BEGIN}
get_path_delay -rise_from {system/output_video/g[0]/opit_0_L8Q_perm/CLK} -fall_to {g_out[6]} -min -max_path 8
puts {TX_DELAY_0047_END}
puts {TX_DELAY_0048_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/g[1]/opit_0_L8Q_perm/CLK} -min -max_path 8
puts {TX_DELAY_0048_END}
puts {TX_DELAY_0049_BEGIN}
get_path_delay -rise_from {system/output_video/g[1]/opit_0_L8Q_perm/CLK} -rise_to {g_out[7]} -min -max_path 8
puts {TX_DELAY_0049_END}
puts {TX_DELAY_0050_BEGIN}
get_path_delay -rise_from {system/output_video/g[1]/opit_0_L8Q_perm/CLK} -fall_to {g_out[7]} -min -max_path 8
puts {TX_DELAY_0050_END}
puts {TX_DELAY_0051_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/hs/opit_0_inv_L6Q_perm/CLK} -min -max_path 8
puts {TX_DELAY_0051_END}
puts {TX_DELAY_0052_BEGIN}
get_path_delay -rise_from {system/output_video/hs/opit_0_inv_L6Q_perm/CLK} -rise_to {hs_out} -min -max_path 8
puts {TX_DELAY_0052_END}
puts {TX_DELAY_0053_BEGIN}
get_path_delay -rise_from {system/output_video/hs/opit_0_inv_L6Q_perm/CLK} -fall_to {hs_out} -min -max_path 8
puts {TX_DELAY_0053_END}
puts {TX_DELAY_0054_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/r[0]/opit_0_L8Q_perm/CLK} -min -max_path 8
puts {TX_DELAY_0054_END}
puts {TX_DELAY_0055_BEGIN}
get_path_delay -rise_from {system/output_video/r[0]/opit_0_L8Q_perm/CLK} -rise_to {r_out[0]} -min -max_path 8
puts {TX_DELAY_0055_END}
puts {TX_DELAY_0056_BEGIN}
get_path_delay -rise_from {system/output_video/r[0]/opit_0_L8Q_perm/CLK} -fall_to {r_out[0]} -min -max_path 8
puts {TX_DELAY_0056_END}
puts {TX_DELAY_0057_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/r[1]/opit_0_L8Q_perm/CLK} -min -max_path 8
puts {TX_DELAY_0057_END}
puts {TX_DELAY_0058_BEGIN}
get_path_delay -rise_from {system/output_video/r[1]/opit_0_L8Q_perm/CLK} -rise_to {r_out[1]} -min -max_path 8
puts {TX_DELAY_0058_END}
puts {TX_DELAY_0059_BEGIN}
get_path_delay -rise_from {system/output_video/r[1]/opit_0_L8Q_perm/CLK} -fall_to {r_out[1]} -min -max_path 8
puts {TX_DELAY_0059_END}
puts {TX_DELAY_0060_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/r[2]/opit_0_L8Q_perm/CLK} -min -max_path 8
puts {TX_DELAY_0060_END}
puts {TX_DELAY_0061_BEGIN}
get_path_delay -rise_from {system/output_video/r[2]/opit_0_L8Q_perm/CLK} -rise_to {r_out[2]} -min -max_path 8
puts {TX_DELAY_0061_END}
puts {TX_DELAY_0062_BEGIN}
get_path_delay -rise_from {system/output_video/r[2]/opit_0_L8Q_perm/CLK} -fall_to {r_out[2]} -min -max_path 8
puts {TX_DELAY_0062_END}
puts {TX_DELAY_0063_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/r[3]/opit_0_L8Q_perm/CLK} -min -max_path 8
puts {TX_DELAY_0063_END}
puts {TX_DELAY_0064_BEGIN}
get_path_delay -rise_from {system/output_video/r[3]/opit_0_L8Q_perm/CLK} -rise_to {r_out[3]} -min -max_path 8
puts {TX_DELAY_0064_END}
puts {TX_DELAY_0065_BEGIN}
get_path_delay -rise_from {system/output_video/r[3]/opit_0_L8Q_perm/CLK} -fall_to {r_out[3]} -min -max_path 8
puts {TX_DELAY_0065_END}
puts {TX_DELAY_0066_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/r[4]/opit_0_L8Q_perm/CLK} -min -max_path 8
puts {TX_DELAY_0066_END}
puts {TX_DELAY_0067_BEGIN}
get_path_delay -rise_from {system/output_video/r[4]/opit_0_L8Q_perm/CLK} -rise_to {r_out[4]} -min -max_path 8
puts {TX_DELAY_0067_END}
puts {TX_DELAY_0068_BEGIN}
get_path_delay -rise_from {system/output_video/r[4]/opit_0_L8Q_perm/CLK} -fall_to {r_out[4]} -min -max_path 8
puts {TX_DELAY_0068_END}
puts {TX_DELAY_0069_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/r[0]/opit_0_L8Q_perm/CLK} -min -max_path 8
puts {TX_DELAY_0069_END}
puts {TX_DELAY_0070_BEGIN}
get_path_delay -rise_from {system/output_video/r[0]/opit_0_L8Q_perm/CLK} -rise_to {r_out[5]} -min -max_path 8
puts {TX_DELAY_0070_END}
puts {TX_DELAY_0071_BEGIN}
get_path_delay -rise_from {system/output_video/r[0]/opit_0_L8Q_perm/CLK} -fall_to {r_out[5]} -min -max_path 8
puts {TX_DELAY_0071_END}
puts {TX_DELAY_0072_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/r[1]/opit_0_L8Q_perm/CLK} -min -max_path 8
puts {TX_DELAY_0072_END}
puts {TX_DELAY_0073_BEGIN}
get_path_delay -rise_from {system/output_video/r[1]/opit_0_L8Q_perm/CLK} -rise_to {r_out[6]} -min -max_path 8
puts {TX_DELAY_0073_END}
puts {TX_DELAY_0074_BEGIN}
get_path_delay -rise_from {system/output_video/r[1]/opit_0_L8Q_perm/CLK} -fall_to {r_out[6]} -min -max_path 8
puts {TX_DELAY_0074_END}
puts {TX_DELAY_0075_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/r[2]/opit_0_L8Q_perm/CLK} -min -max_path 8
puts {TX_DELAY_0075_END}
puts {TX_DELAY_0076_BEGIN}
get_path_delay -rise_from {system/output_video/r[2]/opit_0_L8Q_perm/CLK} -rise_to {r_out[7]} -min -max_path 8
puts {TX_DELAY_0076_END}
puts {TX_DELAY_0077_BEGIN}
get_path_delay -rise_from {system/output_video/r[2]/opit_0_L8Q_perm/CLK} -fall_to {r_out[7]} -min -max_path 8
puts {TX_DELAY_0077_END}
puts {TX_DELAY_0078_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/vs/opit_0_inv_L6Q_perm/CLK} -min -max_path 8
puts {TX_DELAY_0078_END}
puts {TX_DELAY_0079_BEGIN}
get_path_delay -rise_from {system/output_video/vs/opit_0_inv_L6Q_perm/CLK} -rise_to {vs_out} -min -max_path 8
puts {TX_DELAY_0079_END}
puts {TX_DELAY_0080_BEGIN}
get_path_delay -rise_from {system/output_video/vs/opit_0_inv_L6Q_perm/CLK} -fall_to {vs_out} -min -max_path 8
puts {TX_DELAY_0080_END}
puts {TX_DELAY_0081_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {pix_clk} -min -max_path 8
puts {TX_DELAY_0081_END}
puts {TX_DELAY_0082_BEGIN}
get_path_delay -fall_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -fall_to {pix_clk} -min -max_path 8
puts {TX_DELAY_0082_END}
puts {TX_DELAY_0083_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/b[0]/opit_0_L8Q_perm/CLK} -max_path 8
puts {TX_DELAY_0083_END}
puts {TX_DELAY_0084_BEGIN}
get_path_delay -rise_from {system/output_video/b[0]/opit_0_L8Q_perm/CLK} -rise_to {b_out[0]} -max_path 8
puts {TX_DELAY_0084_END}
puts {TX_DELAY_0085_BEGIN}
get_path_delay -rise_from {system/output_video/b[0]/opit_0_L8Q_perm/CLK} -fall_to {b_out[0]} -max_path 8
puts {TX_DELAY_0085_END}
puts {TX_DELAY_0086_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/b[1]/opit_0_L8Q_perm/CLK} -max_path 8
puts {TX_DELAY_0086_END}
puts {TX_DELAY_0087_BEGIN}
get_path_delay -rise_from {system/output_video/b[1]/opit_0_L8Q_perm/CLK} -rise_to {b_out[1]} -max_path 8
puts {TX_DELAY_0087_END}
puts {TX_DELAY_0088_BEGIN}
get_path_delay -rise_from {system/output_video/b[1]/opit_0_L8Q_perm/CLK} -fall_to {b_out[1]} -max_path 8
puts {TX_DELAY_0088_END}
puts {TX_DELAY_0089_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/b[2]/opit_0_L8Q_perm/CLK} -max_path 8
puts {TX_DELAY_0089_END}
puts {TX_DELAY_0090_BEGIN}
get_path_delay -rise_from {system/output_video/b[2]/opit_0_L8Q_perm/CLK} -rise_to {b_out[2]} -max_path 8
puts {TX_DELAY_0090_END}
puts {TX_DELAY_0091_BEGIN}
get_path_delay -rise_from {system/output_video/b[2]/opit_0_L8Q_perm/CLK} -fall_to {b_out[2]} -max_path 8
puts {TX_DELAY_0091_END}
puts {TX_DELAY_0092_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/b[3]/opit_0_L8Q_perm/CLK} -max_path 8
puts {TX_DELAY_0092_END}
puts {TX_DELAY_0093_BEGIN}
get_path_delay -rise_from {system/output_video/b[3]/opit_0_L8Q_perm/CLK} -rise_to {b_out[3]} -max_path 8
puts {TX_DELAY_0093_END}
puts {TX_DELAY_0094_BEGIN}
get_path_delay -rise_from {system/output_video/b[3]/opit_0_L8Q_perm/CLK} -fall_to {b_out[3]} -max_path 8
puts {TX_DELAY_0094_END}
puts {TX_DELAY_0095_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/b[4]/opit_0_L8Q_perm/CLK} -max_path 8
puts {TX_DELAY_0095_END}
puts {TX_DELAY_0096_BEGIN}
get_path_delay -rise_from {system/output_video/b[4]/opit_0_L8Q_perm/CLK} -rise_to {b_out[4]} -max_path 8
puts {TX_DELAY_0096_END}
puts {TX_DELAY_0097_BEGIN}
get_path_delay -rise_from {system/output_video/b[4]/opit_0_L8Q_perm/CLK} -fall_to {b_out[4]} -max_path 8
puts {TX_DELAY_0097_END}
puts {TX_DELAY_0098_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/b[0]/opit_0_L8Q_perm/CLK} -max_path 8
puts {TX_DELAY_0098_END}
puts {TX_DELAY_0099_BEGIN}
get_path_delay -rise_from {system/output_video/b[0]/opit_0_L8Q_perm/CLK} -rise_to {b_out[5]} -max_path 8
puts {TX_DELAY_0099_END}
puts {TX_DELAY_0100_BEGIN}
get_path_delay -rise_from {system/output_video/b[0]/opit_0_L8Q_perm/CLK} -fall_to {b_out[5]} -max_path 8
puts {TX_DELAY_0100_END}
puts {TX_DELAY_0101_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/b[1]/opit_0_L8Q_perm/CLK} -max_path 8
puts {TX_DELAY_0101_END}
puts {TX_DELAY_0102_BEGIN}
get_path_delay -rise_from {system/output_video/b[1]/opit_0_L8Q_perm/CLK} -rise_to {b_out[6]} -max_path 8
puts {TX_DELAY_0102_END}
puts {TX_DELAY_0103_BEGIN}
get_path_delay -rise_from {system/output_video/b[1]/opit_0_L8Q_perm/CLK} -fall_to {b_out[6]} -max_path 8
puts {TX_DELAY_0103_END}
puts {TX_DELAY_0104_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/b[2]/opit_0_L8Q_perm/CLK} -max_path 8
puts {TX_DELAY_0104_END}
puts {TX_DELAY_0105_BEGIN}
get_path_delay -rise_from {system/output_video/b[2]/opit_0_L8Q_perm/CLK} -rise_to {b_out[7]} -max_path 8
puts {TX_DELAY_0105_END}
puts {TX_DELAY_0106_BEGIN}
get_path_delay -rise_from {system/output_video/b[2]/opit_0_L8Q_perm/CLK} -fall_to {b_out[7]} -max_path 8
puts {TX_DELAY_0106_END}
puts {TX_DELAY_0107_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/de/opit_0_inv_L6Q_perm/CLK} -max_path 8
puts {TX_DELAY_0107_END}
puts {TX_DELAY_0108_BEGIN}
get_path_delay -rise_from {system/output_video/de/opit_0_inv_L6Q_perm/CLK} -rise_to {de_out} -max_path 8
puts {TX_DELAY_0108_END}
puts {TX_DELAY_0109_BEGIN}
get_path_delay -rise_from {system/output_video/de/opit_0_inv_L6Q_perm/CLK} -fall_to {de_out} -max_path 8
puts {TX_DELAY_0109_END}
puts {TX_DELAY_0110_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/g[0]/opit_0_L8Q_perm/CLK} -max_path 8
puts {TX_DELAY_0110_END}
puts {TX_DELAY_0111_BEGIN}
get_path_delay -rise_from {system/output_video/g[0]/opit_0_L8Q_perm/CLK} -rise_to {g_out[0]} -max_path 8
puts {TX_DELAY_0111_END}
puts {TX_DELAY_0112_BEGIN}
get_path_delay -rise_from {system/output_video/g[0]/opit_0_L8Q_perm/CLK} -fall_to {g_out[0]} -max_path 8
puts {TX_DELAY_0112_END}
puts {TX_DELAY_0113_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/g[1]/opit_0_L8Q_perm/CLK} -max_path 8
puts {TX_DELAY_0113_END}
puts {TX_DELAY_0114_BEGIN}
get_path_delay -rise_from {system/output_video/g[1]/opit_0_L8Q_perm/CLK} -rise_to {g_out[1]} -max_path 8
puts {TX_DELAY_0114_END}
puts {TX_DELAY_0115_BEGIN}
get_path_delay -rise_from {system/output_video/g[1]/opit_0_L8Q_perm/CLK} -fall_to {g_out[1]} -max_path 8
puts {TX_DELAY_0115_END}
puts {TX_DELAY_0116_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/g[2]/opit_0_L8Q_perm/CLK} -max_path 8
puts {TX_DELAY_0116_END}
puts {TX_DELAY_0117_BEGIN}
get_path_delay -rise_from {system/output_video/g[2]/opit_0_L8Q_perm/CLK} -rise_to {g_out[2]} -max_path 8
puts {TX_DELAY_0117_END}
puts {TX_DELAY_0118_BEGIN}
get_path_delay -rise_from {system/output_video/g[2]/opit_0_L8Q_perm/CLK} -fall_to {g_out[2]} -max_path 8
puts {TX_DELAY_0118_END}
puts {TX_DELAY_0119_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/g[3]/opit_0_L8Q_perm/CLK} -max_path 8
puts {TX_DELAY_0119_END}
puts {TX_DELAY_0120_BEGIN}
get_path_delay -rise_from {system/output_video/g[3]/opit_0_L8Q_perm/CLK} -rise_to {g_out[3]} -max_path 8
puts {TX_DELAY_0120_END}
puts {TX_DELAY_0121_BEGIN}
get_path_delay -rise_from {system/output_video/g[3]/opit_0_L8Q_perm/CLK} -fall_to {g_out[3]} -max_path 8
puts {TX_DELAY_0121_END}
puts {TX_DELAY_0122_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/g[4]/opit_0_L8Q_perm/CLK} -max_path 8
puts {TX_DELAY_0122_END}
puts {TX_DELAY_0123_BEGIN}
get_path_delay -rise_from {system/output_video/g[4]/opit_0_L8Q_perm/CLK} -rise_to {g_out[4]} -max_path 8
puts {TX_DELAY_0123_END}
puts {TX_DELAY_0124_BEGIN}
get_path_delay -rise_from {system/output_video/g[4]/opit_0_L8Q_perm/CLK} -fall_to {g_out[4]} -max_path 8
puts {TX_DELAY_0124_END}
puts {TX_DELAY_0125_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/g[5]/opit_0_L8Q_perm/CLK} -max_path 8
puts {TX_DELAY_0125_END}
puts {TX_DELAY_0126_BEGIN}
get_path_delay -rise_from {system/output_video/g[5]/opit_0_L8Q_perm/CLK} -rise_to {g_out[5]} -max_path 8
puts {TX_DELAY_0126_END}
puts {TX_DELAY_0127_BEGIN}
get_path_delay -rise_from {system/output_video/g[5]/opit_0_L8Q_perm/CLK} -fall_to {g_out[5]} -max_path 8
puts {TX_DELAY_0127_END}
puts {TX_DELAY_0128_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/g[0]/opit_0_L8Q_perm/CLK} -max_path 8
puts {TX_DELAY_0128_END}
puts {TX_DELAY_0129_BEGIN}
get_path_delay -rise_from {system/output_video/g[0]/opit_0_L8Q_perm/CLK} -rise_to {g_out[6]} -max_path 8
puts {TX_DELAY_0129_END}
puts {TX_DELAY_0130_BEGIN}
get_path_delay -rise_from {system/output_video/g[0]/opit_0_L8Q_perm/CLK} -fall_to {g_out[6]} -max_path 8
puts {TX_DELAY_0130_END}
puts {TX_DELAY_0131_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/g[1]/opit_0_L8Q_perm/CLK} -max_path 8
puts {TX_DELAY_0131_END}
puts {TX_DELAY_0132_BEGIN}
get_path_delay -rise_from {system/output_video/g[1]/opit_0_L8Q_perm/CLK} -rise_to {g_out[7]} -max_path 8
puts {TX_DELAY_0132_END}
puts {TX_DELAY_0133_BEGIN}
get_path_delay -rise_from {system/output_video/g[1]/opit_0_L8Q_perm/CLK} -fall_to {g_out[7]} -max_path 8
puts {TX_DELAY_0133_END}
puts {TX_DELAY_0134_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/hs/opit_0_inv_L6Q_perm/CLK} -max_path 8
puts {TX_DELAY_0134_END}
puts {TX_DELAY_0135_BEGIN}
get_path_delay -rise_from {system/output_video/hs/opit_0_inv_L6Q_perm/CLK} -rise_to {hs_out} -max_path 8
puts {TX_DELAY_0135_END}
puts {TX_DELAY_0136_BEGIN}
get_path_delay -rise_from {system/output_video/hs/opit_0_inv_L6Q_perm/CLK} -fall_to {hs_out} -max_path 8
puts {TX_DELAY_0136_END}
puts {TX_DELAY_0137_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/r[0]/opit_0_L8Q_perm/CLK} -max_path 8
puts {TX_DELAY_0137_END}
puts {TX_DELAY_0138_BEGIN}
get_path_delay -rise_from {system/output_video/r[0]/opit_0_L8Q_perm/CLK} -rise_to {r_out[0]} -max_path 8
puts {TX_DELAY_0138_END}
puts {TX_DELAY_0139_BEGIN}
get_path_delay -rise_from {system/output_video/r[0]/opit_0_L8Q_perm/CLK} -fall_to {r_out[0]} -max_path 8
puts {TX_DELAY_0139_END}
puts {TX_DELAY_0140_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/r[1]/opit_0_L8Q_perm/CLK} -max_path 8
puts {TX_DELAY_0140_END}
puts {TX_DELAY_0141_BEGIN}
get_path_delay -rise_from {system/output_video/r[1]/opit_0_L8Q_perm/CLK} -rise_to {r_out[1]} -max_path 8
puts {TX_DELAY_0141_END}
puts {TX_DELAY_0142_BEGIN}
get_path_delay -rise_from {system/output_video/r[1]/opit_0_L8Q_perm/CLK} -fall_to {r_out[1]} -max_path 8
puts {TX_DELAY_0142_END}
puts {TX_DELAY_0143_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/r[2]/opit_0_L8Q_perm/CLK} -max_path 8
puts {TX_DELAY_0143_END}
puts {TX_DELAY_0144_BEGIN}
get_path_delay -rise_from {system/output_video/r[2]/opit_0_L8Q_perm/CLK} -rise_to {r_out[2]} -max_path 8
puts {TX_DELAY_0144_END}
puts {TX_DELAY_0145_BEGIN}
get_path_delay -rise_from {system/output_video/r[2]/opit_0_L8Q_perm/CLK} -fall_to {r_out[2]} -max_path 8
puts {TX_DELAY_0145_END}
puts {TX_DELAY_0146_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/r[3]/opit_0_L8Q_perm/CLK} -max_path 8
puts {TX_DELAY_0146_END}
puts {TX_DELAY_0147_BEGIN}
get_path_delay -rise_from {system/output_video/r[3]/opit_0_L8Q_perm/CLK} -rise_to {r_out[3]} -max_path 8
puts {TX_DELAY_0147_END}
puts {TX_DELAY_0148_BEGIN}
get_path_delay -rise_from {system/output_video/r[3]/opit_0_L8Q_perm/CLK} -fall_to {r_out[3]} -max_path 8
puts {TX_DELAY_0148_END}
puts {TX_DELAY_0149_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/r[4]/opit_0_L8Q_perm/CLK} -max_path 8
puts {TX_DELAY_0149_END}
puts {TX_DELAY_0150_BEGIN}
get_path_delay -rise_from {system/output_video/r[4]/opit_0_L8Q_perm/CLK} -rise_to {r_out[4]} -max_path 8
puts {TX_DELAY_0150_END}
puts {TX_DELAY_0151_BEGIN}
get_path_delay -rise_from {system/output_video/r[4]/opit_0_L8Q_perm/CLK} -fall_to {r_out[4]} -max_path 8
puts {TX_DELAY_0151_END}
puts {TX_DELAY_0152_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/r[0]/opit_0_L8Q_perm/CLK} -max_path 8
puts {TX_DELAY_0152_END}
puts {TX_DELAY_0153_BEGIN}
get_path_delay -rise_from {system/output_video/r[0]/opit_0_L8Q_perm/CLK} -rise_to {r_out[5]} -max_path 8
puts {TX_DELAY_0153_END}
puts {TX_DELAY_0154_BEGIN}
get_path_delay -rise_from {system/output_video/r[0]/opit_0_L8Q_perm/CLK} -fall_to {r_out[5]} -max_path 8
puts {TX_DELAY_0154_END}
puts {TX_DELAY_0155_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/r[1]/opit_0_L8Q_perm/CLK} -max_path 8
puts {TX_DELAY_0155_END}
puts {TX_DELAY_0156_BEGIN}
get_path_delay -rise_from {system/output_video/r[1]/opit_0_L8Q_perm/CLK} -rise_to {r_out[6]} -max_path 8
puts {TX_DELAY_0156_END}
puts {TX_DELAY_0157_BEGIN}
get_path_delay -rise_from {system/output_video/r[1]/opit_0_L8Q_perm/CLK} -fall_to {r_out[6]} -max_path 8
puts {TX_DELAY_0157_END}
puts {TX_DELAY_0158_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/r[2]/opit_0_L8Q_perm/CLK} -max_path 8
puts {TX_DELAY_0158_END}
puts {TX_DELAY_0159_BEGIN}
get_path_delay -rise_from {system/output_video/r[2]/opit_0_L8Q_perm/CLK} -rise_to {r_out[7]} -max_path 8
puts {TX_DELAY_0159_END}
puts {TX_DELAY_0160_BEGIN}
get_path_delay -rise_from {system/output_video/r[2]/opit_0_L8Q_perm/CLK} -fall_to {r_out[7]} -max_path 8
puts {TX_DELAY_0160_END}
puts {TX_DELAY_0161_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/vs/opit_0_inv_L6Q_perm/CLK} -max_path 8
puts {TX_DELAY_0161_END}
puts {TX_DELAY_0162_BEGIN}
get_path_delay -rise_from {system/output_video/vs/opit_0_inv_L6Q_perm/CLK} -rise_to {vs_out} -max_path 8
puts {TX_DELAY_0162_END}
puts {TX_DELAY_0163_BEGIN}
get_path_delay -rise_from {system/output_video/vs/opit_0_inv_L6Q_perm/CLK} -fall_to {vs_out} -max_path 8
puts {TX_DELAY_0163_END}
puts {TX_DELAY_0164_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {pix_clk} -max_path 8
puts {TX_DELAY_0164_END}
puts {TX_DELAY_0165_BEGIN}
get_path_delay -fall_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -fall_to {pix_clk} -max_path 8
puts {TX_DELAY_0165_END}
puts {TX_DELAY_0166_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/b[0]/opit_0_L8Q_perm/CLK} -min -fast -max_path 8
puts {TX_DELAY_0166_END}
puts {TX_DELAY_0167_BEGIN}
get_path_delay -rise_from {system/output_video/b[0]/opit_0_L8Q_perm/CLK} -rise_to {b_out[0]} -min -fast -max_path 8
puts {TX_DELAY_0167_END}
puts {TX_DELAY_0168_BEGIN}
get_path_delay -rise_from {system/output_video/b[0]/opit_0_L8Q_perm/CLK} -fall_to {b_out[0]} -min -fast -max_path 8
puts {TX_DELAY_0168_END}
puts {TX_DELAY_0169_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/b[1]/opit_0_L8Q_perm/CLK} -min -fast -max_path 8
puts {TX_DELAY_0169_END}
puts {TX_DELAY_0170_BEGIN}
get_path_delay -rise_from {system/output_video/b[1]/opit_0_L8Q_perm/CLK} -rise_to {b_out[1]} -min -fast -max_path 8
puts {TX_DELAY_0170_END}
puts {TX_DELAY_0171_BEGIN}
get_path_delay -rise_from {system/output_video/b[1]/opit_0_L8Q_perm/CLK} -fall_to {b_out[1]} -min -fast -max_path 8
puts {TX_DELAY_0171_END}
puts {TX_DELAY_0172_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/b[2]/opit_0_L8Q_perm/CLK} -min -fast -max_path 8
puts {TX_DELAY_0172_END}
puts {TX_DELAY_0173_BEGIN}
get_path_delay -rise_from {system/output_video/b[2]/opit_0_L8Q_perm/CLK} -rise_to {b_out[2]} -min -fast -max_path 8
puts {TX_DELAY_0173_END}
puts {TX_DELAY_0174_BEGIN}
get_path_delay -rise_from {system/output_video/b[2]/opit_0_L8Q_perm/CLK} -fall_to {b_out[2]} -min -fast -max_path 8
puts {TX_DELAY_0174_END}
puts {TX_DELAY_0175_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/b[3]/opit_0_L8Q_perm/CLK} -min -fast -max_path 8
puts {TX_DELAY_0175_END}
puts {TX_DELAY_0176_BEGIN}
get_path_delay -rise_from {system/output_video/b[3]/opit_0_L8Q_perm/CLK} -rise_to {b_out[3]} -min -fast -max_path 8
puts {TX_DELAY_0176_END}
puts {TX_DELAY_0177_BEGIN}
get_path_delay -rise_from {system/output_video/b[3]/opit_0_L8Q_perm/CLK} -fall_to {b_out[3]} -min -fast -max_path 8
puts {TX_DELAY_0177_END}
puts {TX_DELAY_0178_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/b[4]/opit_0_L8Q_perm/CLK} -min -fast -max_path 8
puts {TX_DELAY_0178_END}
puts {TX_DELAY_0179_BEGIN}
get_path_delay -rise_from {system/output_video/b[4]/opit_0_L8Q_perm/CLK} -rise_to {b_out[4]} -min -fast -max_path 8
puts {TX_DELAY_0179_END}
puts {TX_DELAY_0180_BEGIN}
get_path_delay -rise_from {system/output_video/b[4]/opit_0_L8Q_perm/CLK} -fall_to {b_out[4]} -min -fast -max_path 8
puts {TX_DELAY_0180_END}
puts {TX_DELAY_0181_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/b[0]/opit_0_L8Q_perm/CLK} -min -fast -max_path 8
puts {TX_DELAY_0181_END}
puts {TX_DELAY_0182_BEGIN}
get_path_delay -rise_from {system/output_video/b[0]/opit_0_L8Q_perm/CLK} -rise_to {b_out[5]} -min -fast -max_path 8
puts {TX_DELAY_0182_END}
puts {TX_DELAY_0183_BEGIN}
get_path_delay -rise_from {system/output_video/b[0]/opit_0_L8Q_perm/CLK} -fall_to {b_out[5]} -min -fast -max_path 8
puts {TX_DELAY_0183_END}
puts {TX_DELAY_0184_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/b[1]/opit_0_L8Q_perm/CLK} -min -fast -max_path 8
puts {TX_DELAY_0184_END}
puts {TX_DELAY_0185_BEGIN}
get_path_delay -rise_from {system/output_video/b[1]/opit_0_L8Q_perm/CLK} -rise_to {b_out[6]} -min -fast -max_path 8
puts {TX_DELAY_0185_END}
puts {TX_DELAY_0186_BEGIN}
get_path_delay -rise_from {system/output_video/b[1]/opit_0_L8Q_perm/CLK} -fall_to {b_out[6]} -min -fast -max_path 8
puts {TX_DELAY_0186_END}
puts {TX_DELAY_0187_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/b[2]/opit_0_L8Q_perm/CLK} -min -fast -max_path 8
puts {TX_DELAY_0187_END}
puts {TX_DELAY_0188_BEGIN}
get_path_delay -rise_from {system/output_video/b[2]/opit_0_L8Q_perm/CLK} -rise_to {b_out[7]} -min -fast -max_path 8
puts {TX_DELAY_0188_END}
puts {TX_DELAY_0189_BEGIN}
get_path_delay -rise_from {system/output_video/b[2]/opit_0_L8Q_perm/CLK} -fall_to {b_out[7]} -min -fast -max_path 8
puts {TX_DELAY_0189_END}
puts {TX_DELAY_0190_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/de/opit_0_inv_L6Q_perm/CLK} -min -fast -max_path 8
puts {TX_DELAY_0190_END}
puts {TX_DELAY_0191_BEGIN}
get_path_delay -rise_from {system/output_video/de/opit_0_inv_L6Q_perm/CLK} -rise_to {de_out} -min -fast -max_path 8
puts {TX_DELAY_0191_END}
puts {TX_DELAY_0192_BEGIN}
get_path_delay -rise_from {system/output_video/de/opit_0_inv_L6Q_perm/CLK} -fall_to {de_out} -min -fast -max_path 8
puts {TX_DELAY_0192_END}
puts {TX_DELAY_0193_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/g[0]/opit_0_L8Q_perm/CLK} -min -fast -max_path 8
puts {TX_DELAY_0193_END}
puts {TX_DELAY_0194_BEGIN}
get_path_delay -rise_from {system/output_video/g[0]/opit_0_L8Q_perm/CLK} -rise_to {g_out[0]} -min -fast -max_path 8
puts {TX_DELAY_0194_END}
puts {TX_DELAY_0195_BEGIN}
get_path_delay -rise_from {system/output_video/g[0]/opit_0_L8Q_perm/CLK} -fall_to {g_out[0]} -min -fast -max_path 8
puts {TX_DELAY_0195_END}
puts {TX_DELAY_0196_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/g[1]/opit_0_L8Q_perm/CLK} -min -fast -max_path 8
puts {TX_DELAY_0196_END}
puts {TX_DELAY_0197_BEGIN}
get_path_delay -rise_from {system/output_video/g[1]/opit_0_L8Q_perm/CLK} -rise_to {g_out[1]} -min -fast -max_path 8
puts {TX_DELAY_0197_END}
puts {TX_DELAY_0198_BEGIN}
get_path_delay -rise_from {system/output_video/g[1]/opit_0_L8Q_perm/CLK} -fall_to {g_out[1]} -min -fast -max_path 8
puts {TX_DELAY_0198_END}
puts {TX_DELAY_0199_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/g[2]/opit_0_L8Q_perm/CLK} -min -fast -max_path 8
puts {TX_DELAY_0199_END}
puts {TX_DELAY_0200_BEGIN}
get_path_delay -rise_from {system/output_video/g[2]/opit_0_L8Q_perm/CLK} -rise_to {g_out[2]} -min -fast -max_path 8
puts {TX_DELAY_0200_END}
puts {TX_DELAY_0201_BEGIN}
get_path_delay -rise_from {system/output_video/g[2]/opit_0_L8Q_perm/CLK} -fall_to {g_out[2]} -min -fast -max_path 8
puts {TX_DELAY_0201_END}
puts {TX_DELAY_0202_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/g[3]/opit_0_L8Q_perm/CLK} -min -fast -max_path 8
puts {TX_DELAY_0202_END}
puts {TX_DELAY_0203_BEGIN}
get_path_delay -rise_from {system/output_video/g[3]/opit_0_L8Q_perm/CLK} -rise_to {g_out[3]} -min -fast -max_path 8
puts {TX_DELAY_0203_END}
puts {TX_DELAY_0204_BEGIN}
get_path_delay -rise_from {system/output_video/g[3]/opit_0_L8Q_perm/CLK} -fall_to {g_out[3]} -min -fast -max_path 8
puts {TX_DELAY_0204_END}
puts {TX_DELAY_0205_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/g[4]/opit_0_L8Q_perm/CLK} -min -fast -max_path 8
puts {TX_DELAY_0205_END}
puts {TX_DELAY_0206_BEGIN}
get_path_delay -rise_from {system/output_video/g[4]/opit_0_L8Q_perm/CLK} -rise_to {g_out[4]} -min -fast -max_path 8
puts {TX_DELAY_0206_END}
puts {TX_DELAY_0207_BEGIN}
get_path_delay -rise_from {system/output_video/g[4]/opit_0_L8Q_perm/CLK} -fall_to {g_out[4]} -min -fast -max_path 8
puts {TX_DELAY_0207_END}
puts {TX_DELAY_0208_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/g[5]/opit_0_L8Q_perm/CLK} -min -fast -max_path 8
puts {TX_DELAY_0208_END}
puts {TX_DELAY_0209_BEGIN}
get_path_delay -rise_from {system/output_video/g[5]/opit_0_L8Q_perm/CLK} -rise_to {g_out[5]} -min -fast -max_path 8
puts {TX_DELAY_0209_END}
puts {TX_DELAY_0210_BEGIN}
get_path_delay -rise_from {system/output_video/g[5]/opit_0_L8Q_perm/CLK} -fall_to {g_out[5]} -min -fast -max_path 8
puts {TX_DELAY_0210_END}
puts {TX_DELAY_0211_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/g[0]/opit_0_L8Q_perm/CLK} -min -fast -max_path 8
puts {TX_DELAY_0211_END}
puts {TX_DELAY_0212_BEGIN}
get_path_delay -rise_from {system/output_video/g[0]/opit_0_L8Q_perm/CLK} -rise_to {g_out[6]} -min -fast -max_path 8
puts {TX_DELAY_0212_END}
puts {TX_DELAY_0213_BEGIN}
get_path_delay -rise_from {system/output_video/g[0]/opit_0_L8Q_perm/CLK} -fall_to {g_out[6]} -min -fast -max_path 8
puts {TX_DELAY_0213_END}
puts {TX_DELAY_0214_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/g[1]/opit_0_L8Q_perm/CLK} -min -fast -max_path 8
puts {TX_DELAY_0214_END}
puts {TX_DELAY_0215_BEGIN}
get_path_delay -rise_from {system/output_video/g[1]/opit_0_L8Q_perm/CLK} -rise_to {g_out[7]} -min -fast -max_path 8
puts {TX_DELAY_0215_END}
puts {TX_DELAY_0216_BEGIN}
get_path_delay -rise_from {system/output_video/g[1]/opit_0_L8Q_perm/CLK} -fall_to {g_out[7]} -min -fast -max_path 8
puts {TX_DELAY_0216_END}
puts {TX_DELAY_0217_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/hs/opit_0_inv_L6Q_perm/CLK} -min -fast -max_path 8
puts {TX_DELAY_0217_END}
puts {TX_DELAY_0218_BEGIN}
get_path_delay -rise_from {system/output_video/hs/opit_0_inv_L6Q_perm/CLK} -rise_to {hs_out} -min -fast -max_path 8
puts {TX_DELAY_0218_END}
puts {TX_DELAY_0219_BEGIN}
get_path_delay -rise_from {system/output_video/hs/opit_0_inv_L6Q_perm/CLK} -fall_to {hs_out} -min -fast -max_path 8
puts {TX_DELAY_0219_END}
puts {TX_DELAY_0220_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/r[0]/opit_0_L8Q_perm/CLK} -min -fast -max_path 8
puts {TX_DELAY_0220_END}
puts {TX_DELAY_0221_BEGIN}
get_path_delay -rise_from {system/output_video/r[0]/opit_0_L8Q_perm/CLK} -rise_to {r_out[0]} -min -fast -max_path 8
puts {TX_DELAY_0221_END}
puts {TX_DELAY_0222_BEGIN}
get_path_delay -rise_from {system/output_video/r[0]/opit_0_L8Q_perm/CLK} -fall_to {r_out[0]} -min -fast -max_path 8
puts {TX_DELAY_0222_END}
puts {TX_DELAY_0223_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/r[1]/opit_0_L8Q_perm/CLK} -min -fast -max_path 8
puts {TX_DELAY_0223_END}
puts {TX_DELAY_0224_BEGIN}
get_path_delay -rise_from {system/output_video/r[1]/opit_0_L8Q_perm/CLK} -rise_to {r_out[1]} -min -fast -max_path 8
puts {TX_DELAY_0224_END}
puts {TX_DELAY_0225_BEGIN}
get_path_delay -rise_from {system/output_video/r[1]/opit_0_L8Q_perm/CLK} -fall_to {r_out[1]} -min -fast -max_path 8
puts {TX_DELAY_0225_END}
puts {TX_DELAY_0226_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/r[2]/opit_0_L8Q_perm/CLK} -min -fast -max_path 8
puts {TX_DELAY_0226_END}
puts {TX_DELAY_0227_BEGIN}
get_path_delay -rise_from {system/output_video/r[2]/opit_0_L8Q_perm/CLK} -rise_to {r_out[2]} -min -fast -max_path 8
puts {TX_DELAY_0227_END}
puts {TX_DELAY_0228_BEGIN}
get_path_delay -rise_from {system/output_video/r[2]/opit_0_L8Q_perm/CLK} -fall_to {r_out[2]} -min -fast -max_path 8
puts {TX_DELAY_0228_END}
puts {TX_DELAY_0229_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/r[3]/opit_0_L8Q_perm/CLK} -min -fast -max_path 8
puts {TX_DELAY_0229_END}
puts {TX_DELAY_0230_BEGIN}
get_path_delay -rise_from {system/output_video/r[3]/opit_0_L8Q_perm/CLK} -rise_to {r_out[3]} -min -fast -max_path 8
puts {TX_DELAY_0230_END}
puts {TX_DELAY_0231_BEGIN}
get_path_delay -rise_from {system/output_video/r[3]/opit_0_L8Q_perm/CLK} -fall_to {r_out[3]} -min -fast -max_path 8
puts {TX_DELAY_0231_END}
puts {TX_DELAY_0232_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/r[4]/opit_0_L8Q_perm/CLK} -min -fast -max_path 8
puts {TX_DELAY_0232_END}
puts {TX_DELAY_0233_BEGIN}
get_path_delay -rise_from {system/output_video/r[4]/opit_0_L8Q_perm/CLK} -rise_to {r_out[4]} -min -fast -max_path 8
puts {TX_DELAY_0233_END}
puts {TX_DELAY_0234_BEGIN}
get_path_delay -rise_from {system/output_video/r[4]/opit_0_L8Q_perm/CLK} -fall_to {r_out[4]} -min -fast -max_path 8
puts {TX_DELAY_0234_END}
puts {TX_DELAY_0235_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/r[0]/opit_0_L8Q_perm/CLK} -min -fast -max_path 8
puts {TX_DELAY_0235_END}
puts {TX_DELAY_0236_BEGIN}
get_path_delay -rise_from {system/output_video/r[0]/opit_0_L8Q_perm/CLK} -rise_to {r_out[5]} -min -fast -max_path 8
puts {TX_DELAY_0236_END}
puts {TX_DELAY_0237_BEGIN}
get_path_delay -rise_from {system/output_video/r[0]/opit_0_L8Q_perm/CLK} -fall_to {r_out[5]} -min -fast -max_path 8
puts {TX_DELAY_0237_END}
puts {TX_DELAY_0238_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/r[1]/opit_0_L8Q_perm/CLK} -min -fast -max_path 8
puts {TX_DELAY_0238_END}
puts {TX_DELAY_0239_BEGIN}
get_path_delay -rise_from {system/output_video/r[1]/opit_0_L8Q_perm/CLK} -rise_to {r_out[6]} -min -fast -max_path 8
puts {TX_DELAY_0239_END}
puts {TX_DELAY_0240_BEGIN}
get_path_delay -rise_from {system/output_video/r[1]/opit_0_L8Q_perm/CLK} -fall_to {r_out[6]} -min -fast -max_path 8
puts {TX_DELAY_0240_END}
puts {TX_DELAY_0241_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/r[2]/opit_0_L8Q_perm/CLK} -min -fast -max_path 8
puts {TX_DELAY_0241_END}
puts {TX_DELAY_0242_BEGIN}
get_path_delay -rise_from {system/output_video/r[2]/opit_0_L8Q_perm/CLK} -rise_to {r_out[7]} -min -fast -max_path 8
puts {TX_DELAY_0242_END}
puts {TX_DELAY_0243_BEGIN}
get_path_delay -rise_from {system/output_video/r[2]/opit_0_L8Q_perm/CLK} -fall_to {r_out[7]} -min -fast -max_path 8
puts {TX_DELAY_0243_END}
puts {TX_DELAY_0244_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/vs/opit_0_inv_L6Q_perm/CLK} -min -fast -max_path 8
puts {TX_DELAY_0244_END}
puts {TX_DELAY_0245_BEGIN}
get_path_delay -rise_from {system/output_video/vs/opit_0_inv_L6Q_perm/CLK} -rise_to {vs_out} -min -fast -max_path 8
puts {TX_DELAY_0245_END}
puts {TX_DELAY_0246_BEGIN}
get_path_delay -rise_from {system/output_video/vs/opit_0_inv_L6Q_perm/CLK} -fall_to {vs_out} -min -fast -max_path 8
puts {TX_DELAY_0246_END}
puts {TX_DELAY_0247_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {pix_clk} -min -fast -max_path 8
puts {TX_DELAY_0247_END}
puts {TX_DELAY_0248_BEGIN}
get_path_delay -fall_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -fall_to {pix_clk} -min -fast -max_path 8
puts {TX_DELAY_0248_END}
puts {TX_DELAY_0249_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/b[0]/opit_0_L8Q_perm/CLK} -fast -max_path 8
puts {TX_DELAY_0249_END}
puts {TX_DELAY_0250_BEGIN}
get_path_delay -rise_from {system/output_video/b[0]/opit_0_L8Q_perm/CLK} -rise_to {b_out[0]} -fast -max_path 8
puts {TX_DELAY_0250_END}
puts {TX_DELAY_0251_BEGIN}
get_path_delay -rise_from {system/output_video/b[0]/opit_0_L8Q_perm/CLK} -fall_to {b_out[0]} -fast -max_path 8
puts {TX_DELAY_0251_END}
puts {TX_DELAY_0252_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/b[1]/opit_0_L8Q_perm/CLK} -fast -max_path 8
puts {TX_DELAY_0252_END}
puts {TX_DELAY_0253_BEGIN}
get_path_delay -rise_from {system/output_video/b[1]/opit_0_L8Q_perm/CLK} -rise_to {b_out[1]} -fast -max_path 8
puts {TX_DELAY_0253_END}
puts {TX_DELAY_0254_BEGIN}
get_path_delay -rise_from {system/output_video/b[1]/opit_0_L8Q_perm/CLK} -fall_to {b_out[1]} -fast -max_path 8
puts {TX_DELAY_0254_END}
puts {TX_DELAY_0255_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/b[2]/opit_0_L8Q_perm/CLK} -fast -max_path 8
puts {TX_DELAY_0255_END}
puts {TX_DELAY_0256_BEGIN}
get_path_delay -rise_from {system/output_video/b[2]/opit_0_L8Q_perm/CLK} -rise_to {b_out[2]} -fast -max_path 8
puts {TX_DELAY_0256_END}
puts {TX_DELAY_0257_BEGIN}
get_path_delay -rise_from {system/output_video/b[2]/opit_0_L8Q_perm/CLK} -fall_to {b_out[2]} -fast -max_path 8
puts {TX_DELAY_0257_END}
puts {TX_DELAY_0258_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/b[3]/opit_0_L8Q_perm/CLK} -fast -max_path 8
puts {TX_DELAY_0258_END}
puts {TX_DELAY_0259_BEGIN}
get_path_delay -rise_from {system/output_video/b[3]/opit_0_L8Q_perm/CLK} -rise_to {b_out[3]} -fast -max_path 8
puts {TX_DELAY_0259_END}
puts {TX_DELAY_0260_BEGIN}
get_path_delay -rise_from {system/output_video/b[3]/opit_0_L8Q_perm/CLK} -fall_to {b_out[3]} -fast -max_path 8
puts {TX_DELAY_0260_END}
puts {TX_DELAY_0261_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/b[4]/opit_0_L8Q_perm/CLK} -fast -max_path 8
puts {TX_DELAY_0261_END}
puts {TX_DELAY_0262_BEGIN}
get_path_delay -rise_from {system/output_video/b[4]/opit_0_L8Q_perm/CLK} -rise_to {b_out[4]} -fast -max_path 8
puts {TX_DELAY_0262_END}
puts {TX_DELAY_0263_BEGIN}
get_path_delay -rise_from {system/output_video/b[4]/opit_0_L8Q_perm/CLK} -fall_to {b_out[4]} -fast -max_path 8
puts {TX_DELAY_0263_END}
puts {TX_DELAY_0264_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/b[0]/opit_0_L8Q_perm/CLK} -fast -max_path 8
puts {TX_DELAY_0264_END}
puts {TX_DELAY_0265_BEGIN}
get_path_delay -rise_from {system/output_video/b[0]/opit_0_L8Q_perm/CLK} -rise_to {b_out[5]} -fast -max_path 8
puts {TX_DELAY_0265_END}
puts {TX_DELAY_0266_BEGIN}
get_path_delay -rise_from {system/output_video/b[0]/opit_0_L8Q_perm/CLK} -fall_to {b_out[5]} -fast -max_path 8
puts {TX_DELAY_0266_END}
puts {TX_DELAY_0267_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/b[1]/opit_0_L8Q_perm/CLK} -fast -max_path 8
puts {TX_DELAY_0267_END}
puts {TX_DELAY_0268_BEGIN}
get_path_delay -rise_from {system/output_video/b[1]/opit_0_L8Q_perm/CLK} -rise_to {b_out[6]} -fast -max_path 8
puts {TX_DELAY_0268_END}
puts {TX_DELAY_0269_BEGIN}
get_path_delay -rise_from {system/output_video/b[1]/opit_0_L8Q_perm/CLK} -fall_to {b_out[6]} -fast -max_path 8
puts {TX_DELAY_0269_END}
puts {TX_DELAY_0270_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/b[2]/opit_0_L8Q_perm/CLK} -fast -max_path 8
puts {TX_DELAY_0270_END}
puts {TX_DELAY_0271_BEGIN}
get_path_delay -rise_from {system/output_video/b[2]/opit_0_L8Q_perm/CLK} -rise_to {b_out[7]} -fast -max_path 8
puts {TX_DELAY_0271_END}
puts {TX_DELAY_0272_BEGIN}
get_path_delay -rise_from {system/output_video/b[2]/opit_0_L8Q_perm/CLK} -fall_to {b_out[7]} -fast -max_path 8
puts {TX_DELAY_0272_END}
puts {TX_DELAY_0273_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/de/opit_0_inv_L6Q_perm/CLK} -fast -max_path 8
puts {TX_DELAY_0273_END}
puts {TX_DELAY_0274_BEGIN}
get_path_delay -rise_from {system/output_video/de/opit_0_inv_L6Q_perm/CLK} -rise_to {de_out} -fast -max_path 8
puts {TX_DELAY_0274_END}
puts {TX_DELAY_0275_BEGIN}
get_path_delay -rise_from {system/output_video/de/opit_0_inv_L6Q_perm/CLK} -fall_to {de_out} -fast -max_path 8
puts {TX_DELAY_0275_END}
puts {TX_DELAY_0276_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/g[0]/opit_0_L8Q_perm/CLK} -fast -max_path 8
puts {TX_DELAY_0276_END}
puts {TX_DELAY_0277_BEGIN}
get_path_delay -rise_from {system/output_video/g[0]/opit_0_L8Q_perm/CLK} -rise_to {g_out[0]} -fast -max_path 8
puts {TX_DELAY_0277_END}
puts {TX_DELAY_0278_BEGIN}
get_path_delay -rise_from {system/output_video/g[0]/opit_0_L8Q_perm/CLK} -fall_to {g_out[0]} -fast -max_path 8
puts {TX_DELAY_0278_END}
puts {TX_DELAY_0279_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/g[1]/opit_0_L8Q_perm/CLK} -fast -max_path 8
puts {TX_DELAY_0279_END}
puts {TX_DELAY_0280_BEGIN}
get_path_delay -rise_from {system/output_video/g[1]/opit_0_L8Q_perm/CLK} -rise_to {g_out[1]} -fast -max_path 8
puts {TX_DELAY_0280_END}
puts {TX_DELAY_0281_BEGIN}
get_path_delay -rise_from {system/output_video/g[1]/opit_0_L8Q_perm/CLK} -fall_to {g_out[1]} -fast -max_path 8
puts {TX_DELAY_0281_END}
puts {TX_DELAY_0282_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/g[2]/opit_0_L8Q_perm/CLK} -fast -max_path 8
puts {TX_DELAY_0282_END}
puts {TX_DELAY_0283_BEGIN}
get_path_delay -rise_from {system/output_video/g[2]/opit_0_L8Q_perm/CLK} -rise_to {g_out[2]} -fast -max_path 8
puts {TX_DELAY_0283_END}
puts {TX_DELAY_0284_BEGIN}
get_path_delay -rise_from {system/output_video/g[2]/opit_0_L8Q_perm/CLK} -fall_to {g_out[2]} -fast -max_path 8
puts {TX_DELAY_0284_END}
puts {TX_DELAY_0285_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/g[3]/opit_0_L8Q_perm/CLK} -fast -max_path 8
puts {TX_DELAY_0285_END}
puts {TX_DELAY_0286_BEGIN}
get_path_delay -rise_from {system/output_video/g[3]/opit_0_L8Q_perm/CLK} -rise_to {g_out[3]} -fast -max_path 8
puts {TX_DELAY_0286_END}
puts {TX_DELAY_0287_BEGIN}
get_path_delay -rise_from {system/output_video/g[3]/opit_0_L8Q_perm/CLK} -fall_to {g_out[3]} -fast -max_path 8
puts {TX_DELAY_0287_END}
puts {TX_DELAY_0288_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/g[4]/opit_0_L8Q_perm/CLK} -fast -max_path 8
puts {TX_DELAY_0288_END}
puts {TX_DELAY_0289_BEGIN}
get_path_delay -rise_from {system/output_video/g[4]/opit_0_L8Q_perm/CLK} -rise_to {g_out[4]} -fast -max_path 8
puts {TX_DELAY_0289_END}
puts {TX_DELAY_0290_BEGIN}
get_path_delay -rise_from {system/output_video/g[4]/opit_0_L8Q_perm/CLK} -fall_to {g_out[4]} -fast -max_path 8
puts {TX_DELAY_0290_END}
puts {TX_DELAY_0291_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/g[5]/opit_0_L8Q_perm/CLK} -fast -max_path 8
puts {TX_DELAY_0291_END}
puts {TX_DELAY_0292_BEGIN}
get_path_delay -rise_from {system/output_video/g[5]/opit_0_L8Q_perm/CLK} -rise_to {g_out[5]} -fast -max_path 8
puts {TX_DELAY_0292_END}
puts {TX_DELAY_0293_BEGIN}
get_path_delay -rise_from {system/output_video/g[5]/opit_0_L8Q_perm/CLK} -fall_to {g_out[5]} -fast -max_path 8
puts {TX_DELAY_0293_END}
puts {TX_DELAY_0294_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/g[0]/opit_0_L8Q_perm/CLK} -fast -max_path 8
puts {TX_DELAY_0294_END}
puts {TX_DELAY_0295_BEGIN}
get_path_delay -rise_from {system/output_video/g[0]/opit_0_L8Q_perm/CLK} -rise_to {g_out[6]} -fast -max_path 8
puts {TX_DELAY_0295_END}
puts {TX_DELAY_0296_BEGIN}
get_path_delay -rise_from {system/output_video/g[0]/opit_0_L8Q_perm/CLK} -fall_to {g_out[6]} -fast -max_path 8
puts {TX_DELAY_0296_END}
puts {TX_DELAY_0297_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/g[1]/opit_0_L8Q_perm/CLK} -fast -max_path 8
puts {TX_DELAY_0297_END}
puts {TX_DELAY_0298_BEGIN}
get_path_delay -rise_from {system/output_video/g[1]/opit_0_L8Q_perm/CLK} -rise_to {g_out[7]} -fast -max_path 8
puts {TX_DELAY_0298_END}
puts {TX_DELAY_0299_BEGIN}
get_path_delay -rise_from {system/output_video/g[1]/opit_0_L8Q_perm/CLK} -fall_to {g_out[7]} -fast -max_path 8
puts {TX_DELAY_0299_END}
puts {TX_DELAY_0300_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/hs/opit_0_inv_L6Q_perm/CLK} -fast -max_path 8
puts {TX_DELAY_0300_END}
puts {TX_DELAY_0301_BEGIN}
get_path_delay -rise_from {system/output_video/hs/opit_0_inv_L6Q_perm/CLK} -rise_to {hs_out} -fast -max_path 8
puts {TX_DELAY_0301_END}
puts {TX_DELAY_0302_BEGIN}
get_path_delay -rise_from {system/output_video/hs/opit_0_inv_L6Q_perm/CLK} -fall_to {hs_out} -fast -max_path 8
puts {TX_DELAY_0302_END}
puts {TX_DELAY_0303_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/r[0]/opit_0_L8Q_perm/CLK} -fast -max_path 8
puts {TX_DELAY_0303_END}
puts {TX_DELAY_0304_BEGIN}
get_path_delay -rise_from {system/output_video/r[0]/opit_0_L8Q_perm/CLK} -rise_to {r_out[0]} -fast -max_path 8
puts {TX_DELAY_0304_END}
puts {TX_DELAY_0305_BEGIN}
get_path_delay -rise_from {system/output_video/r[0]/opit_0_L8Q_perm/CLK} -fall_to {r_out[0]} -fast -max_path 8
puts {TX_DELAY_0305_END}
puts {TX_DELAY_0306_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/r[1]/opit_0_L8Q_perm/CLK} -fast -max_path 8
puts {TX_DELAY_0306_END}
puts {TX_DELAY_0307_BEGIN}
get_path_delay -rise_from {system/output_video/r[1]/opit_0_L8Q_perm/CLK} -rise_to {r_out[1]} -fast -max_path 8
puts {TX_DELAY_0307_END}
puts {TX_DELAY_0308_BEGIN}
get_path_delay -rise_from {system/output_video/r[1]/opit_0_L8Q_perm/CLK} -fall_to {r_out[1]} -fast -max_path 8
puts {TX_DELAY_0308_END}
puts {TX_DELAY_0309_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/r[2]/opit_0_L8Q_perm/CLK} -fast -max_path 8
puts {TX_DELAY_0309_END}
puts {TX_DELAY_0310_BEGIN}
get_path_delay -rise_from {system/output_video/r[2]/opit_0_L8Q_perm/CLK} -rise_to {r_out[2]} -fast -max_path 8
puts {TX_DELAY_0310_END}
puts {TX_DELAY_0311_BEGIN}
get_path_delay -rise_from {system/output_video/r[2]/opit_0_L8Q_perm/CLK} -fall_to {r_out[2]} -fast -max_path 8
puts {TX_DELAY_0311_END}
puts {TX_DELAY_0312_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/r[3]/opit_0_L8Q_perm/CLK} -fast -max_path 8
puts {TX_DELAY_0312_END}
puts {TX_DELAY_0313_BEGIN}
get_path_delay -rise_from {system/output_video/r[3]/opit_0_L8Q_perm/CLK} -rise_to {r_out[3]} -fast -max_path 8
puts {TX_DELAY_0313_END}
puts {TX_DELAY_0314_BEGIN}
get_path_delay -rise_from {system/output_video/r[3]/opit_0_L8Q_perm/CLK} -fall_to {r_out[3]} -fast -max_path 8
puts {TX_DELAY_0314_END}
puts {TX_DELAY_0315_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/r[4]/opit_0_L8Q_perm/CLK} -fast -max_path 8
puts {TX_DELAY_0315_END}
puts {TX_DELAY_0316_BEGIN}
get_path_delay -rise_from {system/output_video/r[4]/opit_0_L8Q_perm/CLK} -rise_to {r_out[4]} -fast -max_path 8
puts {TX_DELAY_0316_END}
puts {TX_DELAY_0317_BEGIN}
get_path_delay -rise_from {system/output_video/r[4]/opit_0_L8Q_perm/CLK} -fall_to {r_out[4]} -fast -max_path 8
puts {TX_DELAY_0317_END}
puts {TX_DELAY_0318_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/r[0]/opit_0_L8Q_perm/CLK} -fast -max_path 8
puts {TX_DELAY_0318_END}
puts {TX_DELAY_0319_BEGIN}
get_path_delay -rise_from {system/output_video/r[0]/opit_0_L8Q_perm/CLK} -rise_to {r_out[5]} -fast -max_path 8
puts {TX_DELAY_0319_END}
puts {TX_DELAY_0320_BEGIN}
get_path_delay -rise_from {system/output_video/r[0]/opit_0_L8Q_perm/CLK} -fall_to {r_out[5]} -fast -max_path 8
puts {TX_DELAY_0320_END}
puts {TX_DELAY_0321_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/r[1]/opit_0_L8Q_perm/CLK} -fast -max_path 8
puts {TX_DELAY_0321_END}
puts {TX_DELAY_0322_BEGIN}
get_path_delay -rise_from {system/output_video/r[1]/opit_0_L8Q_perm/CLK} -rise_to {r_out[6]} -fast -max_path 8
puts {TX_DELAY_0322_END}
puts {TX_DELAY_0323_BEGIN}
get_path_delay -rise_from {system/output_video/r[1]/opit_0_L8Q_perm/CLK} -fall_to {r_out[6]} -fast -max_path 8
puts {TX_DELAY_0323_END}
puts {TX_DELAY_0324_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/r[2]/opit_0_L8Q_perm/CLK} -fast -max_path 8
puts {TX_DELAY_0324_END}
puts {TX_DELAY_0325_BEGIN}
get_path_delay -rise_from {system/output_video/r[2]/opit_0_L8Q_perm/CLK} -rise_to {r_out[7]} -fast -max_path 8
puts {TX_DELAY_0325_END}
puts {TX_DELAY_0326_BEGIN}
get_path_delay -rise_from {system/output_video/r[2]/opit_0_L8Q_perm/CLK} -fall_to {r_out[7]} -fast -max_path 8
puts {TX_DELAY_0326_END}
puts {TX_DELAY_0327_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {system/output_video/vs/opit_0_inv_L6Q_perm/CLK} -fast -max_path 8
puts {TX_DELAY_0327_END}
puts {TX_DELAY_0328_BEGIN}
get_path_delay -rise_from {system/output_video/vs/opit_0_inv_L6Q_perm/CLK} -rise_to {vs_out} -fast -max_path 8
puts {TX_DELAY_0328_END}
puts {TX_DELAY_0329_BEGIN}
get_path_delay -rise_from {system/output_video/vs/opit_0_inv_L6Q_perm/CLK} -fall_to {vs_out} -fast -max_path 8
puts {TX_DELAY_0329_END}
puts {TX_DELAY_0330_BEGIN}
get_path_delay -rise_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -rise_to {pix_clk} -fast -max_path 8
puts {TX_DELAY_0330_END}
puts {TX_DELAY_0331_BEGIN}
get_path_delay -fall_from {video_pll/u_gpll/gpll_inst/CLKOUT0} -fall_to {pix_clk} -fast -max_path 8
puts {TX_DELAY_0331_END}
