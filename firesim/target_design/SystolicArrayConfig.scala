// SystolicArrayConfig.scala
// Integrates SystolicArrayTop as an MMIO peripheral in a FireSim target

package systolicarray

import chisel3._
import chisel3.util._
import org.chipsalliance.cde.config._
import freechips.rocketchip.config._
import freechips.rocketchip.diplomacy._
import freechips.rocketchip.amba.axi4._
import freechips.rocketchip.subsystem._
import freechips.rocketchip.tilelink._
import freechips.rocketchip.regmapper._
import freechips.rocketchip.devices.tilelink._
import freechips.rocketchip.util._

// Base address for the systolic array MMIO region (must match FireSim workload driver)
object SystolicArrayConsts {
  val baseAddress = 0x10020000L
  val size        = 0x1000L // 4KB MMIO window (covers 0x00–0x64 register map)
}

/** Diplomacy parameters for where the peripheral is mapped in physical address space. */
case class SystolicArrayAttachParams(
  baseAddress: BigInt = SystolicArrayConsts.baseAddress,
  size: BigInt = SystolicArrayConsts.size
)

/**
 * Black-box Verilog wrapper generated from firesim/target_design/SystolicArrayTop.v.
 * Chipyard elaboration treats this as an external AXI4-Lite slave.
 */
class SystolicArrayTopBlackBox extends BlackBox with HasBlackBoxResource {
  val io = IO(new Bundle {
    val s_axi_aclk    = Input(Clock())
    val s_axi_aresetn = Input(Bool())

    val s_axi_awaddr  = Input(UInt(8.W))
    val s_axi_awvalid = Input(Bool())
    val s_axi_awready = Output(Bool())

    val s_axi_wdata   = Input(UInt(32.W))
    val s_axi_wstrb   = Input(UInt(4.W))
    val s_axi_wvalid  = Input(Bool())
    val s_axi_wready  = Output(Bool())

    val s_axi_bresp   = Output(UInt(2.W))
    val s_axi_bvalid  = Output(Bool())
    val s_axi_bready  = Input(Bool())

    val s_axi_araddr  = Input(UInt(8.W))
    val s_axi_arvalid = Input(Bool())
    val s_axi_arready = Output(Bool())

    val s_axi_rdata   = Output(UInt(32.W))
    val s_axi_rresp   = Output(UInt(2.W))
    val s_axi_rvalid  = Output(Bool())
    val s_axi_rready  = Input(Bool())
  })

  addResource("/src/main/resources/SystolicArrayTop.v")
}

/** LazyModule that instantiates the black box and exposes AXI4-Lite diplomatic ports. */
class SystolicArrayLazyModule(implicit p: Parameters) extends LazyModule {
  val node = AXI4SlaveNode(Seq(
  AXI4SlavePortParameters(
    slaves = Seq(AXI4SlaveParameters(
      address       = Seq(AddressSet(SystolicArrayConsts.baseAddress, SystolicArrayConsts.size - 1)),
      regionType    = RegionType.UNCACHED,
      executable    = false,
      supportsWrite = TransferSizes(1, 4),
      supportsRead  = TransferSizes(1, 4),
      interleavedId = Some(0)
    )),
    beatBytes = 4
  )))

  lazy val module = new LazyModuleImp(this) {
    val (axi, _) = node.in(0)

    val bb = Module(new SystolicArrayTopBlackBox)
    bb.io.s_axi_aclk    := clock
    bb.io.s_axi_aresetn := !reset.asBool

    // Tie AXI4 master (from bus) to black-box slave (peripheral) — simplified direct connect
    bb.io.s_axi_awaddr  := axi.aw.bits.addr(7, 0)
    bb.io.s_axi_awvalid := axi.aw.valid
    axi.aw.ready        := bb.io.s_axi_awready

    bb.io.s_axi_wdata   := axi.w.bits.data
    bb.io.s_axi_wstrb   := axi.w.bits.strb
    bb.io.s_axi_wvalid  := axi.w.valid
    axi.w.ready         := bb.io.s_axi_wready

    axi.b.bits.resp     := bb.io.s_axi_bresp
    axi.b.valid         := bb.io.s_axi_bvalid
    bb.io.s_axi_bready  := axi.b.ready

    bb.io.s_axi_araddr  := axi.ar.bits.addr(7, 0)
    bb.io.s_axi_arvalid := axi.ar.valid
    axi.ar.ready        := bb.io.s_axi_arready

    axi.r.bits.data     := bb.io.s_axi_rdata
    axi.r.bits.resp     := bb.io.s_axi_rresp
    axi.r.valid         := bb.io.s_axi_rvalid
    bb.io.s_axi_rready  := axi.r.ready
  }
}

/**
 * Mixin trait: when present in the SoC config, attaches the systolic array at the MMIO base.
 */
trait CanHaveSystolicArray { this: BaseSubsystem =>
  val systolicParams = SystolicArrayAttachParams()
  val systolicArray  = LazyModule(new SystolicArrayLazyModule)

  // Map the peripheral into the platform MMIO bus (same pattern as other Chipyard devices)
  pbus.toVariableWidthSlave(Some("systolic-array")) := systolicArray.node
}

/** Config fragment: add `CanHaveSystolicArray` to the subsystem. */
class WithSystolicArray extends Config((site, here, up) => {
  case BuildSystem => (p: Parameters) => new CanHaveSystolicArray with SubsystemModuleImp(p)
})

/** Top-level FireSim generator config: default Rocket subsystem + systolic peripheral. */
class SystolicArrayConfig extends Config(
  new WithSystolicArray ++
  new freechips.rocketchip.system.DefaultConfig
)
