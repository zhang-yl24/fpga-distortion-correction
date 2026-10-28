# K320 开发三联目标与标定来源输入模式对照

两者使用同一 OV5640 init/ROM、原生采样前端和 CAM2 引脚映射；已按 T01 实际 guarded 构建的源 SHA 核对。这里只确认源码等价，新目标尚未上板，各寄存器实值、实际时钟仍未知；开发参数不构成正式标定复用。

|项目|寄存器|两者最终源码配置|
|---|---|---|
|Output size|3808..380B|640x480|
|Sensor crop start|3800..3803|0,4|
|Sensor crop end|3804..3807|2623,1947|
|Offsets|3810..3813|16,6|
|Subsampling increments|3814/3815|31/31|
|Orientation controls|3820/3821|06/00|
|HTS/VTS|380C..380F|1936/1088|
|RGB formatter|4300/501F|6F/01|
|Sync control|4740|23|
|Pad mask|3017/3018|7F/F0 (DYNAMIC_PAD_MASK=1; trial_pad_mask=7FF0)|
|PLL/control bytes|3034/3035/3036/3037/3108|18/21/60/13/01|
|PCLK divider control|3824|02|

两者均在 PCLK 上升沿采样，顶层接 `!cam_vsync/!cam_href`，`HIGH_BYTE_FIRST=0`，按原生 640×480 RGB565LE 保存；raw 前没有裁剪、重采样、旋转或镜像。128 个共同引脚逐项相同；新目标仅没有 guarded 的 UART RX B24。

区别为采集授权：guarded 使用租约/健康门禁，新目标在 camera+DDR+8s warmup 后自动冻结一帧并一次导出三包。该差异不等于模式寄存器实测一致。新目标未实物读取过 crop/方向等寄存器，不能把同名 capture_mode_id 当独立光学证明。
