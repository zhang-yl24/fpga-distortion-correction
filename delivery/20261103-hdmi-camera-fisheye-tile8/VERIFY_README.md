# 不连接硬件的交付校验

从仓库根目录执行：

```powershell
python -B delivery/20261103-hdmi-camera-fisheye-tile8/verify_source.py
python -B distortion/results/hdmi-camera-fisheye-tile8-20261103-a/verify_archive_portable.py --manifest portable-evidence-manifest-c.json
python -B distortion/tools/verify_fisheye_tile8_archive.py
```

源码校验验证原始/编译 SHA、110 项输入闭包、DDR IDF 展开、5 个 include 重定位、顶层数字时序参数及 seed 3 的 Tcl。归档校验只读取包内相对路径，逐项检查大小和 SHA。

离线测率校验重新解析包内 S3/tile8 的原始串口字节，核对 CRC、样本序列、有效矫正状态、帧计数、主机到达时间、缓存计数及提升比例，并关联实际位流、ADF、下载与测率回执。S3 位流来自仓库已发布的 S3 结果包。历史 JSON 内的本机绝对路径用于追溯，脚本使用仓库中的固定相对路径定位实际证据。

上述命令不运行仿真器或 EDA，不打开串口/JTAG，不重新下载板卡。它们检验已保存的数据与来源绑定；完整物理接受仍依赖本轮保留的大型原件，数字遥测也不替代视觉、光学延迟或长期稳定性验收。
