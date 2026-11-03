# tile8 鱼眼矫正：阶段 B

阶段 B 保存本轮真实最终物理证明、选定位流、易失 SRAM 下载、COM7 默认矫正测率和独立保存字节复解码。阶段 A 原件保留。归档时间（UTC）：2026-11-03T13:36:52.915836+00:00。

| 指标 | 本轮 tile8 | S3 基线 |
| --- | ---: | ---: |
| 矫正新画面 FPS（名义时钟） | 15.000000 | 5.000000 |
| 矫正新画面 FPS（主机到达时间） | 15.000262 | 5.000101 |

主机计时新画面 FPS 相对 S3 改变 +199.999%。本次测率调用持续 30.009 秒，保存 30 个样本；计数器窗口 29.000000 秒，主机样本窗口 28.999494 秒。处理 FPS 为 15.000000，扫描刷新为 30.000000 Hz。

SRAM 下载回执通过、DONE 与器件 ID 确认；未写 Flash。原始串口字节重新解码通过，CRC 拒绝和丢弃均为 0，测量窗口新增空白帧为 0。选定位流 SHA256：`1236d82f113e1ddb1c5e24502ed1aa03e4758db0a7d6ff17bf9216f0fbd0e4f3`；最终 ADF SHA256：`d883052e4912056a91d634e4d6887f49c45ce60dea52266db94df0659b8a3913`。

[状态](status-snapshot-b.json)、[位流与板上测率索引](selected-bit-board-fps-index-b.json)、[明确来源清单](approved-evidence-sources-b.json)、[复制回执](copy-receipt-b.json)、[独立比较](evidence/release-b/independent-tile8-vs-S3-comparison.json)。本轮尚无用户视觉反馈、光学延迟、长期稳定性或原图／KEY1 切换验收；S3 的历史视觉反馈仅属于 S3。

大型物理报告、ADF 及超过 4 MiB 的证明仅作精确引用，共 11 项；原始来源路径和 SHA 忠实保留。随包文件可离线校验，但本包未包含完整 EDA 安装、全部报告和夹具，不可据此独立重新推导物理接受。

```powershell
python verify_archive_portable.py --manifest portable-evidence-manifest-b.json
```

具备原始 work 证据的开发机还可运行：

```powershell
python copy_evidence.py --sources approved-evidence-sources-b.json --verify-only
```

阶段 B 归档只复制和校验已完成证据，不运行 EDA、不访问硬件、不创建提交或对外发布。
