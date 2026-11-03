# 选定 S3 的源码与重建输入

`source-manifest.json` 绑定本次已上板位流的 110 份原始输入、对应编译 SHA、文件顺序与角色。DDR IDF 展开 74 份源码，显式设计、头文件及 FDC/RCF 的角色单独校验。选定生产源码位于仓库 `distortion/`。

6 份冻结编译快照位于 `frozen-compiled/`：5 处受绑定的 include 路径重定位，以及顶层 `INPUT_TIMING_CONFIGURED` 从 0 变为 1。准备新构建只重新定位这 5 处 include 与 Tcl 的 compiled 根路径，保持已选数字时序配置。改变源码、变换、字段或来源 SHA 都会使校验失败。

`build-inputs/` 内的四份历史文件均按原字节复制：S3 build plan/Tcl、最终 v2 bit plan/verification。文件中的原开发机绝对路径保留为历史来源，便携脚本只读取随包副本与仓库相对路径。Tcl 的布局布线命令必须精确包含所选的 `-force_to_run -gplace_seed 3` 及其原始 timing/hold 选项。

在仓库根目录运行，要求 Python 3.10 或更新版本：

```powershell
python delivery/20261103-hdmi-camera-fisheye-fill8/verify_source.py
python delivery/20261103-hdmi-camera-fisheye-fill8/prepare_build.py --output .bld
python delivery/20261103-hdmi-camera-fisheye-fill8/verify_source.py --prepared .bld
```

`.bld` 必须不存在。Windows 下建议使用短路径克隆，脚本会在输出最长路径达到 260 字符前拒绝准备。`rebuild-plan.json` 记录生成输入及 Tcl 的 SHA，并给出 PDS 命令模板；准备阶段不执行该命令。

实际综合、布局布线需要用户合法安装相容的 PDS 及其器件/IP 支持。本包不复制 PDS 程序或另一份厂商授权 IP。历史已上板位流位于结果包，未在本目录重复保存。

新的普通构建尚未重新应用或证明历史物理约束。即使源码、工具版本和 seed 相同，也不能据此声称生成了与历史相同的 ADF/bit 或继承完整物理验证。下一轮输出需要独立完成物理范围、全部时序、网表/布局/路由边界、运行门检、bit 身份以及下载后的检查。
