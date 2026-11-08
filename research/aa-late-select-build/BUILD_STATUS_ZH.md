# AA late-select 独立构建准备结果

**当前状态：NOT_MAP_OR_STA_PASSED。** 已完成公开第一方源码、固定构建配方、外部输入清单与防误用检查；尚不具备完整授权 EDA 输入，不能称为可独立生成位流的完整 PDS 工程。

- 基线固定于 AA 提交 `87cf6ca466ba90d4d18c5d4d82ccd8b1820fde99`。保留78项公开 native 输入和全部原约束；总闭包仍需155项、68项有序直接导入。
- 已验证 late-select system 原始字节保持不变。独立 TOP 只新增 grace=8192 的参数默认值和向 system 实例转发，共两行。System 自身兼容默认值仍为0。
- Brown 固定、零旋转、Gamma关闭、STATS开启、AA cache HEAD=0、RESULT_BANKS=2、KEY1原2,500,000周期消抖不变。Core模型125MHz，输出像素148.5MHz，输入约束150.2MHz。8192周期对应65.536微秒的有界等待窗口，不是整机延迟保证。
- 核对完整公开源哈希、TOP参数及转发、有序导入、约束原样保留，并通过36项静态/构建入口防误用测试。没有重跑旧HDL六帧或60帧测试。
- 缺少77项厂商输入（75项DDR、两个PLL wrapper）；公开资料未提供这77项原件的逐文件哈希。恢复有授权输入或重新生成后，必须记录新哈希并核对371项DDR和两组PLL参数，不能据此声称原件逐字节重现。
- 目标工具为PDS2025.2/Fabric Compiler build211867；DDR生成环境为IP Compiler2022.2-SP6.4 build146967/HMIC_S1.10。PLL的具体生成版本不能从原wrapper认证。不可混同版本，也不提供受限厂商实现或授权文件。
- 此次受检云端没有找到可用的匹配厂商工具或完整IP，因此Map、place、route、STA、bitgen及板测均为NOT_RUN。前置条件检查按预期停止，**不是目标时序运行失败，也不是时序通过**。

以后补齐输入时使用 `tools/run_stage.py`。该入口把真实工具路径、公开源身份、外部IP及工具回执、前一阶段新ADF和已生成报告哈希串起来；拒绝旧输出目录、旧检查点、报告替换、输入/工具跨阶段变更。Bitgen还需要同一路由ADF对应的STA及显式报告覆盖审阅，不把exit0当成签核。原PDS Tcl及选项没有改写。

详细操作见README.md、RECEIPTS.md；时钟网名追踪和原DDR相关时钟/多周期约束见CLOCK_AND_PARAMETERS.md。整个包只包含公开源码/配置及检查脚本，不含厂商IP、ADF、旧位流或可烧板镜像。新实现完成后仍需独立审查资源、STA/CDC、外部HDMI物理时序及真实摄像头验收。
