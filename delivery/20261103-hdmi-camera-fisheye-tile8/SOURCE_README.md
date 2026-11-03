# tile8 的源码与重建输入

`source-manifest.json` 绑定已上板 tile8 位流的 110 项原始输入、对应编译 SHA、文件顺序与角色。DDR IDF 展开 74 项源码；显式设计、头文件及 FDC/RCF 的角色单独核对。生产源码位于仓库 `distortion/`，tile8 选用独立的 engine、bank 和双条带 writer，未替换 S3 的历史源码或交付包。

`frozen-compiled/` 的 6 份编译快照包含 5 处受绑定的 include 重定位，以及顶层 `INPUT_TIMING_CONFIGURED` 从 0 到 1 的变换。新构建仅重定位这 5 处 include 和 Tcl 的 compiled 根路径，保留已选数字时序参数。

`build-inputs/` 的四份历史文件按原字节复制：tile8 build plan/Tcl、最终 v2 bit plan/verification。历史开发机绝对路径保留为来源记录；便携脚本只读取随包副本和仓库相对路径。Tcl 中的布局布线命令必须保留 `-force_to_run -gplace_seed 3` 及原 timing/hold 选项。

在仓库根目录运行，要求 Python 3.10 或更新版本：

```powershell
python -B delivery/20261103-hdmi-camera-fisheye-tile8/verify_source.py
python -B delivery/20261103-hdmi-camera-fisheye-tile8/prepare_build.py --output .bld-tile8-ci
python -B delivery/20261103-hdmi-camera-fisheye-tile8/verify_source.py --prepared .bld-tile8-ci
```

输出目录必须不存在。Windows 下采用短路径克隆；脚本会在准备路径达到 PDS 的 260 字符限制前拒绝准备。`rebuild-plan.json` 记录所有新输入与 Tcl 的 SHA，并给出 PDS 命令模板；准备阶段不执行此命令。

实际综合和布局布线需要相容的合法 PDS 安装及器件/IP 支持。本目录未复制 PDS 程序；已在仓库中的 DDR IP 通过原 IDF 清单绑定。历史上板位流只保存在结果包中。

新的普通构建尚未重新应用或证明本轮完整物理范围。即使源码、工具版本和 seed 相同，也不保证生成同一个 ADF/位流；新输出需要完成独立物理、时序、路由、生成前校验、位流身份和下载后的验证。
