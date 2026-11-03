# tile8 最终上板版本资源占用（2026-11-03）

最终上板 tile8 占用 **13,181 LUT（19.79%）、13,987 FF（10.50%）、35.5 个 36K RAM 当量（22.90%）和 54 APM（22.50%）**。相比 S3，LUT 减少 624，FF 减少 3,871，RAM 增加 16 个 36K 当量；保存的板上测率为 **5 → 15 FPS（3 倍，提升 200%）**。

本次只读取并核对已有报告、原生网表和回执 SHA，没有重跑 EDA、仿真、硬件下载或测率。资源测量原文来自已完成的 Route Optimize；通过物理应用保留及最终网表、FF 布局和布线等价性，将该资源表绑定到本轮最终上板版本。这里没有声称新增运行了最终 ADF 的资源统计。

## 主要资源

| 资源 | S3 最终用量 | tile8 最终绑定用量 / 容量 | 占用率 | 差值 | 余量 |
| --- | ---: | ---: | ---: | ---: | ---: |
| LUT | 13805 | 13181 / 66600 | 19.79% | -624 | 53419 |
| FF | 17858 | 13987 / 133200 | 10.50% | -3871 | 119213 |
| DRM | 19.5 | 35.5 / 155 | 22.90% | +16 | 119.5 |
| APM | 54 | 54 / 240 | 22.50% | +0 | 186 |
| CLMA | 4348 | 3442 / 11675 | 29.48% | -906 | 8233 |
| CLMS | 1753 | 1375 / 4975 | 27.64% | -378 | 3600 |
| GPLL | 4 | 4 / 6 | 66.67% | +0 | 2 |
| USCM | 6 | 6 / 32 | 18.75% | +0 | 26 |
| BKCL | 5 | 5 / 6 | 83.33% | +0 | 1 |
| CCS | 1 | 1 / 1 | 100.00% | +0 | 0 |
| IO | 144 | 144 / 300 | 48.00% | +0 | 156 |

DRM 按 36K 当量计。最终原生网表为 34 个 DRM36K 与 3 个 DRM18K，共 1,308,672 bit（159.75 KiB）；这是同一 RAM 池，不能将两种容量重复相加。总容量 155 个 36K 当量（697.5 KiB），尚余 119.5 个当量（537.75 KiB）。

两份八行 stripe 各使用 8 个 DRM36K，合计新增 16 个实际原语，与相对 S3 的 RAM 差值相符。两份逻辑缓冲合计 60 KiB，深度取整后的有效映射容量 64 KiB，16 个块的标称物理容量 72 KiB。综合映射表与底层原语模式分别记录在 JSON，不能混用。

LUT = CLMA 9,449 + CLMS 3,732；FF = CLMA 10,358 + CLMS 3,629。LUT-CONST 和 Distributed RAM 单列，不再次加到 LUT 总量。表中百分比由用量/容量重算，PDS 原文的整数百分比可能向上取整。

## 完整资源明细

以下为剩余全部资源行，包含共享池的分项，分项不能与总项重复求和。

| 资源 | S3 最终用量 | tile8 最终绑定用量 / 容量 | 占用率 | 差值 | 余量 |
| --- | ---: | ---: | ---: | ---: | ---: |
| ADC | 0 | 0 / 1 | 0.00% | +0 | 1 |
| ANALOG | 0 | 0 / 1 | 0.00% | +0 | 1 |
| CLMA.FF | 13103 | 10358 / 93400 | 11.09% | -2745 | 83042 |
| CLMA.LUT | 9841 | 9449 / 46700 | 20.23% | -392 | 37251 |
| CLMA.LUT-FF pairs | 4507 | 4728 / 46700 | 10.12% | +221 | 41972 |
| CLMA.LUT-CONST | 1066 | 1219 / 46700 | 2.61% | +153 | 45481 |
| CLMS.FF | 4755 | 3629 / 39800 | 9.12% | -1126 | 36171 |
| CLMS.LUT | 3964 | 3732 / 19900 | 18.75% | -232 | 16168 |
| CLMS.LUT-FF pairs | 1558 | 1494 / 19900 | 7.51% | -64 | 18406 |
| CLMS.LUT-CONST | 460 | 363 / 19900 | 1.82% | -97 | 19537 |
| CLMS.Distributed RAM | 610 | 738 / 19900 | 3.71% | +128 | 19162 |
| DDRPHY_CPD | 1 | 1 / 12 | 8.33% | +0 | 11 |
| DDRPHY_IOCLK_DIV | 2 | 2 / 6 | 33.33% | +0 | 4 |
| DDR_PHY | 7 | 7 / 24 | 29.17% | +0 | 17 |
| GSEB | 0 | 0 / 218 | 0.00% | +0 | 218 |
| HARD0 | 1695 | 1780 / 10550 | 16.87% | +85 | 8770 |
| HCKB | 18 | 21 / 96 | 21.88% | +3 | 75 |
| HCKB.HCKB dataused | 0 | 0 / 96 | 0.00% | +0 | 96 |
| HCKB.HCKB-BYPASS | 18 | 21 / 96 | 21.88% | +3 | 75 |
| HSSTLP | 0 | 0 / 2 | 0.00% | +0 | 2 |
| IO.IOBD | 71 | 71 / 144 | 49.31% | +0 | 73 |
| IO.IOBS | 73 | 73 / 156 | 46.79% | +0 | 83 |
| IOCKB | 0 | 0 / 24 | 0.00% | +0 | 24 |
| IOLHR | 143 | 143 / 300 | 47.67% | +0 | 157 |
| KEYRAM | 0 | 0 / 1 | 0.00% | +0 | 1 |
| MRCKB | 1 | 1 / 12 | 8.33% | +0 | 11 |
| PCIE | 0 | 0 / 1 | 0.00% | +0 | 1 |
| PPLL | 2 | 2 / 6 | 33.33% | +0 | 4 |
| RCKB | 4 | 4 / 24 | 16.67% | +0 | 20 |
| RCKB.RCKB dataused | 1 | 1 / 24 | 4.17% | +0 | 23 |
| RCKB.RCKB-BYPASS | 2 | 2 / 24 | 8.33% | +0 | 22 |
| SCANCHAIN | 0 | 0 / 1 | 0.00% | +0 | 1 |
| SPAD | 0 | 0 / 8 | 0.00% | +0 | 8 |
| TSERDES | 14 | 14 / 48 | 29.17% | +0 | 34 |
| USCM.USCM dataused | 0 | 0 / 32 | 0.00% | +0 | 32 |
| USCM.USCM-BYPASS | 0 | 0 / 32 | 0.00% | +0 | 32 |
| LUT-CONST | 1526 | 1582 / 66600 | 2.38% | +56 | 65018 |

## 从原始资源表到实际上板位流的证据链

1. [原始路由资源报告](../distortion/results/hdmi-camera-fisheye-tile8-20261103-a/evidence/publication-c/resource-report-a.md)及[结构化原件](../distortion/results/hdmi-camera-fisheye-tile8-20261103-a/evidence/publication-c/resource-report-a.json)的 build-a ADF SHA256 为 `7bf8bded0b6db30c5c942800a28939bb2aeea90e2fda6bea7e5f5bd9f1e88e6a`。[资源原文 run_route_optimize.log](../distortion/results/hdmi-camera-fisheye-tile8-20261103-a/evidence/publication-c/run-route-optimize.log) SHA256 为 `a65481a18c3e0eb1b43edaecaa96a3fb3f04d81e8783ee04ab04ff9bd18aeeee`。
2. [B 来源清单中的物理应用回执引用（stage-b-002）](../distortion/results/hdmi-camera-fisheye-tile8-20261103-a/approved-evidence-sources-b.json)精确引用该 SourceADF 和资源报告所用的旧原生网表，保存 `RoutesAndPlacementUnchanged`、`OriginalADFUnchanged`、`InitializationPreservedADF`、`SavedADFReadbackMatches` 全 true。其 ResultADF 为最终 `d883052e4912056a91d634e4d6887f49c45ce60dea52266db94df0659b8a3913`。
3. 最终物理证明 SHA256 为 `ed6bb686bf203cf6b48674ecfbaf37a8826aefac42d0fe815e6b3cb35dcd1735`，保存 `NetlistEquivalent`、`AllFFPlacementsEquivalent`、`RoutesUnchanged` 及 `STAAllTenPassed` 全 true；原生路由中的 NETANNOTATE、目标树和非约束语义保持一致。
4. 本次额外读取应用前后两份原生网表，剥除块注释后重计 26 类 V_ 原语、每份 32,521 个实例，逐类型计数完全相同；其中 DRM36K=34、DRM18K=3、APM=54、GPLL=4、USCM=6。应用前网表 SHA 为 `74b386c47d132a3d1fda06496461b53f806ac80fb1891ee4e8e2db5f61997454`，最终网表 SHA 为 `334847b5e342bc33f27f2baf023daa5f73042f1394f3207a68558ea75fea5e70`。
5. 已通过的独立生成前检查及位流验证绑定同一最终 ADF。实际上板位流 SHA256 为 `1236d82f113e1ddb1c5e24502ed1aa03e4758db0a7d6ff17bf9216f0fbd0e4f3`，3,791,112 字节；SRAM 下载 DONE 与器件 ID 确认、未写 Flash。下载、FPS 和独立复解码回执中的 ADF/bit 身份一致。

所有上述来源 SHA 已在本次报告生成前重新核对；完整绝对路径、SHA、原文行号、全部资源数据和复计结果保存在[结构化报告](HDMI_CAMERA_FISHEYE_TILE8_RESOURCES_20261103.json)。 RAM 映射原文另见[apm-drm-lutram-utilization.log](../distortion/results/hdmi-camera-fisheye-tile8-20261103-a/evidence/publication-c/apm-drm-lutram-utilization.log)。publication-c 保存资源原件，阶段 A/B 包保持原字节；约 107.2 MB 的物理应用回执和约 64.6 MB 的完整最终物理证明仅保留上述 SHA 与原始路径引用，不复制进 Git。绝对路径用于记录原始实验来源；仓库读者可从[阶段 B 实测报告](../distortion/results/hdmi-camera-fisheye-tile8-20261103-a/README-stage-b.md)、[位流与测率索引](../distortion/results/hdmi-camera-fisheye-tile8-20261103-a/selected-bit-board-fps-index-b.json)和[本轮位流](../distortion/results/hdmi-camera-fisheye-tile8-20261103-a/evidence/release-b/hdmi_camera_fisheye_top.sbit)读取已发布结果。

## 余量的含义

当前 LUT、FF、RAM 和 APM 均有数量余量，CCS 已为 1/1，BKCL 为 5/6。资源余量本身不能推出多 lane 的可布通性、时序、DDR 带宽或吞吐；15 FPS 来自本轮保存的数字遥测及独立复解码。新重建的 ADF/位流需要自己的验证，不能继承这份历史哈希对应的签核。
