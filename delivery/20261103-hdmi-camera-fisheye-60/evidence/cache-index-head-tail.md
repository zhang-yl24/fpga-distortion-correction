# Cache decoded index head/tail 修复

RTL SHA-256：`a77a7fb5d527b8de0728719a634db6b9de7f6bd086d39e35dcc692661a34a1fe`。测试 SHA-256：`e03d0bd9c5c04e703513c782fed35a317c92ffc489cea0f250a3e1e26c7d300f`。

G 原生路径 `decoded_read` → 两槽 index 读取 → metadata index → valid_lines 选择 → query_cached_valid 的最差 slack 为 −1.805 ns；总 Data delay 9.340 ns，其中 route 8.258 ns。pointer fanout 112 对应 2.682 ns，metadata index fanout 129 对应 3.329 ns。

本次仅将 4×INDEX_BITS 的两项索引存储改成直接 head/tail 寄存器。metadata 和 query_line_index 直接读取 head；坐标、pixel_number、fraction、tag、bounds 保持原两槽存储，队列计数、读写指针、ready、metadata 读使能、slow refresh、DDR 与数据 RAM 均保持原协议，无新增拍。

队列规则：count=0 的 push 写 head；count=1 的 push-only 写 tail，同时 push/pop 用新值替换 head；count=2 的 pop 令 head=tail。当前 admission 使用 `count<2`，满队列不允许同拍 push，即使有 pop。未来若修改为 full+pop lookahead，必须同步调整 tail 更新规则。

四组 XSim 回归通过：row-padded INDEX10/PREDECODE=0、1，以及 linear INDEX7、9。证据位于同目录 `cache-index-head-i10-p0`、`cache-index-head-i10-p1`、`cache-index-head-i7`、`cache-index-head-i9`。

每组新增的独立 circular-slot shadow 在边沿前和 NBA 后检查 head/tail：head 1126 次、tail 84 次；count0/1/2 分别覆盖 1530/521/42 拍，122 次同时 push/pop，9 个故障驻留拍、86 个 reset 拍。使用真实 warm cache 与输出背压填满 inner decoded FIFO，再注入 unsolicited R 并复位，验证 head/tail 冻结和失效。原测试的错误场景保留外层两项队列，新场景补充内层驻留覆盖。

每组原行为检查仍通过：7 次年轻 query refresh、784 次 metadata 实际读取地址对照、2694 次启用 RAM 端口地址对照、189 个独立数值 query、467 次实际 RAM 内容检查。首结果 5 拍、64 个连续结果用 63 拍；32 组每拍变化的 XY/fraction/tag 结果用 31 拍。rowpad 实际不同于 linear 的邻点索引 458 次。

第一轮新增覆盖断言因 inner 队列未驻留故障而失败，所有功能与等价断言当时通过；补充上述非空队列故障场景后四组通过。失败运行保留在 `D:/f60-work/cache-index-head-i10-p1`；最终证据目录只收录完整通过版本。

本次 H 仅包含 writer 私有 payload 预取和该 index head/tail 改动。G 还存在 read_bus/state → cache RAM 的 −1.309 ns、writer beat → send_data 的 −1.593 ns、selected_block → valid_lines 的 −1.585 ns 等路径，后续以新原生快照确定瓶颈。数字单元通过与物理时序验收分别记录。
