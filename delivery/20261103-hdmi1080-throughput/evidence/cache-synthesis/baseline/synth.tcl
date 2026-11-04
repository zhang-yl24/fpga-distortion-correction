proc checked {command} {
    set rc [catch {uplevel 1 $command} result]
    if {$rc != 0} { puts stderr $result; exit 1 }
    puts $result
}
cd {C:/Users/Lenovo/Documents/Codex/2026-11-02/2026-fpga/work/repo/delivery/20261103-hdmi1080-throughput/_build/cache-synth-baseline-a}
checked [list add_design {C:/Users/Lenovo/Documents/Codex/2026-11-02/2026-fpga/work/repo/delivery/20261103-hdmi1080-throughput/_build/cache-synth-baseline-a/cache.v}]
checked [list set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676]
checked [list compile -top_module ddr_neighbour_cache_scatter4_tag_prefetch_local]
checked [list synthesize -ads -selected_syn_tool_opt 2]
puts {CACHE_SYNTH_PROBE_COMPLETE}
