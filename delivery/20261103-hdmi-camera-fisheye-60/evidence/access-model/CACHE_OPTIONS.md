# 8×8、8 beat 填充路线的缓存访问分析

结论：最值得先做 RTL 周期验证的是 **上 lane index10、下 lane index9，两个 lane 都使用源行补齐到16条线的 row16 索引**。模型总 miss 为 **22,777，较 cache9 direct 的31,147下降26.87%**。索引由源 y 低位与源 x 的128像素块号直接拼接，可保持直映射及现有四邻域读端口组织。已完成的 physical-c（上10row16/下9direct）实际综合占用147.5/155个DRM36K等价，余7.5；两个lane都启用row16的方案仍需另行综合确认。所有推荐方案保持RGB565、原标定、8×8输出遍历、128像素cache line、ARLEN=7的8 beat填充。

若要求两 lane 同为index9，4way tree-PLRU、row-stride35 索引得到 **22,061次miss，下降29.17%**；需要增加路比较、选择和PLRU更新，优先级低于简单直映射索引试验。2way LRU row35为24,890，下降20.09%。整个分析只写本目录，未改RTL。

## 模型与复核

- 上 lane 输出行 `[0,544)`、1,044,480个查询；下 lane `[544,1080)`、1,029,120个查询。各自8×8 tile顺序与独立冷缓存。
- 输入为 `D:/f60-work/fisheye-c-q8-1920x1080.i32`，Q8坐标SHA-256 `61354e91b499900343753f63687642d4672bba8ea717eefc8ecdd034f387a7a1`。来源和整数运算见原 `mapper_access.py`、`map-generation.json`。
- 第一轮70组配置、扩展搜索覆盖低成本源行步长与折叠索引。完整每lane计数在 `all-options.csv`、`results.json` 和 `expanded-results.json`。
- 基准模型复现完整 RTL 的 **miss=31,147、hits=7,422,805**，对应 `e8-cache9-pressure12/sim/engine-result.json`；latency40运行得到相同计数。
- 第二个独立的坐标直接遍历模型复核index9/10、direct/row16/row7的12个lane配置，另验证强制miss不变、3C分解相加、奇数索引置换不改变轨迹等，共19项通过，见 `verification.json`。
- 这里统计真实坐标访问所需的fill和慢路径次数。DDR仲裁、寄存流水代价和每lane完成先后会影响FPS，表中不将miss下降直接换算为帧率。

## 同容量结果

| 配置 | 上 lane miss | 下 lane miss | 合计 | 对 cache9 direct |
| --- | ---: | ---: | ---: | ---: |
| index8 direct | 19,588 | 17,932 | 37,520 | +20.46% |
| index8 xor(line>>8) | 22,842 | 20,975 | 43,817 | +40.68% |
| index8 2way direct | 22,599 | 20,352 | 42,951 | +37.90% |
| index8 4way direct PLRU | 24,236 | 21,837 | 46,073 | +47.92% |
| index9 direct | 15,210 | 15,937 | 31,147 | +0.00% |
| index9 xor(line>>9) | 17,229 | 16,401 | 33,630 | +7.97% |
| index9 row16 | 16,839 | 15,494 | 32,333 | +3.81% |
| index9 row39 | 14,929 | 13,642 | 28,571 | -8.27% |
| index9 2way row35 LRU | 11,996 | 12,894 | 24,890 | -20.09% |
| index9 4way direct PLRU | 13,347 | 13,416 | 26,763 | -14.08% |
| index9 4way row35 LRU | 11,049 | 10,515 | 21,564 | -30.77% |
| index9 4way row35 PLRU | 11,504 | 10,557 | 22,061 | -29.17% |
| index10 direct | 11,685 | 13,185 | 24,870 | -20.15% |
| index10 row16 | 7,283 | 7,727 | 15,010 | -51.81% |

index8每lane64KiB、index9每lane128KiB、index10每lane256KiB。组相联保持总行数 `2^INDEX_BITS`，set数除以ways；4way同时列出准确LRU与可直接实现的3bit/set树形PLRU。128像素一行占256字节。

简单 `line ^ (line >> INDEX_BITS)` 在index8/9均增加miss；对line乘奇数只重新排列set编号，结果精确等于direct。index8下组相联普遍更差，原有set分区恰好保护部分访问，不应假定增加ways必然改善。

## 强制、容量与冲突

两个独立缓存每帧必须首次读取的line数：上lane **7,257**，下lane **7,542**，合计 **14,799**。所有配置的强制miss相同。下表按标准3C分类：首次出现为强制；再次target miss且同容量全相联LRU也miss为容量类；全相联LRU命中而target miss为冲突类。

| 配置与 lane | 强制 | 容量类 | 冲突类 | miss 总数 |
| --- | ---: | ---: | ---: | ---: |
| index9 direct 上 | 7,257 | 287 | 7,666 | 15,210 |
| index9 direct 下 | 7,542 | 0 | 8,395 | 15,937 |
| index9 4way row35 PLRU 上 | 7,257 | 285 | 3,962 | 11,504 |
| index9 4way row35 PLRU 下 | 7,542 | 0 | 3,015 | 10,557 |
| index10 row16 上 | 7,257 | 0 | 26 | 7,283 |
| index10 row16 下 | 7,542 | 0 | 185 | 7,727 |

全相联LRU参考：index8上/下为25,814/23,494，index9为8,034/7,542，index10为7,257/7,542。全相联LRU是分类参考，不代表对这个流的最优下界；分区缓存可保护行而少于全相联LRU的总miss。文件同时提供 `noncompulsory_misses`，可直接查看超出强制读取的总代价，避免把容量类与冲突类混淆。

index10 row16上lane仅26次冲突类miss，下lane185次，已非常接近各自强制读取量。

## 上下lane容量分配

| 上 / 下配置 | 上 miss | 下 miss | 合计 | 减少 |
| --- | ---: | ---: | ---: | ---: |
| 9direct/9direct | 15,210 | 15,937 | 31,147 | 0.00% |
| 10direct/9direct | 11,685 | 15,937 | 27,622 | 11.32% |
| 9direct/10direct | 15,210 | 13,185 | 28,395 | 8.84% |
| 10row16/9direct | 7,283 | 15,937 | 23,220 | 25.45% |
| 9direct/10row16 | 15,210 | 7,727 | 22,937 | 26.36% |
| 10row16/9row16 | 7,283 | 15,494 | 22,777 | 26.87% |
| 9row16/10row16 | 16,839 | 7,727 | 24,566 | 21.13% |
| 10row16/9row7 | 7,283 | 13,617 | 20,900 | 32.90% |
| 9row17/10row16 | 14,496 | 7,727 | 22,223 | 28.65% |

两种只改变一个lane为index10 row16、另一个保留direct的方案都值得做cycle仿真：上10/下9为23,220，下10/上9为22,937。两个lane统一row16时，上10/下9为22,777，下10/上9为24,566，建议先测前者。上10 row16加下9 row7达到20,900，是已测直映射组合中更低的结果；下lane需要额外窄加减索引。

最新实际综合已替代早期数据RAM估算：physical-b的同步metadata cache9配置为113/155 DRM36K等价；physical-c的上10row16/下9direct配置为147.5/155。一个lane从index9升到10增加34.5，其中数据存储增加32、metadata复制/打包增加2.5，当前余量为7.5。按同类增量估算两lane均index10将达182/155，超过器件容量。physical-c另记录LUT28779、FF41599、APM96；最终时序和其他配置仍以各自PDS为准。两lane index10 row16共15,010次miss可作比较，当前容量预算不支持直接采用。

## 索引定义与实现要点

有效邻域的源坐标记作 `x,y`，`col=x>>7`，原linear block为 `b=15*y+col`，set mask为 `2^SET_BITS-1`。

- direct：`set=b & mask`。
- row16：`set=((y<<4)|col) & mask`。index10直映射即 `{y[5:0],x[10:7]}`；index9直映射即 `{y[4:0],x[10:7]}`。每源行15条有效line占16个slot，col15空置。
- row7：`set=((y<<3)-y+col) & mask`，也可用`b-(y<<3)`；保持当前line内部字偏移。
- row35：`set=((y<<5)+(y<<1)+y+col) & mask`，也可用`b+(y<<4)+(y<<2)`。4way index9时SET_BITS=7，2way时SET_BITS=8。
- row_xor_fold：`set=((y<<4)^col^(y>>(SET_BITS-4))) & mask`，SET_BITS随ways变化。它比row35组相联方案差。

**metadata、valid、selected_line、fill地址和全部四邻域data read地址必须使用一致索引。** 物理数据地址高位换为新的line slot，低4位保留原 `pixel_number[6:3]`。tag和DDR AR仍保留真实linear block，DDR burst地址继续按原线性布局。

源行索引优先在已有x/y解码阶段生成，随坐标元数据进入队列。直接在25bit linear block上组合 `/15` 和 `%15` 会重新引入较长算术链；此处row16本质只需连线。通用WIDTH不适合该映射时保留direct fallback。

2way可用每set1bit LRU；4way tree-PLRU每set3bit，更新顺序固定为邻域00、10、01、11。四个邻域的tag/way命中判断、物理slot选择和PLRU写入需要对齐；无需大排序，但会增加metadata组合量，当前时序优化应先用直映射候选。

## 同一像素的集合冲突与完成性

推荐row16、row7、row35配置在真实映射流中均为0个单查询集合容量冲突。部分折叠方案会让上下源行的不同line落入同一set：index9 `b^y` 共8,092个查询，`b^(b>>4)` 共242个，`b^(b>>5)` 共92个，`b^(y>>2)` 共81个；示例源坐标、linear block和set见 `query-conflicts.json`。这些方案不推荐。

现有RTL慢路径为SELECT→SLOW_LOOKUP→CHECK→LOAD/PICK，先保存当前邻域像素，再令neighbour递增。即使后一个line驱逐前一个line，已保存的像素仍可使用；正常DDR返回时每个查询有限次完成，不依赖四条line同时驻留。若将慢路径改为“不断填充直到all_hit”，上述自冲突查询会无法完成。hash只改metadata而未同步data slot也会造成错误，因此后续RTL必须同时做像素与CRC全帧验证。

## 复跑

```powershell
node D:/f60-work/cache-options/analyze.mjs
node D:/f60-work/cache-options/expanded.mjs
node D:/f60-work/cache-options/verify.mjs
```

`comparisons.json`保存主要混合容量方案，`all-options.csv`是全配置每lane数据，所有报告均为分析证据。
