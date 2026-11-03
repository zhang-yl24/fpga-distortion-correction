当前已上板 S3 的总体资源余量充足。LUT 20.73%、逻辑 FF 13.41%、片上 BRAM 当量 12.58%、APM 22.50%；“画面仍卡顿”不能由资源总量直接解释。

本报告针对最终 ADF `8510ff44a6c5cba81b675ad3bdf249ba93e1be4f2c372f5ff76b855ba761e2a2`，并核对了已成功 SRAM 编程的 bitstream `ae6be718eaa60fdcd1ba252c08133e7e24d22d247d2a649d21f0d1f7be4a4d16`。器件为 Logos2 PG2L100H、-6、FBG676。

资源取自本次实际 **Route Optimize 完成后的**报告，不采用综合估计。最终物理证明记录逻辑网表、FF 放置及路由保持不变，从该最终 PNR 结果关联到已上板的 8510 ADF。所引用产物的 SHA 均在本次重新核对；没有重跑 EDA 或整套物理证明。

| 资源 | 当前 S3 已用 / 容量 | 精确占比 | 冻结 C 已用 | S3−C |
| --- | ---: | ---: | ---: | ---: |
| LUT（工具 LUT 行合计） | 13805 / 66600 | 20.73% | 13776 | +29 |
| 逻辑 FF | 17858 / 133200 | 13.41% | 17652 | +206 |
| LUT-CONST（工具单列） | 1526 / 66600 | 2.29% | 1420 | +106 |
| CLMA 已分配站点 | 4348 / 11675 | 37.24% | 4325 | +23 |
| CLMS 已分配站点 | 1753 / 4975 | 35.24% | 1725 | +28 |
| 分布式 RAM（CLMS 单列） | 610 / 19900 | 3.07% | 610 | 0 |
| DRM／36K BRAM 当量 | 19.5 / 155 | 12.58% | 19.5 | 0 |
| APM 运算单元 | 54 / 240 | 22.50% | 54 | 0 |
| GPLL | 4 / 6 | 66.67% | 4 | 0 |
| USCM 全局时钟缓冲 | 6 / 32 | 18.75% | 6 | 0 |
| BKCL | 5 / 6 | 83.33% | 5 | 0 |
| CCS | 1 / 1 | 100.00% | 1 | 0 |
| PPLL | 2 / 6 | 33.33% | 2 | 0 |
| RCKB | 4 / 24 | 16.67% | 4 | 0 |
| HCKB | 18 / 96 | 18.75% | 20 | -2 |
| IO | 144 / 300 | 48.00% | 144 | 0 |
| TSERDES | 14 / 48 | 29.17% | 14 | 0 |
| DDR_PHY | 7 / 24 | 29.17% | 7 | 0 |

上表百分比由实际数量除以器件容量重新计算；PDS 原表显示向上取整的整数百分比。LUT-CONST 和分布式 RAM 按工具单列保留，不擅自与 LUT 行叠加或相减。

BRAM 口径：最终原生网表实际包含 **18 个 DRM36K_E1 和 3 个 DRM18K_E1**，与冻结 C 一致。合计 `18 + 3×0.5 = 19.5` 个 36K 当量，即 39 个 18K 当量、718,848 bit（87.75 KiB）。器件为 155 个 36K 当量／310 个 18K 当量（697.5 KiB）；两者共享同一容量池，不能重复相加。18K/36K 每块位数另与安装的官方原语模型 MEM_SIZE=18432/36864 核对。

一个容易误读的细节：S3 的 `.rur` 是较早 Route 阶段报告，CLMA 为 4,345；最终 Route Optimize 日志为 **4,348**。本报告采用后者。

双路提帧的资源判断：仅把当前整机可复制资源数量乘二作为粗预算，LUT 为 27,610/66,600（41.46%），FF 35,716/133,200（26.81%），DRM 39/155（25.16%），APM 108/240（45.00%）。这些是算术估算，没有实现或测量双 lane。实际只复制运算链并共享 DDR/IO/时钟时，资源分配会不同。

同时，当前 CLMA/CLMS 已分配站点为 37.24%/35.24%，简单翻倍将达到约 74.48%/70.47%；局部拥塞和时序不能从 LUT 空闲率推出。GPLL、BKCL、CCS 已分别使用 4/6、5/6、1/1，双路应共用现有时钟体系。资源上可以开展独立双 lane 或更大缓存候选，但是否值得先做，仍需按缓存 miss、DDR 等待、处理周期和输出重复帧来判断；本报告不承诺双倍 FPS。

用户反馈“当前画面正常、比之前流畅，但仍卡顿”作为观察保留。此报告不把该观察转换为帧率，也不把某一种等待机制定为卡顿原因。

证据文件（完整路径、SHA、逐行原始数量均见配套 JSON）：
- S3 PostRouteOptimizeLog：[文件](../distortion/results/hdmi-camera-fisheye-s3-planning-20261103-a/955765ce7a-run_route_optimize.log)，SHA256 `049052ee345edc8025f2fee29edf0a6d1d2cd6faba48203ddcfd95b93f352bdb`。
- S3 FinalPhysicalProof：[文件](../distortion/results/hdmi-camera-fisheye-s3-planning-20261103-a/large-originals-index.json)，SHA256 `e2abc4bd5dc9de4f4be940a310974130ae0edec90023f802e8b827e0fd65f9bd`。
- S3 ProgramReceipt：[文件](../distortion/results/hdmi-camera-fisheye-s3-planning-20261103-a/a10ade9dbf-receipt.json)，SHA256 `d7a10e641ab1a5c21122b72e5e4e86879561e033f00caa5b12a5483ae6d65cea`。
- S3 FinalNativeNetlist：[文件](../distortion/results/hdmi-camera-fisheye-s3-planning-20261103-a/large-originals-index.json)，SHA256 `4e0a43daccc241560e7c486db710a3187eedab96334d95a2ffbe09030d33b4f7`。
- C PostRouteOptimizeLog：[文件](../distortion/results/hdmi-camera-fisheye-s3-planning-20261103-a/dd452b1071-run_route_optimize.log)，SHA256 `38b768499423b98b7ee581b2f4c1d1e65e58139c77a2f31542c6eba940708457`。
- C FinalPhysicalProof：[文件](../distortion/results/hdmi-camera-fisheye-s3-planning-20261103-a/large-originals-index.json)，SHA256 `05b8b4ec1a1e2cf454ef6a9fdbb0cc0af82a7b7e3f76bf3a667d1c0a1b0f021f`。
- C ProgramReceipt：[文件](../distortion/results/hdmi-camera-fisheye-s3-planning-20261103-a/950f1f9aee-receipt.json)，SHA256 `2f52c0634bb8c05d2c6a60c6d3e02e09a23cf3f57797408a436e5c321ba651cb`。
- C FinalNativeNetlist：[文件](../distortion/results/hdmi-camera-fisheye-s3-planning-20261103-a/large-originals-index.json)，SHA256 `bc780473ef7254572d7726e0360bfaee99be6f5643d7787462aef3468ee39727`。

机器可读明细：[JSON](HDMI_CAMERA_FISHEYE_S3_RESOURCES_20261103.json)。本次只新增此 Markdown 和 JSON，未修改冻结输入、提交或推送仓库。
