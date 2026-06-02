// AXI4-Lite MMIO wrapper for systolic_array_3x3 (FireSim / Chipyard black box)
`timescale 1ns/1ps

module SystolicArrayTop (
    input  wire        s_axi_aclk,
    input  wire        s_axi_aresetn,

    input  wire [7:0]  s_axi_awaddr,
    input  wire        s_axi_awvalid,
    output reg         s_axi_awready,

    input  wire [31:0] s_axi_wdata,
    input  wire [3:0]  s_axi_wstrb,
    input  wire        s_axi_wvalid,
    output reg         s_axi_wready,

    output reg  [1:0]  s_axi_bresp,
    output reg         s_axi_bvalid,
    input  wire        s_axi_bready,

    input  wire [7:0]  s_axi_araddr,
    input  wire        s_axi_arvalid,
    output reg         s_axi_arready,

    output reg  [31:0] s_axi_rdata,
    output reg  [1:0]  s_axi_rresp,
    output reg         s_axi_rvalid,
    input  wire        s_axi_rready
);

    localparam [7:0] REG_A0   = 8'h00;
    localparam [7:0] REG_A1   = 8'h04;
    localparam [7:0] REG_A2   = 8'h08;
    localparam [7:0] REG_B0   = 8'h0C;
    localparam [7:0] REG_B1   = 8'h10;
    localparam [7:0] REG_B2   = 8'h14;
    localparam [7:0] REG_CTRL = 8'h18;

    reg signed [7:0] reg_a0, reg_a1, reg_a2;
    reg signed [7:0] reg_b0, reg_b1, reg_b2;

    reg        core_clk;
    reg        core_rst;
    reg        do_latch_pulse;
    reg        do_rst_pulse;

    wire signed [15:0] c00, c01, c02, c10, c11, c12, c20, c21, c22;
    wire               write_fire = s_axi_awvalid && s_axi_wvalid &&
                                    s_axi_awready && s_axi_wready;

    function [15:0] c_result_for_addr;
        input [7:0] addr;
        begin
            case (addr)
                8'h40: c_result_for_addr = c00;
                8'h44: c_result_for_addr = c01;
                8'h48: c_result_for_addr = c02;
                8'h4C: c_result_for_addr = c10;
                8'h50: c_result_for_addr = c11;
                8'h54: c_result_for_addr = c12;
                8'h58: c_result_for_addr = c20;
                8'h5C: c_result_for_addr = c21;
                8'h60: c_result_for_addr = c22;
                8'h64: c_result_for_addr = c22;
                default: c_result_for_addr = 16'sd0;
            endcase
        end
    endfunction

    systolic_array_3x3 u_array (
        .clk(core_clk),
        .rst(core_rst),
        .a0(reg_a0), .a1(reg_a1), .a2(reg_a2),
        .b0(reg_b0), .b1(reg_b1), .b2(reg_b2),
        .c00(c00), .c01(c01), .c02(c02),
        .c10(c10), .c11(c11), .c12(c12),
        .c20(c20), .c21(c21), .c22(c22)
    );

    always @(posedge s_axi_aclk or negedge s_axi_aresetn) begin
        if (!s_axi_aresetn) begin
            reg_a0        <= 8'sd0;
            reg_a1        <= 8'sd0;
            reg_a2        <= 8'sd0;
            reg_b0        <= 8'sd0;
            reg_b1        <= 8'sd0;
            reg_b2        <= 8'sd0;
            core_clk      <= 1'b0;
            core_rst      <= 1'b0;
            do_latch_pulse <= 1'b0;
            do_rst_pulse  <= 1'b0;

            s_axi_awready <= 1'b1;
            s_axi_wready  <= 1'b1;
            s_axi_bvalid  <= 1'b0;
            s_axi_bresp   <= 2'b00;
            s_axi_arready <= 1'b1;
            s_axi_rvalid  <= 1'b0;
            s_axi_rresp   <= 2'b00;
            s_axi_rdata   <= 32'd0;
        end else begin
            core_clk       <= 1'b0;
            core_rst       <= 1'b0;
            do_latch_pulse <= 1'b0;
            do_rst_pulse   <= 1'b0;

            if (do_latch_pulse)
                core_clk <= 1'b1;
            if (do_rst_pulse)
                core_rst <= 1'b1;

            if (write_fire) begin
                s_axi_bvalid <= 1'b1;
                s_axi_bresp  <= 2'b00;
                case (s_axi_awaddr)
                    REG_A0: if (s_axi_wstrb[0]) reg_a0 <= s_axi_wdata[7:0];
                    REG_A1: if (s_axi_wstrb[0]) reg_a1 <= s_axi_wdata[7:0];
                    REG_A2: if (s_axi_wstrb[0]) reg_a2 <= s_axi_wdata[7:0];
                    REG_B0: if (s_axi_wstrb[0]) reg_b0 <= s_axi_wdata[7:0];
                    REG_B1: if (s_axi_wstrb[0]) reg_b1 <= s_axi_wdata[7:0];
                    REG_B2: if (s_axi_wstrb[0]) reg_b2 <= s_axi_wdata[7:0];
                    REG_CTRL: begin
                        if (s_axi_wstrb[0]) begin
                            if (s_axi_wdata[0])
                                do_rst_pulse <= 1'b1;
                            if (s_axi_wdata[1])
                                do_latch_pulse <= 1'b1;
                        end
                    end
                    default: ;
                endcase
            end

            if (s_axi_bvalid && s_axi_bready)
                s_axi_bvalid <= 1'b0;

            if (s_axi_arvalid && s_axi_arready) begin
                s_axi_rdata  <= {16'd0, c_result_for_addr(s_axi_araddr)};
                s_axi_rvalid <= 1'b1;
                s_axi_rresp  <= 2'b00;
            end else if (s_axi_rvalid && s_axi_rready) begin
                s_axi_rvalid <= 1'b0;
            end

            s_axi_awready <= !s_axi_bvalid;
            s_axi_wready  <= !s_axi_bvalid;
            s_axi_arready <= !s_axi_rvalid;
        end
    end

endmodule
