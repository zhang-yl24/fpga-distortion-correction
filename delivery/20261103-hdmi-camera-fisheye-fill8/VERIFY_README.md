# 便携离线验证

以下命令均不运行 EDA、不访问串口/JTAG，也不写 Flash。

```powershell
python delivery/20261103-hdmi-camera-fisheye-fill8/verify_source.py
python distortion/results/hdmi-camera-fisheye-fill8r3s3-20261103-a/verify_archive_portable.py
```

源码验证检查 110 份原始输入与原编译角色、6 份冻结编译变换、74 份 DDR IDF 展开、原始 Tcl/plan 的 SHA 关联、精确 seed 3 命令，以及随结果包提供的选定位流 SHA 和大小。结果包验证使用包内相对路径核对文件字节，所需内容来自仓库，无需开发机 `work/`。

原始回执保留当时的绝对路径作为来源，不修改为新机器路径；便携脚本不会沿这些历史路径读取文件。65 MB 最终物理证明、大型时序/路由原件与 ADF 未随包提供，只有摘要和 SHA。因此离线核验只能确认所提供的来源和保存的结果，不等同于独立重新推导完整物理证明。

30 Hz 显示刷新中有 25 Hz 重复帧，新画面为 5 FPS。用户报告正常且更流畅，卡顿仍在。S3 原图帧率、KEY1 往返、光学端到端延迟及配置逐位回读没有完成；旧 C 的原图/切换回执仅作旧版基线。
