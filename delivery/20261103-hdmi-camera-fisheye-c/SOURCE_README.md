# C 版源码闭包与重建准备

这份闭包对应当前板上运行的 `hdmi_camera_fisheye_top` C 版。发布 bitstream 的 SHA256 是 `8c43a77d9ddce72dc7015ef7f63aabe37ab6758dd698e2e811b669c5aa5ba047`，最终 ADF 的 SHA256 是 `7b21d06112eda0213bd60780d971e90a9da492d7a29daac09eda11d388f96310`。

`source-manifest.json` 逐项记录原始源码 SHA256、实际 build-c 编译输入 SHA256 和转换来源。110 份源码、头文件、约束及 DDR IP 输入都与 bit-c 的原始 `bitstream-plan.json` 双向绑定；保留在仓库原有 `distortion/` 路径。DDR IDF 及其声明的全部加密源文件一起校验，保留原 IP 文件与合成选项。

`build-inputs/` 保存实际 build-c 的计划和 Tcl、bit-c 的计划和验证记录原字节。它们里面的本机绝对路径是原始记录，只用于校验溯源，重建工具不访问这些历史路径，也不需要旧 `distortion/work/` 文件。

实际编译输入中有 6 份文件不同于原始源码：5 份只是绑定头文件的 include 路径重定位；板顶层将 `INPUT_TIMING_CONFIGURED` 从 `0` 改为 `1`。`frozen-compiled/` 保存这 6 份实际编译输入原字节。校验器会从原始源码重放已记录的变换，并确认它们与快照逐字节相同。原始生产源码保持不变。

在干净克隆的仓库根目录执行（只需要 Python 3.10+ 标准库）：

```powershell
python delivery/20261103-hdmi-camera-fisheye-c/verify_source.py
python delivery/20261103-hdmi-camera-fisheye-c/prepare_build.py --output .bld
python delivery/20261103-hdmi-camera-fisheye-c/verify_source.py --prepared .bld
```

输出目录必须尚不存在。Windows 下应选短目录，避免最长 DDR IP 文件名超过 PDS 的 260 字符路径限制；准备器会在写入前检查。准备工具复制完整闭包，重定位 5 处 include 及构建 Tcl 的路径，并写入可再次校验的 `rebuild-plan.json`。顶层编译输入仍使用已经记录的 `INPUT_TIMING_CONFIGURED=1`。Tcl 保留原来的架构、32 个显式设计输入、2 个约束输入，以及 `synthesize -ads -selected_syn_tool_opt 2`、多角时序、hold 修复和时序报告选项。DDR 的其他源文件由 IDF 展开。

准备过程不调用 EDA 或硬件。要自行启动新构建，使用与发布版本相同的 Pango PDS 2023.2-SP3（build 154097），本机安装目录和许可证由使用者配置：

```powershell
& '<PDS安装目录>/bin/pds_shell.exe' -file '<重建目录绝对路径>/build.tcl' -work_dir '<重建目录绝对路径>' -project_name hdmi_camera_fisheye_top
```

新构建仅从相同输入和编译选项开始；路径重定位、工具环境和布局布线运行都可能影响结果。历史物理及时序签核只属于发布的 ADF 和 bitstream；新结果需要重新完成物理、STA、bitstream 校验及上板验证。这份准备工具不会生成 bitstream、烧写 SRAM 或 Flash。
