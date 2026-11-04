# 同学 1080p15 directfill 选定版源码契约

审计固定 main `327ef108f48b467b8bbe5c4e67f9b503e4983b50`。main 已由 `8f2a5b76` 前进一笔报告提交；`delivery` 和 `distortion` 子树仍与先前快照相同。选定生产来源是 `45223998ce3695960297937519d37759499bb4f5`，最新 `14397de2` 的256 KiB缓存研究没有作为已板测版本使用。本轮只读远端，未访问正在构建的D盘工程、运行EDA或操作硬件。

## 应选择的精确入口

`delivery/20261104-hdmi-camera-fisheye-tile8-directfill/submission/`；实际顶层 **`hdmi_camera_fisheye_top`**，实际编译顶层是 `compiled-snapshots/board/hdmi_camera_fisheye_top.v`，其 `INPUT_TIMING_CONFIGURED=1`；原 `source/board/` 副本为0。选定位流SHA256 `aa21991374fbeb4a6733741095f38e27336f1e47dd67b963feb243428a5b353b`，3,791,112字节，PG2L100H-6-FBG676。[源码/证据](https://github.com/zhang-yl24/fpga-distortion-correction/blob/327ef108f48b467b8bbe5c4e67f9b503e4983b50/delivery/20261104-hdmi-camera-fisheye-tile8-directfill/submission/README.md#L3)

生产清单列110输入，当前提交内110路径均存在；其中22份关键源码在本轮重算SHA256与生产清单一致。6份实际编译差异为5次绑定头文件路径迁移与1次顶层参数选择；另外104份原记录字节不变。包是选定生产输入/证据闭包，**尚不能宣称在另一电脑一条命令即可精确重建最终物理实现**：原plan保留历史P:/及工具路径，后续物理约束/最终ADF链需要另行重建。[源码/证据](https://github.com/zhang-yl24/fpga-distortion-correction/blob/327ef108f48b467b8bbe5c4e67f9b503e4983b50/delivery/20261104-hdmi-camera-fisheye-tile8-directfill/submission/README.md#L9)

## 图像、DDR和模式契约

- 输入RGB888共用PCLK采样级，再经两拍四舍五入量化；DDR是RGB565，256bit一拍16像素，地址单位4字节。INDEX8指缓存索引，不是8bit像素。固定1920×1080、KB4镜头ROM/profile `ed59f83e3cfbc77b`，Gamma关闭、无旋转，74.25MHz输出30Hz扫描。约15个新结果帧/秒与输入约60Hz、输出扫描30Hz分列。[源码/证据](https://github.com/zhang-yl24/fpga-distortion-correction/blob/327ef108f48b467b8bbe5c4e67f9b503e4983b50/delivery/20261104-hdmi-camera-fisheye-tile8-directfill/submission/compiled-snapshots/board/hdmi_camera_fisheye_top.v#L73)
- 只有四个4MiB槽：源0/1、结果2/3，基址单位分别0、0x100000、0x200000、0x300000；每帧4,147,200字节/129,600拍。输入只有一份保留的reservation/source-valid mailbox，不能直接替换成另一条路线的描述符/槽位约定。Pango UI没有WVALID或B响应；WREADY消耗数据，WLast由控制器返回，首拍可与AW同拍。[源码/证据](https://github.com/zhang-yl24/fpga-distortion-correction/blob/327ef108f48b467b8bbe5c4e67f9b503e4983b50/delivery/20261104-hdmi-camera-fisheye-tile8-directfill/submission/compiled-snapshots/board/hdmi_camera_fisheye_top.v#L108)
- KEY1 C23低有效，2FF和125MHz下20ms释放/按下去抖；上电默认校正，复位按住不会触发，长按只切一次。**模式与bank接受的source id/bank同拍锁定**，再由engine、mapper、writer在共同frame握手沿锁定；处理中按键不能追改该帧。原图也通过相同DDR/校验/显示所有权链，不做异步输出mux。LED6与UART仅报告请求模式，没有“已显示模式”ack。[源码/证据](https://github.com/zhang-yl24/fpga-distortion-correction/blob/327ef108f48b467b8bbe5c4e67f9b503e4983b50/delivery/20261104-hdmi-camera-fisheye-tile8-directfill/submission/compiled-snapshots/board/hdmi_camera_fisheye_top.v#L213)
- 源commit要完整像素数、拍数、bank/id、capture CRC和写后CRC相符，并清空FIFO返回/校验/部分burst；源bank仅在engine完成并校验结果身份后释放。结果须完整写完才pending。显示lease包含id/bank/CRC/epoch；reader完成和像素完成都正确、reader idle、FIFO为0且无fault，才可释放。[源码/证据](https://github.com/zhang-yl24/fpga-distortion-correction/blob/327ef108f48b467b8bbe5c4e67f9b503e4983b50/delivery/20261104-hdmi-camera-fisheye-tile8-directfill/submission/source/rtl/experimental/hdmi1080_capture_cdc.v#L100) [源码/证据](https://github.com/zhang-yl24/fpga-distortion-correction/blob/327ef108f48b467b8bbe5c4e67f9b503e4983b50/delivery/20261104-hdmi-camera-fisheye-tile8-directfill/submission/source/rtl/experimental/ddr_adaptive_result_writer_dualstripe.v#L2)
- 运行故障停止新admission，保持已发布地址/整burst归属；fault为粘滞隔离，坏帧不能发布或释放lease，显示端继续丢弃/排空返回直到共同reset。PCLK watchdog只查时钟活动，不证明帧进展，也不擅自释放bank或reset事务。[源码/证据](https://github.com/zhang-yl24/fpga-distortion-correction/blob/327ef108f48b467b8bbe5c4e67f9b503e4983b50/delivery/20261104-hdmi-camera-fisheye-tile8-directfill/submission/compiled-snapshots/board/hdmi_camera_fisheye_top.v#L179)

## UART与证据边界

`PGHFPS02` v2，96字节little-endian、115200 8N1，一秒core原子快照，CRC32覆盖前92字节；BuildID `11030001`。源帧、接受帧、处理、新显示、扫描、重复、空白分开计数。underflow槽是0，不是当前欠流计数；没有图像overflow遥测或显示mode ack。长窗cache计数应逐相邻样本modulo32累加，不能直接用端点差跨多次回卷。[源码/证据](https://github.com/zhang-yl24/fpga-distortion-correction/blob/327ef108f48b467b8bbe5c4e67f9b503e4983b50/delivery/20261104-hdmi-camera-fisheye-tile8-directfill/submission/source/rtl/experimental/hdmi_camera_fisheye_status_uart.v#L2)

原保存证据记载双角10表零失败（slow setup最差+0.092ns）、144个引脚、30s/600s窗口约15新帧/秒；这是选定旧bit的证据身份。本轮没有重新运行RTL、原生时序、下载或板测，不能把这些通过结论转移给任何新合并源。外部AC、实际板压、模拟MTBF和完整视场光学验收仍需独立证据。[源码/证据](https://github.com/zhang-yl24/fpga-distortion-correction/blob/327ef108f48b467b8bbe5c4e67f9b503e4983b50/delivery/20261104-hdmi-camera-fisheye-tile8-directfill/submission/README.md#L21)

## 合入前必须保留的选择

`board1080_top.v`与`board1080_checked_top.v`都声明旧`board1080_top`，不是选定top。读仲裁同名`ddr_read_arbiter`在选定版来自`experimental/ddr_read_arbiter_fill8r2.v`，与O/P原件不同；DMA同名也不同字节。写仲裁这两份副本确为同blob `424fd88d`。选定writer为`ddr_adaptive_result_writer_dualstripe`，O/P旧文件声明`ddr_adaptive_result_writer_capture_local`并含多个overlap实现。不得用目录glob或文件名覆盖替代精确source manifest；详细Git SHA、110条输入和全部关键事实行号见[机器契约](peer-source-contract.json)。

不另做竞争KEY1候选。下一步离线验收只应围绕现有实现：去抖/复位、source-id绑定模式、任意ready/DDR服务停顿、四槽不重用、结果/显示CRC与完整计数、同时fault+release、共同epoch reset。要求全帧像素/tag/CRC scoreboard，无混合模式、半帧发布或错误释放。各项通过标准已列入JSON；本轮未执行这些回归。物理重建与上板由原硬件任务继续。
