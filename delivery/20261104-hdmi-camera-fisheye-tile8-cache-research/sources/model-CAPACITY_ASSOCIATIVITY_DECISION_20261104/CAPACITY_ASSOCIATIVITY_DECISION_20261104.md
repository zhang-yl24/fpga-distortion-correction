当前最值得继续验证的是 **256 KiB、2 路 LRU**。完整 2,073,600 条查询从冷 cache 重放后，填充从 37,483 降到 20,630，减少 16,853 次（约 44.96%）；有效 DDR 读负载从 9,595,648 降到 5,281,280 字节。这里的“有效负载”指所请求的 burst payload，不是测得的总线利用率。

| 总像素容量 | ways | fills | slow queries | 邻域 hit 次数 | DDR payload 字节 | synthetic latency40 服务模型相对 INDEX8 省时 |
|---|---:|---:|---:|---:|---:|---:|
| 64 KiB | 1 | 37,483 | 34,705 | 7,416,463 | 9,595,648 | 基线 |
| 64 KiB | 2 | 42,914 | 39,948 | 7,411,032 | 10,985,984 | −3.125080 ms |
| 64 KiB | 4 | 46,004 | 42,943 | 7,407,942 | 11,777,024 | −4.899992 ms |
| 128 KiB | 1 | 31,110 | 28,598 | 7,422,836 | 7,964,160 | 3.644216 ms |
| 128 KiB | 2 | 32,752 | 30,215 | 7,421,194 | 8,384,512 | 2.699776 ms |
| 128 KiB | 4 | 26,457 | 24,293 | 7,427,489 | 6,772,992 | 6.284624 ms |
| 256 KiB | 1 | 24,833 | 22,755 | 7,429,113 | 6,357,248 | 7.211136 ms |
| 256 KiB | 2 | 20,630 | 18,737 | 7,433,316 | 5,281,280 | 9.614664 ms |
| 256 KiB | 4 | 20,841 | 18,954 | 7,433,105 | 5,335,296 | 9.492912 ms |

同容量增加相联路数并不必然减少 miss。64 KiB 的 2/4 路，以及 128 KiB 的 2 路，在这个轨迹上都更差；256 KiB 的 4 路也比 2 路略差，暂不实现。256 KiB direct 是更简单的备选，但其 24,833 次填充比本轮 24,000 的筛选门槛高 833 次。

所有配置均保留完整 block tag，128 pixels/block，set 为 block ID 的低 set bits，每帧从空 cache 开始，按原 query 顺序、每条 query 的 00、10、01、11 邻域顺序访问。越界邻域不分配、不触碰 LRU。LRU 每次有效需求访问均更新；缺失先选无效 way（双无效固定 way0），否则驱逐最久未用 way。fast/slow 判定在该条 query 的任何需求访问之前完成。全部配置各自重放同一轨迹，INDEX8/9 direct 的 37,483/31,110 次填充已复现。完整轨迹共有 14,762 个不同 block、1,734,931 个被请求的不同源像素；256 KiB 2 路仍有 5,868 次重复 block 填充，不等于已到 compulsory 下界。

周期列复用原来的串行慢路 SELECT/CHECK/LOAD/PICK 服务成本：单 outstanding、8 个返回 beat、每 beat 后一拍实际 RAM commit、最后 commit 后才发布 tag。声明的周期 AR 阻塞和 R 空洞，与此前独立模型一致。256 KiB 2 路在 latency0/8/40 时分别省 4.213648、5.296880、9.614664 ms；无 AR 阻塞、无 beat 空洞的同结构模型分别省 3.905608、4.984200、9.298568 ms。latency0 仍未给出 5 ms 余量。模型没有计入相联 tag 比较、LRU 写端口或 way 选择的新开销，也没有重放 mapper、writer、共享 DDR 仲裁、帧 admission、bank 所有权、scanout，因此这些数值不能从旧板上 35.45 ms gauge 直接相减，更不能宣布持续 ≤30 ms 或 >15 新帧 FPS。

这条路线的价值在于减少串行 miss 的首返回等待，和完整仿真 profile 所指出的等待主导方向一致；该 profile 是仿真证据，不能提供板上 DDR latency。像素 RAM 容量粗估为 64 个 DRM36K，加旧非 cache 27.5，约 91.5/155；2 路 tag、复制读端口和 LRU 的额外资源尚需真实映射。INDEX11 像素 RAM 加原非 cache 约 155.5/155，暂不推进。

最小 RTL 实验已经单独放在 `assoc2way256-a/`：总 INDEX_BITS=10，set bits=9，两 way 同步 tag lookup，physical line={way,set}，保留公开接口、FIFO、慢路单 owner、最后 RAM commit 发布和 epoch。必须保持热流 II=1；若相联判断引入每条 fast query 的串行气泡，约两百万条 fast query 会吞掉模型收益。最终进入系统验证前需要独立像素/CRC、双 invalid 优先、LRU 双向驱逐、同 set 异 tag、held younger metadata stale refresh、RESULT stall、fault/reset/末 commit 碰撞通过。当前单元通过不等于 full-system、物理或板测通过。

模型产物是 `full-capacity-associativity-screen-a.json`，SHA256 `1b327fe39f4d4079f8906ab5bea7a1826f94ca9a55d3b05c8c6589cbd9707f14`。独立未压缩 OrderedDict oracle 覆盖随机重复冲突、OOB、完整 tag、LRU、原生前 20,000 条以及冷帧隔离；8 项 CPU 测试实际通过，见 `capacity-model-tests-a.json`。完整 INDEX8 三种 latency 的服务周期与此前独立模型逐项相等。原冻结 RTL、provider、板上 image 和已发布 A/B/C/D 不变；本实验尚无新的时序或上板接受。
