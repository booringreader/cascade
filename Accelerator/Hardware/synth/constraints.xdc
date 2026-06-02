# Timing and I/O constraints for systolic_array_3x3 (AWS F1 class UltraScale+)

create_clock -period 10.000 -name clk_sys [get_ports clk]
set_input_delay  -clock clk_sys 2.000 [get_ports -filter {DIRECTION == IN}]
set_output_delay -clock clk_sys 2.000 [get_ports -filter {DIRECTION == OUT}]

set_property IOSTANDARD LVCMOS18 [get_ports *]
