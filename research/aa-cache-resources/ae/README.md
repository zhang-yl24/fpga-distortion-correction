# AE：真实 AA HEAD0 配置的 RTL 差分门禁

本包验证已提出的 AE 单行比较优化，不修改已发布 AA 位流或冻结工程。目标仍为 HDMI 摄像头 1920×1080、标称 60 Hz，KEY1 RAW/CORR、固定 Brown、零旋转、Gamma OFF。这里只执行核心单时钟 cache 模块，**不是摄像头整帧或实板 60 FPS 验证**。

## 本次新增结果

- 真实参数为 HEAD_PREDECODE=0、TAG_W=25、QUERY_DEPTH=4096、LOOKAHEAD=512、CACHE_ROW_STRIDE=2、INDEX_BITS=7、TIMEOUT_BITS=26。编译后的实例明确断言 query token 为 63 位，未套用假设 HEAD1 的旧 FIFO 节省结论。
- AA 与 AE 的缓存控制、四邻域像素/小数/25 位 tag、DDR 请求、目录与生命周期状态逐周期比较通过。主测试完成 27,100 个查询/输出、80,552 个周期，FIFO 实际达到 4096；有三次在复位前明确断言的低位身份窗口自然跨越，坏 RID 故障及共同复位恢复。
- 定向测试完成 576 个正常查询，覆盖 x=1791/y=50 的 line63→0、127/128 边界、63/64 行界、四角/OOB、极端有符号输入，以及直接注入近 QID24 上限后的故障45与复位恢复。head_unique 比较 8,595 个有效 head 周期，其中 line63→0 场景 704 个观察周期。累计输出578包含注入阶段的2个输出，不能当作576个正常查询出错。
- 故意把候选的 native 比较改成恒相等，定向检查在 133 ns 明确以 `native head_unique mismatch` 拒绝，排除了该检查完全未起作用的情形。故障版本只用于负向测试，不能拿去综合。
- 源码和差异已经独立审阅，无本次 AE 缺陷；两份依赖与公开 AA 逐字节一致。

这四个主测试 cache frame epoch 不是四幅完整1080p相机图像。DDR是离板模型，输入/输出停顿来自测试驱动。比较的是 AA/AE 在这些输入下的等价结果，不是独立光学/图像 golden。

## 优化内容及真实边界

AE只改 head_unique 的一个表达式：精确 native 配置用 `head_line[h]==head_line[z]` 代替全 block 比较；其他配置仍用原 block 比较。两邻居均 bounded 才参与比较。相邻行奇偶不同，同一行的块列相等或只差1，模64不会把差1混同，因此同一2×2 footprint 内的两种相等关系一致。

独立消费锥审查确认：native 分支下，四个14位 head_block 寄存器及只供给它们的 next_head_block 运算不再具有功能消费者；通用分支和共享坐标/line/bounds 运算保留。**这是可由综合去除的结构机会，不是已测得减少56 FF、LUT、DRM或时序改善。** 项目级保留约束和真实网表尚未审查。

本包没有改变时钟、FIFO宽度/深度、调度流水、DDR协议、KEY1、Gamma、旋转或像素算法。该优化不减少 RTL 周期；若有资源或布线收益，只能由同条件 Map/STA 给出。AA原3 ps setup余量不能转给AE。

## 复现

只需 Python3 和 Icarus Verilog，标准库脚本不访问网络、串口、JTAG或厂商工具：

```
python run_rtl.py --iverilog iverilog --vvp vvp --output my-head0-run
python run_rtl.py --iverilog iverilog --vvp vvp --testbench directed_native --output my-directed-run
python check_negative.py --iverilog iverilog --vvp vvp --output my-negative-run
```

输出目录必须不存在。缓存原件保留在 sources/，只在新输出目录生成改名后的测试实例。results/ 保存本次执行回执、日志和哈希；SHA256SUMS.txt 约束交付文件。原始源码来自公开 AA `ea180eb7` 和研究 AE `c4a07e85`，完整SHA见 SOURCE_IDENTITY.json。

## 未覆盖与下一步

- Map、place/route、独立STA、bitgen、CDC/I/O及实板：均未运行。缺匹配授权PDS/IP，用户电脑离线；本包不含厂商实现、许可证或可烧板文件。
- 主测试 triple_overlap=0、accept_done=0，这两种同时事件未覆盖，不能写成通过覆盖。
- 日志的 WINDOW_CROSSINGS=4 含一次复位造成的监测跳变；可靠的自然跨越结论是复位前已断言的至少3次。
- 日志的 quarantine=30 指30个周期的差分观察，不是独立证明整段完全静止或没有接收/输出。
- Nonnative fallback未执行新RTL回归；仅确认条件为假时表达式原样保留。新实现同条件对比与同版相机验证见 MAP_NEXT_ZH.md。

AE是单独的资源候选，不与 late-select 或 AD 路由优先级候选叠加，不据此宣称持续60个新校正帧或端到端延迟已改善。

若从 Git 获取，请保持 sources/ 的原始字节；Windows 自动换行转换会被严格 SHA 检查拒绝。公开日志只规范化本机工作目录前缀，前后哈希见 PUBLIC_LOG_NORMALIZATION.json；原始数据和源码身份没有改写。
