# FireSim Integration — Systolic Array 3×3

This guide explains how to integrate the CASCADE `systolic_array_3x3` accelerator into a [FireSim](https://docs.fires.im/) / Chipyard target using the AXI4-Lite wrapper and Scala config stub in this repository.

## 1. Prerequisites

| Requirement | Notes |
|-------------|--------|
| **AWS account** | FireSim manager and run farm run on EC2 |
| **FireSim** | Clone and initialize per [FireSim docs](https://docs.fires.im/en/latest/Getting-Started-Guides/AWS-EC2-F1-Getting-Started/Initial-Setup/index.html) |
| **Manager instance** | `m5.4xlarge` (or larger) for builds and orchestration |
| **FPGA instance** | `f1.2xlarge` for simulation (one F1 per simulated node) |
| **Vivado** | Provided on the FireSim manager AMI for bitstream builds |

Typical setup:

```bash
git clone https://github.com/firesim/firesim.git
cd firesim
./scripts/machine-launch-script.sh --platform ec2 --tag <your-tag>
source sourceme-manager.sh --platform ec2
firesim managerinit --platform ec2
```

## 2. File placement in the FireSim / Chipyard tree

Copy artifacts from this repo into your FireSim checkout (paths assume Chipyard 1.9+ layout):

| Source (this repo) | Destination (FireSim) |
|--------------------|-------------------------|
| `firesim/target_design/SystolicArrayTop.v` | `generators/chipyard/src/main/resources/SystolicArrayTop.v` |
| `firesim/target_design/SystolicArrayTop.v` | Symlink or copy into Chipyard `generators/` Verilog search path used by your config |
| `firesim/target_design/SystolicArrayConfig.scala` | `generators/chipyard/src/main/scala/systolicarray/SystolicArrayConfig.scala` |

Also copy the **RTL core** (unchanged) so Vivado/FIRRTL can elaborate the black box:

```bash
mkdir -p generators/chipyard/src/main/resources/cascade
cp <cascade-repo>/Accelerator/Hardware/src/pe.v \
   <cascade-repo>/Accelerator/Hardware/src/systolic_array.v \
   generators/chipyard/src/main/resources/cascade/
```

Update `SystolicArrayTopBlackBox` `addResource` paths in `SystolicArrayConfig.scala` if your layout differs.

**MMIO map** (must match software drivers):

| Offset | Register | Access |
|--------|----------|--------|
| `0x00`–`0x14` | `REG_A0`–`REG_B2` | Write 8-bit matrix inputs |
| `0x18` | `REG_CTRL` | bit0 = reset pulse, bit1 = clock/latch pulse |
| `0x40`–`0x64` | `REG_C00`–`REG_C22` | Read 16-bit results |

Base address: `0x10020000` (4 KB region) — see `SystolicArrayConsts` in the Scala file.

## 3. Build flow

1. **Add a build recipe** in `deploy/config_build_recipes.ini`:

```ini
[systolic_array_build]
TARGET_CONFIG = SystolicArrayConfig
PLATFORM_CONFIG = f1
deploy_quintuplet = firesim-chipyard-systolicarrayconfig-0.1.0
```

2. **Point FireSim at your config** in `config_build.ini` / `config_build_recipes.ini` (manager defaults).

3. **Build the bitstream** from the manager:

```bash
firesim buildbitstream
```

Expect **~6–8 hours** on AWS for a full F1 bitstream (varies with instance load and design size). The build runs Vivado place-and-route on the generated RTL including `SystolicArrayTop`.

4. **Optional: local RTL synthesis** (CASCADE repo only, no FireSim):

```bash
cd Accelerator/Hardware
vivado -mode batch -source synth/synth.tcl
```

Reports land in `Accelerator/Hardware/output/`.

## 4. Run flow

1. Edit `deploy/config_runtime.ini` — select the quintuplet built above and workload.

2. **Launch the run farm**:

```bash
firesim launchrunfarm
```

3. **Run a workload** (example: bare-metal or Linux driver that writes `REG_A*`, `REG_B*`, pulses `REG_CTRL`, reads `REG_C*`):

```bash
firesim runworkload
```

**Passing workload behavior:**

- Pulse reset via `REG_CTRL[0]`
- Load skewed or stationary 3×3 operands into A/B registers
- Pulse `REG_CTRL[1]` once per systolic clock step (or a small loop implementing skew in software)
- Read `REG_C00`–`REG_C22` and compare to golden (e.g. CASCADE `Simulator/src/run_tests.py` or a C reference)

Console / UART should print success (e.g. `PASS` / matching checksum) if your workload includes self-checks.

## 5. Collecting results

After `firesim buildbitstream`, Vivado reports are under the FireSim build directory, typically:

```text
firesim/deploy/results-build/<build-dir>/vivado_proj/firesim/...
```

| Report | What to check |
|--------|----------------|
| **Utilization** (`utilization.rpt` or `post_route_util.rpt`) | LUT/FF/DSP for `systolic_array_3x3` / `SystolicArrayTop`; DSP count ≈ number of 8×8 multipliers inferred |
| **Timing** (`timing_summary.rpt`) | **WNS ≥ 0** for timing closure at target clock (100 MHz `clk_sys` in CASCADE `constraints.xdc`) |
| **Power** (`power.rpt` if enabled) | Estimated dynamic/static power for sign-off estimates |

Local CASCADE synthesis (without FireSim) writes:

- `Accelerator/Hardware/output/utilization.rpt`
- `Accelerator/Hardware/output/timing.rpt`
- `Accelerator/Hardware/output/systolic_array_synth.dcp`

## 6. Teardown

Always terminate the run farm when finished to avoid EC2 charges:

```bash
firesim terminaterunfarm
```

Optionally stop the manager instance from the AWS console if you no longer need it.

## Related components

| Component | Path |
|-----------|------|
| RTL core | `Accelerator/Hardware/src/systolic_array.v` |
| AXI wrapper | `firesim/target_design/SystolicArrayTop.v` |
| Chipyard config | `firesim/target_design/SystolicArrayConfig.scala` |
| Python golden model | `Simulator/src/systolic_model.py` |
