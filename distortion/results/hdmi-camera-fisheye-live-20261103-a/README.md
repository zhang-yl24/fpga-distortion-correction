# 已上板 C 版原始证据

本目录保留 2026-11-03 新 HDMI 摄像头鱼眼 C 基线下载、三次只读 UART 和用户观察原件。下载时间 10:58:55（北京时间），SRAM/DONE/器件 ID 通过、Flash 未写。位流 SHA256 `8c43a77d9ddce72dc7015ef7f63aabe37ab6758dd698e2e811b669c5aa5ba047`。

矫正 / 原图 / 切回矫正分别实测约 4.31 / 30 / 4.27 FPS，HDMI 扫描为 30Hz。完整说明、位流、源码、标定与 portable 验证见[本次交付](../../../delivery/20261103-hdmi-camera-fisheye-c/README.md)。

原件清单 `evidence-manifest.json` 绑定原始回执、wire.bin 和补充复算报告；原始说明保留在 `README.original.md`。其中绝对路径和提速接续链接是当时本机记录，不是干净克隆依赖。旧 `verify_live_baseline_resume.py` 同样保留为历史原件；请使用交付目录的 `verify_release.py` 在任意机器离线验证，不直接运行依赖历史路径的旧脚本。

本次发布附有程序日志、构建/仿真摘要。大型 STA 和完整物理数据库保留在原机器；原始 bit 验证记录只证明该精确产物当时的签核，新构建须独立重新验证。
