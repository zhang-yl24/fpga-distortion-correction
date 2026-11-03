# 鱼眼矫正 fill8 / R3 Seed 3 交付

这是 2026-11-03 已下载到易失 SRAM 的 S3 版本：矫正模式实测 5.0 个新画面/秒，相比此前 C 版约 4.276 FPS 提高约 16.9%。用户反馈：“画面正常，比之前流畅，但还是有卡顿”。本次未写 Flash；S3 的原图帧率和 KEY1 往返切换尚未实测确认。

- [选定位流及全部运行证据](../../distortion/results/hdmi-camera-fisheye-fill8r3s3-20261103-a/README.md)
- [本次选定位流](../../distortion/results/hdmi-camera-fisheye-fill8r3s3-20261103-a/artifacts/hdmi_camera_fisheye_top.sbit)：3,791,112 字节，仅对应本工程目标板卡和易失 SRAM 流程。
- [源码闭包与重建说明](SOURCE_README.md)、[离线验证说明](VERIFY_README.md)
- [完整源码 SHA 清单](source-manifest.json)、[交付文件清单](delivery-manifest.json)
- [沿用的标定数据与图片](../20261103-hdmi-camera-fisheye-c/calibration/README.md)：本版本未重新标定，也未复制另一份图片。

选定位流 SHA256：`ae6be718eaa60fdcd1ba252c08133e7e24d22d247d2a649d21f0d1f7be4a4d16`。最终 ADF SHA256：`8510ff44a6c5cba81b675ad3bdf249ba93e1be4f2c372f5ff76b855ba761e2a2`。目标器件 PG2L100H、-6、FBG676，历史生成工具 PDS 2023.2-SP3 build 154097。

本目录提供 110 份选定源码/IP/头文件/约束的哈希角色，6 份发生编译变换的冻结快照，以及原始 S3 build plan/Tcl、bit plan/verification；其余未变的编译输入直接由仓库的相同源码字节提供。脚本只使用 Python 标准库，不依赖开发机 `work/`、P: 盘或原绝对路径。

准备脚本生成新的普通构建输入与 Tcl，并保留 `pnr -force_to_run -gplace_seed 3`。它不会执行 EDA、应用历史物理异常、生成 bit 或下载。重建后的 ADF 和位流需要重新检查时序、物理约束、生成过程与板上结果，不能继承历史精确位流的签核。
