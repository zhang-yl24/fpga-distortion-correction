# O/P 实测封存位流

此目录经用户明确批准发布原始 O/P 位流，供团队核对与复现使用。本次上传没有重新构建、加载开发板或写 Flash。

## 下载和身份核对

文件：[camera-q512-faultcodes-fixed0-diagnostic.sbit](camera-q512-faultcodes-fixed0-diagnostic.sbit)

- 字节数：3,791,112。
- SHA256：`99f8a734161364618e18800de2ebdc01f4c7261c2c6579a8be2b11df870708a9`。
- 最终 ADF SHA256：`95d402d3c69f3b47d0aed01995f66d5921c82f1678dc03313882826b5bc1a53b`；ADF 本身未发布。
- native 输入清单 SHA256：`ebd35b5676bf692d81c949fd33cf90ca7f9870eadece3885eb1d26b6038e9c76`。
- 历史工具：PDS 2025.2 ADS；器件 Logos2 PG2L100H，速度等级 −6，封装 FBG676。引脚和板卡必须与本包原工程合同匹配。

Windows 可用 `Get-FileHash -Algorithm SHA256 -LiteralPath <下载文件>` 校验。勿直接保存 GitHub HTML 页面为位流。结构化身份见 [BIT_IDENTITY.json](BIT_IDENTITY.json)。

## 实测适用模式

1920×1080、电脑 HDMI 数字输入、实测输入 59.94 Hz，输出扫描约 60 Hz；校正模式，鱼眼 profile `ed59f83e3cfbc77b`，0°，Gamma OFF。既有 O/P 约 63 秒窗口为约 30.011 个新处理/呈现帧每秒；后续同一位流的约 123 秒稳定性采集也已结束并恢复 golden。详细原有结果及边界见 [上级说明](../README.md) 与 [STATUS.json](../STATUS.json)。

此位流含 PGSTAT02 高 24 位故障诊断扩展，不能作为普通正式 v1 固定 profile 的统计包直接解析。它没有完成动态旋转、Gamma 或全部提高任务验收；未提供 full-frame 画面抓取或 KEY 模式切换验收。

两角内部六类时序检查在所用厂商模型下无违例，slow setup +0.068 ns。外部 I/O、CDC、物理复位、热和长期稳定性仍有未完成项。上述数字不是每秒 60 个新校正帧、光学画质验收或端到端延迟。电脑画面也不能用于证明新相机镜头标定正确；本精确位流的摄像头输入兼容性尚未实测。

## 与同学本地重建文件的区别

同学报告的 `stable30-OP-local-20261104.sbit` SHA256 为 `03497abc09f878e596677806c73dbdcf39d7750d66a9da94c8537b7dcfa80e36`，不是此处封存原件；该本地文件未随本次上传。其报告为摄像头输入、DONE=1 后已捕获 26 帧再出现 input A2 / controller B3；我方通过记录使用电脑 HDMI 输入。失败原因仍在核查，不应描述为初始化全程失败，也不能把该记录归到此精确原件。

文件哈希不同只说明字节不同；位流头部时间等元数据也可能改变哈希，不能仅据此断言逻辑不同。重建版需独立绑定源码、83 项外部依赖、约束、工具、ADF、位流与实测输入/初始化时间线，再判断差异。既有[源码准备流程](../README.md#源码与依赖)不承诺新构建复现历史 ADF 或位流哈希。

本次只补原件和身份说明，不改变生产 RTL、约束、厂商依赖或原始板测证据。
