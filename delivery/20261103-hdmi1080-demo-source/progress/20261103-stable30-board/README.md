# stable30首次我方实板：接近30个新显示ID/秒

同学stable30源码e89a2d42c21e6a216df00e4f0fdeb7c94439ba89在我方D工作空间重新编译。测试使用的冻结位流为 **53f37b7e995541be65c4c29a5c8eeba2d5a59cfb5002ebd54f7fb2ea24fa0bdd**，不是同学原包f77c4991…，也不是旧PGSTAT02测量位流57044fe8…或D256/INDEX6候选。

## 实际观察

北京时间2026-11-03 12:04:16开始有界诊断，12:07前后完成恢复golden，最终记录12:07:04所有Job退出。原始UART按我方冻结工具离线重放通过：

| 项目 | 结果与定义 |
|---|---|
| 模式 | 参数8c73465e；固定校正、旋转0°、Gamma OFF，封存Penn开发参数 |
| 主机单调时间窗口 | 60.0035310999956秒 |
| 完整数字扫描记录 | 1798，约29.964903条/主机秒 |
| 不同显示FrameID | 1797，**约29.948237个新显示ID/主机秒** |
| 重复扫描 | 1，完整记录占比约0.055617% |
| signature序列/scan epoch缺口 | 均0；尾部不完整签名0，校验/身份问题列表为空 |
| 命令 | 一次SGA1，零统计请求，无重试 |
| 热观测 | 峰49.6412℃；恢复golden后34.4037–34.5256℃，不代表正式热签核 |

这里采用与原raw SHA绑定的离线完整记录数量1798。原RESULT中的在线CompleteSignaturesSeen=1797保留不改，不能将它改写成1798或直接当最终raw解析数量。

**这些数值测量显示侧新的FrameID，不是内部处理FPS。** 本位流未导出处理cycle或输入SOF/DMA完整丢帧计数，均未测；PGSIG序列无缺口不能证明输入帧零丢失。显示lease与图像CRC也不是摄像头光学唯一帧、画质或镜头标定golden。当前场景/PCLK没有独立重采，不能据此完成新摄像头画质或1080p60校正验收。硬件外部E2E仍未测。

## 源码、构建与厂商模型边界

源码/参数身份为e89a2d42/8c73465e，132项输入逐项核验，另有UART引脚overlay1项。自编译ADF SHA256为81c17610d1bb4f3f2c72459180247d6cf06ff0e21dfbbe67a65935017d36f5e2。Map资源：FF27184、LUT18782.5、DRM19.5、APM69、IO144。双角setup/hold/recovery/removal/skew/MPW共12类内部原生检查均0违例，slow setup最小+0.009ns。

**本次s30-a的匹配厂商异步组实际生效。** 它会豁免涉及rst_clk与两个fast PHY域的跨域检查，不能叫物理复位修复。外部input/output delay仍缺55/111，CDC/硅片复位/长期运行和全局物理签核仍开放；OT1状态异常未完成解释。一次温控有界板显成功不会消除这些边界。

不要套用另一条D256 INDEX6-60路由的结果：该候选三组仅登记、实际未生效，slow setup10213/−2.105ns，未产bit。两者源码/时钟/ADF不同。BIT_IDENTITY中的BoardOperationYet=false是当时准备记录，本页另用之后的完整执行回执说明已发生诊断测试，没有改写原件。

## 与此前成绩分开

- 旧57044fe8… PGSTAT02：nominal125MHz核心窗口20.033094s，468新处理/呈现、23.3613fps，只有两条31ms内部样本。它与本次主机窗口显示ID率的计数定义/时间基准不同，不据两数计算“处理提速百分比”。
- INDEX6连续3帧：规范化60Hz共享行为DDR的真实RTL通过，33.941813ms为数字SOF→首扫描观测；不是本位流硬件延迟，也不是光学E2E。
- 同学1080p60直通：没有DDR/校正的另一条已现场显示路线；不能称本次已实现60个新校正帧/秒。

## 离线工具和来源

本交付只含去标识摘要与analyze_scan.py，其SHA256为18c7e38fd4190a53c17ae193098abf14cd815f74854f7820d4d13a03dc07a6d4，逐字节等于e89a2d42的tools/analyze_scan.py。它仅解析已有文件，不开串口。参数为原始UART文件、--seconds、--param-id、--session-id和可选--output；时间窗口必须来自对应采集记录，不能猜测。

解码器按PGSIG magic定位128B记录并检查header/tail/CRC及身份；这不是PGSTAT02工具的严格整线byte-boundary解析模式。复核使用230169B原始UART，SHA256 d26da7fa747f557ca041a99cec55970a785759a740d36e05c10518cffebff07c。raw、位流、厂商原件和机器路径不上传。PROVENANCE保留原件SHA，BUILD_SUMMARY与DISPLAY_SUMMARY明确派生，不冒充未修改的原始回执。

运行python -B verify_evidence.py只核验已发布摘要、分析器和边界；不重新测板、编译或重跑HDL。所有新整理数据在项目D工作空间，主工程、冻结输入和main分支不改。