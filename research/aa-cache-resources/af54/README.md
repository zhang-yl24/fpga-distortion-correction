# AF54：AA 查询序号辅助 raster tag 压缩候选

这是仅含源码和验证证据的资源研究候选材料，不是可直接上板的固件。基线为 `zhang-yl24/fpga-distortion-correction` 的 `delivery/20261107-camera1080p60-key1-aa` 分支，冻结提交 `ea180eb7b57b8a0115e2ce793553034ca5b65a24`。不包含 AE 的比较器改动。

## 文件与来源

- `overlays/`：仅 7 个变更的第一方 HDL 文件，逐字节保留候选源码。
- `PUBLIC_IDENTITY.json`：已有公开 AA native 树的 75 个输入，含 Git blob SHA-1 和 SHA-256。总数是 75，其中 7 个变更、68 个不变。
- `SOURCE_IDENTITY.json`、`AA_to_AF54.patch`：7 个文件的前后哈希及完整补丁。
- `CONFIGURATION.json`：精确配置；`PROOF.md`、`check_traversal.py`：证明和独立全遍历模型。
- `tests/`：原始测试台，未改动语义或字节。
- `materialize.py`、`run.py`：离线、安全的重建及可移植测试入口。
- `evidence/`：已有测试的紧凑日志和 JSON，不含 VVP 或整棵源代码副本。
- `EVIDENCE_PROVENANCE.json`：原始与公开材料哈希。原始证据在私有工作区保持不变；公开日志仅替换绝对工作区前缀。结果 JSON 内原有 RunLogSHA256 等字段仍指原始日志，公开文件哈希见该 provenance 清单。
- `PACKAGING_VALIDATION.json`：可移植入口的重测及安全检查；`ALLOWLIST.sha256`：本目录完整文件清单与 SHA-256（不含清单自身）。

本目录不含 vendor 实现、许可证、ADF、bitstream、sbit、生成的 VVP，或原有 75 文件树的重复副本。源码中的第一方模块引用并不意味着提供了被引用的 vendor 模块。

## 精确范围

实际配置为 1920 × 1080、HEAD_PREDECODE = 0、TAG_W = 25、QUERY_DEPTH = 4096、LOOKAHEAD = 512、CACHE_ROW_STRIDE = 2、GROUP = 64、MACRO = 32。保持固定 Brown、Gamma OFF、KEY1 和零额外旋转。

`AF_AA_ORDINAL_TAG_PACK` 在通用模块中默认为 0，只有专用复制 TOP 默认为 1。这是依赖查询顺序的显式契约，不是适用于任意 tag 的压缩。外部 tag 仍为 25 位；FIFO 只保存 `{mask, raster[20:6]}`，实际声明宽度由 63 降为 54。深度 4096 时减少 36,864 个逻辑 payload bits；尚无物理 LUT、DRM 或时序收益测量。

非法 tag 触发 sticky fault `0x4A`，违规 token 不得进入 query FIFO。低位违规 token 可以先进入 skid/decoded 阶段。检测边沿已有合法流量仍可能继续前进，不能把这一行为描述成全局静默。

## 离线复现

使用 Python 3 和 Icarus Verilog（原验证为 12）。从已冻结 AA 交付目录取 `native/`，其中应有 `source/` 和 `b4/`。必须显式提供路径，脚本不联网、不查找硬件、不调用 vendor 工具，也不自动定位其他交付。

```sh
python3 materialize.py --aa-native /path/to/frozen-aa/native --output /new/af54-work
python3 /new/af54-work/run.py proof --output /new/proof-results
python3 /new/af54-work/run.py units --iverilog /path/to/iverilog --vvp /path/to/vvp --output /new/unit-results
python3 /new/af54-work/run.py busy --iverilog /path/to/iverilog --vvp /path/to/vvp --output /new/busy-results
# 可选，耗时更长：实际 cache 差分，不是整帧摄像头测试。
python3 /new/af54-work/run.py full --iverilog /path/to/iverilog --vvp /path/to/vvp --output /new/full-results
```

所有输出目录必须不存在；已有目录会被拒绝，不能覆盖旧结果。重建输出不得位于冻结的 AA native 输入树内，也不得位于本发布目录内；检查会解析符号链接后再判断，且在创建输出前拒绝这些位置。重建先验证 75 个输入的 Git blob SHA-1 和 SHA-256，再验证并应用 7 个 overlay。仅清单内文件会被复制；旁边的 vendor 文件或旧 sbit 不会被带入。新工作区中 baseline 保持 AA，candidate 应用 AF54，测试依赖从该树生成。

严格层次检查默认不忽略缺失模块：

```sh
python3 /new/af54-work/run.py hierarchy --output /new/strict-results
# 仅在明确需要“部分参数绑定”时选择以下模式，不是 build pass。
python3 /new/af54-work/run.py hierarchy --allow-partial-missing-modules --output /new/partial-results
```

原严格检查因缺少 `cfg_pll`、`bringup_pll`、`GTP_INBUFGDS`、`ddr3_test` 失败。`-i` 的成功只能证明已检查部分的参数绑定；入口会将其标为 `PARTIAL_PARAMETER_BINDING_ONLY`。

## 已有证据与覆盖缺口

1. 独立模型遍历 2,073,600 个唯一输出，末尾 24 行有 46,080 个输出；高位与低 6 位关系全部成立。
2. 21 个短单元测试通过，包括默认关闭、通用 TAG8、非法高/低位及 8 个不兼容配置。这些是 OOB-only 测试，不验证 DDR 数据路径。
3. 实际 AA/AF54 cache 差分通过：28,560 个查询及输出、121,688 个周期、最大 FIFO 占用 4096、DDR 请求 5488；覆盖普通与最后 24 行前缀、最大地址、像素/tag/control/state 的逐周期等价。这些是 cache epochs，不是完整 1080p 摄像头帧。
4. 3 个压力拒绝场景通过：在 DDR 在途压力（前缀 8）、head 替换压力（前缀 64）、以及曾达到 FIFO 满的压力（前缀 4105，occupancy 4096）下建立场景，再注入坏 tag。违规 token 未被接纳，fault 为 `4A`。case 1 的替换条件在注入时成立，错误在 2 个周期后检测；case 2 先达到 FIFO 满，再释放压力以让坏 token 到达验证阶段。这些测试不声称压力状态在故障检测同沿仍全部成立。
5. `WINDOW_CROSSINGS = 4` 包含 reset，仅断言 reset 前至少 3 次自然跨越。`triple_overlap = 0` 和 `accept_done = 0` 未覆盖。日志中的 30-cycle quarantine 是差分观察期，不代表全局静默。

打包只重跑了模型、21 个单元及 3 个 busy negative 场景，没有重复耗时的 full differential。HDL 和测试台没有改变；历史完整差分证据与当前可移植入口验证分开记录。

## 下一步 Map 验收

在有授权的本地 vendor 环境中创建独立 AF54 工程，使用同一冻结 AA 约束和器件设置，只替换 7 个已校验文件；不要覆盖原 AA 或其他候选工程。先核对专用 TOP 与上述 native 参数，保持 Brown、Gamma OFF、KEY1、零额外旋转。

首先对 AA 和 AF54 分别运行可比较的综合与 Map，记录工具版本、器件、约束、源码哈希和实际 elaborated 参数 dump，确认 AF54 的 `AF_AA_ORDINAL_TAG_PACK = 1`、`TOKEN_W = 54`。比较 FIFO 的真实映射及 LUT/FF/DRM，检查推断 RAM 是否实际减少。只有 Map 结果值得继续时，才进入布局布线与 STA，检查 tag 重建路径、最差路径、WNS/TNS，并按需要推进 CDC、I/O 和板级回归。不要自动将候选推进到后续实现或上板阶段。任一项未做都标为 NOT_RUN，不能用逻辑位数代替物理收益。

现有 600 秒 `aa_capture.py` 的身份校验锁定已发布 AA 的 sbit SHA 前缀 `1665586d`，只能直接测量该 AA 基线。新构建的 AF54 镜像必须记录其真实 bitstream SHA，并使用经过单独审查、与该镜像匹配的采集器身份配置。不得将 AA SHA 声称为 AF54 的身份，也不得仅为通过校验而沿用或伪造基线 SHA。

当前 Map / STA / bitstream / board / CDC / I/O 均为 **NOT_RUN**。发布本材料不会改变这一状态；没有许可证或 vendor 实现的分发授权。
