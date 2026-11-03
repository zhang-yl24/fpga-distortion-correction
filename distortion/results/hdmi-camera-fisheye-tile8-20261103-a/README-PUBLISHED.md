# tile8 已上板交付：15 FPS

本轮 tile8（8×8 访问 + 双 8 行条带写回）已下载到易失 SRAM。默认矫正采集 30.009 秒、30 个连续样本：新画面 15.0 FPS，相比 S3 5.0 FPS 达到 3 倍（提升 200%），HDMI 扫描 30 Hz。主机独立计时为 15.000262 FPS，末帧处理 44.31112 ms。窗口内新增空白帧/故障/CRC拒绝/丢弃均为0；未写Flash。

- [实际位流](evidence/release-b/hdmi_camera_fisheye_top.sbit)：3,791,112 字节，SHA256 `1236d82f113e1ddb1c5e24502ed1aa03e4758db0a7d6ff17bf9216f0fbd0e4f3`。
- [原阶段B报告](README-stage-b.md)、[生成/下载/测率索引](selected-bit-board-fps-index-b.json)、[独立保存字节对比](evidence/release-b/independent-tile8-vs-S3-comparison.json)。
- [源码闭包与重建入口](../../../delivery/20261103-hdmi-camera-fisheye-tile8/README.md)、[资源报告](../../../handoff/HDMI_CAMERA_FISHEYE_TILE8_RESOURCES_20261103.md)。
- [发布版便携文件清单](portable-evidence-manifest-c.json)：覆盖原A/B包及新增原始资源、已通过的单元仿真回执和进程结束记录。原阶段A/B文件不改写。

本次发布只整理和离线校验已有证据，没有再次访问板卡或运行EDA。历史绝对路径忠实保留在回执中，便携验证走仓库相对路径。约107.2MB的物理应用回执、64.6MB完整物理证明及大型报告保留原路径/SHA引用，未放入Git；随包SHA校验不代替完整物理重推导。新重建必须使用新目录并重新完成自身物理、位流及板上验收。

在仓库根目录运行：

```powershell
python -B delivery/20261103-hdmi-camera-fisheye-tile8/verify_source.py
python -B distortion/results/hdmi-camera-fisheye-tile8-20261103-a/verify_archive_portable.py --manifest portable-evidence-manifest-c.json
python -B distortion/tools/verify_fisheye_tile8_archive.py
```

本轮没有用户视觉反馈、光学延迟/曝光帧率、长期稳定性或KEY1往返验收。数字源时序、处理帧率、新画面帧率与30Hz扫描刷新分别记录。
