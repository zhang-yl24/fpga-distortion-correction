# AE 下一步：同条件 Map，而非继续重复旧仿真

本次已经补齐实际HEAD0/TAG25/FIFO63的候选RTL执行证据。下一项有区分度的工作是**同一工具、相同工程输入的 AA/AE Map 对比**。当前云端没有匹配PDS及完整授权IP，Map/STA均未运行；不能以Icarus代替。

1. 在合法、匹配的本机PDS工程上创建两个独立新目录，先保全现有可回退实现。基线使用 AA cache SHA256 `ff5e551c13083cecf9325b6acef0a00b58f7f1776cd7f5dbec341e52f2082088`，候选只把该文件换为 AE `7a34f75eca6cd8e7eb74ab1adf347572431e26bb8c820b8d2e0032fcc38fed19`。不得覆盖现用工程或活动构建目录。
2. TOP、HDMI1080p60、Brown/KEY1/零旋转/GammaOFF、HEAD0、TAG25、FIFO63、4096深度、512前瞻、行步长2、INDEX7、TIMEOUT26等全部保持一致。Core125MHz、输入/输出像素约束、器件PG2L100H-6/FBG676、厂商DDR/PLL、种子、所有约束和工具版本同源。保留真实编译参数及有序源清单，不能从文件名猜配置。
3. 记录两次 Map 的来源SHA、完整层级 LUT/FF/控制集合、RAM 推断和实际 query FIFO形状。特别检查 head_block[0:3] 及其专属算术锥是否消失，以及是否出现新的逻辑复制或推断变化。56位寄存器只是结构机会，不能直接填成实测FF节省。
4. 若 Map 无收益或其他资源/路径明显变坏，先停在 Map；不要为了“完成流程”继续耗时布线。只有结果值得时才按原配方串行 place、route/hold、独立STA。setup/hold/recovery/removal/pulse/skew全部检查，保留时钟、例外、无覆盖/未约束路径和CDC/I/O审查；不放宽约束、不借用AA的3ps。
5. 新位流必须有独立源码、参数、工具及位流SHA身份。保持现有回退后由同学进行SRAM临时加载，分别验证稳定CORR、KEY1后的RAW、切回CORR、掉信号/首故障与共同复位恢复。现有600秒主机工具锁定原AA的1665586d位流，只能直接用于基线/回退。新候选位流生成并完成同版审阅后，先为其真实SHA准备并审阅对应采集身份配置，再记录600秒原始遥测和逐窗fresh FPS；不能把AA的SHA填作新候选，也不用显示器60Hz代替。

当前公开AE及严格单文件准备工具仍可在研究提交 `c4a07e8535eab4771bef05d1d2de3354041bfaa7` 的 `delivery/20261107-camera1080p60-key1-aa/research/ac-ad-cloud-20261107/` 找到。工具仅校验和独占创建新文件，不调用PDS。一次只验证AE，不把AD优先级或late-select并入本次差分。
