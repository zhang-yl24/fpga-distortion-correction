# tile8 鱼眼矫正：15 FPS 上板版本

2026-11-03 的 tile8 候选使用 8×8 访问和双 8 行条带缓冲。默认矫正模式完成新画面的数字测率为 **15.0 FPS**，S3 基线为 **5.0 FPS**，达到 3 倍（提升 200%）；显示扫描刷新仍为 30 Hz。

本轮仅下载到易失 SRAM，未写 Flash。30.009 秒采集保存 30 个连续样本，首末计数窗口为 29 秒，新增完整结果 ID 435 个。独立主机计时为 15.000262 FPS。保存的串口字节重新解码通过，窗口新增空白、CRC 拒绝、丢字节与故障均为零；未据此推断光学曝光帧率、端到端延迟、视觉质量、长稳或 KEY1 往返切换验收。

选定位流 SHA256 为 `1236d82f113e1ddb1c5e24502ed1aa03e4758db0a7d6ff17bf9216f0fbd0e4f3`，大小 3,791,112 字节。最终 ADF SHA256 为 `d883052e4912056a91d634e4d6887f49c45ce60dea52266db94df0659b8a3913`。

- [本轮位流](../../distortion/results/hdmi-camera-fisheye-tile8-20261103-a/evidence/release-b/hdmi_camera_fisheye_top.sbit)
- [发布结果与证据](../../distortion/results/hdmi-camera-fisheye-tile8-20261103-a/README-PUBLISHED.md)
- [源码与重建输入](SOURCE_README.md)
- [离线校验](VERIFY_README.md)

`source-manifest.json` 绑定 110 项生产输入与选定位流；6 份冻结编译快照保留当时受审查的 include 路径重定位及数字时序参数。准备新构建只复制和重定位输入，不运行 EDA，也不继承历史物理验证。
