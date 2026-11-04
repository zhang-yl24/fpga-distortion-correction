# 已持续实板约30fps的O/P源码交付

按用户要求封存已持续实板运行的30fps版本，继续以1920×1080、输入/输出60Hz、每秒60个新校正帧为目标。**O/P不是60个新校正帧/s，也不是全局时序、热/长期稳定或全部基础/提高任务完成版。**

## 身份与选择

主版为O源码、P持续板测：bit **99f8a734161364618e18800de2ebdc01f4c7261c2c6579a8be2b11df870708a9**；ADF **95d402d3c69f3b47d0aed01995f66d5921c82f1678dc03313882826b5bc1a53b**。147项native输入实际字节逐项核对。原清单BaseDirectory残留L路径，本次按明确O/native原件解析、全量核验，不把旧字段当来源。

R页交织bit00801003…也已板测30.00497fps、内部setup+0.015ns；主工程PromotionDecision明确未晋升替代O/P：没有新FPS改善且O/P最小setup余量+0.068ns较大。STATUS保留R比较及原件SHA，不擅自把它当主回退。Q的−0.010ns实验、H无ACK及L六帧仿真均不是本版验收。

## 已测数字与边界

| 项目 | 同一O/P身份的结果 |
|---|---|
| 输入 | 本机电脑HDMI1080p60数字来源，非匹配镜头摄像头画质验收 |
| 模式 | fisheye profile ed59f83e3cfbc77b、校正、0°、Gamma OFF |
| 处理/呈现 | 9统计包，名义125MHz核心窗口62.976655秒；新处理/呈现各1890，约30.01112fps |
| 扫描/重复 | 数字扫描60.00636Hz；repeat1889/(1890+1889)=49.9868% |
| 整段扫描 | 4085完整签名、2043不同ID、2042连续重复；不能与统计窗口分母混用 |
| 内部耗时 | 稀疏last-cycle inclusive样本24.207232–24.519240ms；不是延迟分布或光学E2E |
| 故障/丢弃 | 根fault全0，DMA dropped端点[0,0]；不证明所有输入帧未被筛选或丢弃 |
| 温控/收尾 | 峰52.6887℃，golden恢复约35.14–35.26℃，原显示恢复、COM关闭、Job退出；OT1及正式热签核仍开放 |
| 命令 | ARM1、统计请求10、Flash0 |

协议是PGSTAT02高24位故障诊断扩展，**不是普通正式v1固定profile**。只上传摘要和原件SHA，不冒称新独立raw重解或新测板。PGSIG为DDR结果RGB565扩展后的注册数字扫描tap，不是光学唯一FPS/物理HDMI采样。

## 实现、资源和时序

tile8、Q512/LOOKAHEAD256、INDEX6/SCATTER8、GROUP64/AWLEN3、earlyjob、实际鱼眼mapper/ROM。小块rowburst writer与行CRC拼接，保留源/结果bank lease及完整发布。不借用同学PR27的15fps、raw或KEY1成绩。

同一O构建资源：FF25952/133200（19.48%）、LUT30952/66600（46.47%）、DRM28.5/155（18.39%）、APM56/240（23.33%）、IO144/300（48%）。Slow/Fast setup/hold/recovery/removal/MPW/skew共12类内部0违例；slow setup **+0.068ns**、fast setup+2.628ns。匹配厂商模型实际异步交互10行，分组负载归属DDR IP。**不等于硅片复位修复或全局物理签核**：输入/输出delay缺55/111，CDC、物理复位、IO、热及长稳待验，blanking仍report-only。

16.622496ms压力模型不代表硬件60；实板约24ms超过16.67ms。继续测ARwait/首R/末R、共享仲裁、bank/display交接，不通过关闭安全条件提帧。

## 源码与依赖

只发布项目输入66项：147份native中的65份项目RTL/参数/约束，另1份项目route priority。绝对include路径只改为native相对路径，其余字节保留。SOURCE_BINDING列原始/导出SHA及每个include变换。新构建不承诺复现历史ADF/bit哈希。

**83份依赖仅列SHA、不发布文件**：厂商DDR/PLL/IP、IP时钟/route约束、生成端口约束及iic_dri/MS7200/MS7210三份供应商来源控制文件。无供应商原件、license、工具、位流、ADF、rawUART、现场图像、账号或私人路径。带penn/1080p30的历史文件名不等于当前参数或EDID时序。

1. python -B verify_export.py：只核导出哈希/状态边界，不执行HDL/EDA。
2. 合法已有工程/合法相容PDS-IP流程准备deps/native/<SOURCE_BINDING.path>及deps/inputs/uart_bound.pcf；83项必须精确匹配SHA，不按文件名替换不同版本或旧30Hz表。
3. python -B prepare_sources.py --dependencies <deps> --output <全新短路径目录>：先核全部依赖，再复制、重定位include、生成map.tcl和PREPARATION.json；不运行EDA/硬件。输出须不存在。
4. 历史工具PDS2025.2-ADS、Logos2 PG2L100H −6 FBG676。Map模板保留原add_design顺序、约束、compile/synthesize/dev_map；只是Map准备，不含完整PDS环境/历史placed数据库。
5. 新物理实现需新Map，核uart_bound.pcf、critical-ca-priority.rcf和匹配DDR IP约束。历史place使用seed2/decongestion1，随后route和带hold修复route_optimize。重新核双角全部检查、模型/例外归属、引脚/CDC/复位/IO，再绑定新STA/bit/板测。不会自动下载依赖或执行PDS，不复用旧ADF冒充新构建签核。

PACKAGE_FILES绑定小包全部文件（自身除外）；父PACKAGE_MANIFEST覆盖增量。CI源码/离线核对不代替EDA/实板；旧PGSTATv1工具不适用于本扩展。

## 已完成与未完成

已完成1080有效像素数字链路、鱼眼profile接入、固定0°/GammaOFF约63秒30fps连续处理/呈现、本构建内部模型时序零违例。未完成60个新校正帧/s、同源camera全视场光学、动态旋转/Gamma整机、延迟分布/E2E、物理复位/IO/CDC/长稳及正式基础/提高任务逐项签核。GitHub交付不等于竞赛已提交。

同学main PR27合并8f365e48…保持不变；仅写既有独立交付分支，保留同学内容，不创建或批准PR。
