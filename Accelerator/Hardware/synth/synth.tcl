# Vivado batch synthesis for systolic_array_3x3
# Run from Accelerator/Hardware: vivado -mode batch -source synth/synth.tcl

set script_dir [file normalize [file dirname [info script]]]
set hw_root    [file normalize [file join $script_dir ..]]
set src_dir    [file join $hw_root src]
set out_dir    [file join $hw_root output]

file mkdir $out_dir

read_verilog [file join $src_dir pe.v]
read_verilog [file join $src_dir systolic_array.v]
read_verilog [file join $src_dir systolic_tiler.v]
read_verilog [file join $src_dir conv_im2col.v]

set_property top systolic_array_3x3 [current_fileset]

set_part xcvu9p-flgb2104-2-i

read_xdc [file join $script_dir constraints.xdc]

synth_design -top systolic_array_3x3 \
    -flatten_hierarchy rebuilt \
    -directive AreaOptimized_high

opt_design

report_utilization -file [file join $out_dir utilization.rpt]
report_timing_summary -file [file join $out_dir timing.rpt]

write_checkpoint -force [file join $out_dir systolic_array_synth.dcp]

puts "SYNTHESIS COMPLETE"
