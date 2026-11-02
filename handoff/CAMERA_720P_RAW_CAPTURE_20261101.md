# 720p 完整原图与模式转移接续（2026-11-01）

## 20:38后最新阶段：第三组通过，板上为VGA原图版

第三组真实720 frame33与VGA原图均接收成功，完整54角点检出；第一组fit01的A逐值不变，只验证held03、不重新拟合。第三组跨模式转移RMS **0.3120311379px**、最大 **0.7409819124px**；固定K720/D、仅solvePnP求每张外参后的目标720重投影RMS **0.2992546507px**、最大 **0.6176820003px**。原session-plan的RMS0.5px/最大1.5px预算未变。

- 实测候选K720为fx=319.4619654229、fy=320.2217583558、cx=643.7313155863、cy=379.2847554790；D完全保留VGA四项鱼眼参数，逆仍为bounded_monotone_bisection_v1/88°前向域。没有用第三组选择或修改K/D。
- 证据目录：distortion/work/camera720-mode-pairs-20261101-a/two-pair-validation-b。paired-transfer-report.json SHA256 d53d18ceab79d49c5fcfaf3c8bac5663e6f1735bcdcd612dfc88bb0b74121c65；target-candidate-freeze.json SHA256 fdc4d1ed782b7908f1b2debf1bd61e02825de4f41b8c0241a1174d1b2cd33267；target-validation-report.json SHA256 a5a22cdea4a36ff9df35d487cbbd1f41b4fac14cdb7214464ab1c70d64a4a32d。
- target.verify从PNG/RGB565/metadata完整重算并与保存结果严格一致，verify跟踪24输入、连同装配共54输入重新SHA核验无漂移；validation-readback.json记录本次核验。
- target实际只含 **1张transfer_held_out，0张new_target_held_out**；角点3×3覆盖为[[6,8,0],[17,23,0],[0,0,0]]，右侧/底部未覆盖，coverage_policy和coverage_passed均null。数值通过支持离线候选开发，不是全视场或实屏光学接受；optical_calibration_accepted、hardware_release_allowed、fpga_mapping_verified仍false。不得臆造固定6张或其他照片数门槛。
- 第二组原失败报告仍是68ac81de…8daf6；用户明确确认相机位移并撤回该对静止声明，原件不改、不进入eligible heldout。背景诊断也发现房间和近FPGA分别有大幅不同位移；第二、第三组720图棋盘角点仅相差RMS0.0580px，这不替代正式跨模式检验。整体世界位姿变化显式记录，光学装配和焦点未调为会话声明、非独立测量。
- **当前板上是raw_camera_capture_cam2_delay的VGA原图固件**。program-modepair03-20261101-a/receipt.json实际20:36:35–20:37:34通过、DONE=true、FlashWritten=false、CleanupErrors=[]，SHA256 89f6d7cc2f25b9ed32d6c1c147adb30c3a8b9a4a63d7f651352d6cd0b89ab21f；pose03-vga/session-summary.json Passed=true、1帧、零拒绝，SHA256 c490f63d33a8de635ae630c5ba0c5d5e84e1a4e9529491f8f3c7b836660497b4。用户已被告知可以松手，无需继续保持棋盘。

接续：实测证据绑定的新camera720_calibrated_top源与构建准备已生成；root已启动distortion/work/camera720-calibrated/build-a的原生诊断（171输入）。新候选自身物理报告/导出/时序/复位/CDC/IO尚待核验，不能继承transport旧final route。尚未生成或下载新矫正位流，720p帧率仍未实测。未来实屏直线检查时可针对右侧/边缘补观察，当前先推进候选开发，不要求用户现在继续采图。没有Git提交/推送。以下保留为历史截面。

## 20:26后历史阶段：第二对固定前提失效，第三组重新配对

第二对实际图像的冻结首对矩阵验证结果为RMS **38.0133003093px**、最大 **58.8957621904px**，原定RMS0.5px/最大1.5px预算未改变。随后用户明确确认相机有位移，撤回该对相机固定的前提；因此该对只能保留为不满足采集前提的失败记录，不能据此认定模式几何迁移不成立，也不能当有效held-out接受。

- 原件 `distortion/work/camera720-mode-pairs-20261101-a/two-pair-validation-a/assembly-summary.json` SHA256 `551d015a92ff5e7ec32c54261741e654bdcb03be357a452affbe21ee055f5c2c`，同目录 `paired-transfer-report.json` SHA256 `68ac81de3a37883dca902906d707ef56a72c94e4c6f45c506bc425b3b478daf6`；不修改报告、阈值或fit01矩阵。
- 第二组720原图确实完整取得：`pose02-720/session-summary.json` Passed=true，frame14为1280×720 RGB565_LE；北京时间20:26:44接收、20:26:51完成，source/received CRC32均 `7C744788`，摘要SHA256 `58e7a29162600d11b71e672e9468ad4a5e13ac5e1a0f22cf0f92ea194b8a41fc`。接收成功不证明几何固定前提。
- 开发板已于20:20:40–20:21:58成功切回720原图版，`program-modepair02-20261101-a/receipt.json` Passed/DONE均true、FlashWritten=false、CleanupErrors=[]，SHA256 `6ee6182e5e189433df351cfa3bf57ba095ea2888037ba2de128ab314daefa847`。
- 用户已明确允许第三组比较并确认摆好固定。root正在只读采 `pose03-720`；VGA准备与等待由同一root进程管理，必须等720接收Passed且串口关闭后才实际切换并采 `pose03-vga`。本交接截面仍为720raw，用户已收到切换通知；不得重复启动PDS/UART/JTAG。后续真实回执覆盖本截面。
- 第三组是候选held03，保持fit01和原预算。当前没有通过的target-validation或冻结正式profile。独立calibrated720 preparer/runner已完成CPU实现及10 tests+14 subtests，尚未用不合格证据准备实际矫正候选，没有新矫正PDS或下载。

`OpticalCorrectionAccepted=false`、`FrameRateMeasured=false`。先完成真实模式几何验证，再推进720p镜头矫正，随后优化帧率。原transport、raw VGA、720raw与VGA校准文件保持冻结；本轮没有Git提交或推送。以下章节保留历史状态。

## 20:15历史阶段：首对fit通过，板上为VGA原图版

用户固定的第一姿态已取得720 frame50及VGA frame6，两侧真实原图、CRC/hash/身份及54角点完整性检查通过。`distortion/work/camera720-mode-pairs-20261101-a/pose01-fit-inspection-a.json` SHA256 `a467530660817401f37612fb34c98c0c16ba0eb0258c2ff6dd0b3da8f4ecb7ee`：54点拟合RMS **0.33103675086284035px**、最大 **0.9797714519124884px**，编号对齐为identity，满足session-plan预先声明的RMS≤0.5px、最大≤1.5px。

首对拟合矩阵（VGA像素坐标→720像素坐标）为：

```text
[[2.0021190701166316, 0, 0.598939240670461],
 [0, 2.003305096187522, -122.02743707675319],
 [0, 0, 1]]
```

这只描述一对fit姿态的坐标关系；`Accepted=false`、`held_out_evaluated=false`，不能据此认定镜头参数转移、720p光学校准或FPGA矫正已完成，也不能把无标记棋盘的编号对齐当方向独立证明。下一姿态须用本矩阵做独立验证，不能用held-out重新拟合。

**当前板上是 `raw_camera_capture_cam2_delay` VGA原图版，尚未切回720。** `distortion/work/raw-camera-upright/program-modepair01-20261101-a/receipt.json` SHA256 `c665c7d9f3d115dc60921f77cdc7a58c5fcd9ab574403140c5b782124aafa7b4`，北京时间20:13:47–20:14:47下载通过、DONE=true、FlashWritten=false、CleanupErrors=[]。`pose01-vga/session-summary.json` SHA256 `e23826ff898bb425a54ab63d2efbb9307928496b107745570fc7448fab65d5bd`，frame6于20:15:29接收，640×480 RGB565_LE、614400字节，source/received CRC32均为 `14B018B0`，rejected_packets=0、binding未漂移。

已向用户请求第二个独立固定姿态，当前回复待定；**用户回复前不采图**。回复后先采VGA held-out，再保持相机、镜头与该姿态固定，切回720原图版采held-out，最后用冻结首对矩阵进行几何诊断。当前没有第二对数据或验证通过结论。帧率仍未实测；保留先720p清晰度与镜头矫正、后帧率优化的顺序。仅更新交接，无Git提交/推送。以下19:55及更早的板上状态均为历史记录。

## 19:55 历史阶段：首张真实1280×720原图接收成功

真实绑定及COM7首帧采集已经完成，不再等待绑定或打开UART。`distortion/work/camera720-raw/frame-a/session-summary.json` 记录 `Passed=true`、来源 `physical_native_camera`：frame17为1280×720 RGB565_LE、1843200字节，source/received CRC32均为 `BE4A63D4`。北京时间2026-11-01 19:55:22接收，19:55:29完成；帧号是固件采集事务号，接收时间不是曝光时刻。

- `RejectedPackets=0`、`InputDrift=[]`、`UARTTransmitBytes=0`、`ReceiverStreamClosed=true`，接收器已关闭串口；本次没有UART发送。
- `InitialDiscardedBytes=1570696` 是从持续运行的数据流中途接入、寻找完整帧边界时丢弃的起始字节，不是坏包或CRC错误。
- RAW SHA256：`afa8c76e632a699d6de2c4cf9c0ebe92913977834c354fbf64568fdfb00c9600`；PNG SHA256：`dde6af8b030c147f2fc148d4e43dd881c809a706f4246d06ff6282acf9a5ef5c`；metadata SHA256：`86ba9d492582b4c502d7beb0bc106c37997e9d48f12c4279dac1eb384e27275a`。三个文件位于 `distortion/work/camera720-raw/frame-a/`，文件名前缀为 `current720-first-native-20261101-a-CAM2-frame0000000017`。
- 根代理已读取summary并查看PNG：房间场景画面完整、正立，无明显行错位；桶形畸变仍可见，没有棋盘。该观察不替代光学标定或逐像素场景真值。
- 当前开发板运行 `raw_camera_capture_cam2_current720` 诊断固件。HDMI预览仍为160×90抽样后放大，UART原始payload是真1280×720，接收端没有几何校正。`OpticalCorrectionAccepted=false`、`FrameRateMeasured=false`；不能把串口导图速度或HDMI刷新率当实际帧率。

下一步做真实VGA/720模式同姿态几何验证，先核对传感器裁剪、缩放与当前镜头关系，不能盲目放大旧K；必要时补独立棋盘图。720p镜头矫正尚未实现，完成该阶段后再优化帧率。本轮没有Git提交或推送。以下19:49及更早章节均为历史截面，其等待绑定/UART/首帧的状态已被本节覆盖。

## 19:49 历史阶段：原图采集位流已成功下载

本节覆盖下方旧阶段的“板上仍为transport”“raw位流尚未生成/下载”。当前板上已经是 `raw_camera_capture_cam2_current720`，不是720p transport单位映射版；本阶段仅诊断采图，不表示720p畸变矫正或外部AC已验收。

- `distortion/work/camera720-raw/bit-authority-b.json` 严格完整验证通过，992项输入绑定；SHA256 `42f7a2fc4940ffb10c88406838a90470d1d5b578e01734cdc6db64a7e7c5c8df`。使用绝对路径proof-b，原严格比较未放宽。
- `bit-a` 位流核验 `Verified=true`，目标 `raw_camera_capture_cam2_current720`，大小3791112字节，头部时间2026-11-01 19:44:40；位流SHA256 `d20f3110cabab0c453ec4bb89190952c1d96210677c2da6288f7cbf011eac951`。`bit-a/verification.json` SHA256 `542b1e20109f9df6e99e797848b74d6f67d1412d5481eb776a102d2d0c4dc688`。
- `program-a/receipt.json` 记录实际下载北京时间19:48:17–19:49:36，`Passed=true`、`DoneConfirmed=true`、`FlashWritten=false`、`CleanupErrors=[]`，SHA256 `6d3ee26575bd701c08fe6c8b0909e281a298402d6c3c896426b56fbe996226c9`。仅下载易失SRAM；复用用户本会话持续上电与检查通过直接下载的明确授权，已通知用户。
- 新采图版的HDMI调试预览为160×90抽样后放大8倍，因此预览较粗是设计行为；UART导出的真实原图仍是完整1280×720 RGB565_LE、921600像素、1843200字节payload。不得把放大预览当原图清晰度，或把UART耗时当相机帧率。
- 19:49交接截面：root正在建立 `binding-a` 接收绑定（CPU任务session7374），**尚未打开UART、尚未取得实际raw帧**。本轮没有Git提交或远端推送；下载成功不替代首帧CRC、实际图像或几何验收。

下一步在真实绑定完成后，从COM7只读采集第一张普通场景完整帧，核对尺寸、1843200字节payload及CRC；随后再与用户进行当前镜头VGA/720p同姿态几何验证，必要时补独立棋盘图。保留先720p有效清晰度与镜头矫正、后帧率优化的顺序。若用户随后断电或要求停止，以新反馈为准。

以下章节保留各时间点的历史状态与证据，不覆盖本节。

## 用户要求与板上状态

用户离开约一小时，开发板会一直上电且连接正常，已授权检查通过后直接下载，不重复问上电。当前板上仍是已确认画面正常的 camera720_transport_top，1280×720单位映射，尚未加入720p镜头矫正。新采图候选仍在离线阶段，不安排棋盘摆拍。

任务顺序：720p完整原图 → 核验VGA/720p裁剪缩放关系与当前镜头参数 → 必要的独立光学验证 → 720p矫正 → 帧率优化。不能把旧VGA约24fps、HDMI刷新率或UART导图速度写成720p实测帧率。

## 独立采图候选

- raw_camera_capture_cam2_current720 继承VGA采图的DDR、PGFRAME1、注册上电复位和8位1500ps输入延迟；传感器使用当前720p403动作、两完整好帧门禁，8秒稳定后允许新事务。
- 全1280×720 RGB565_LE：921600像素、1843200字节、57600个256位DDR数据拍；授权丢失阻止新事务，已开始事务继续排空。
- 调试预览采样160×90、放大8倍到720p输出；UART原图不缩小。调试预览较粗不表示原图分辨率下降，也不替代最终清晰度验证。
- UART921600/8N1只读导出，一张完整帧理论约20秒，默认90秒采集窗口；这是调试传输耗时。自动重复发送，关闭串口不停止FPGA采集。没有旧脚本收尾烧写heartbeat的操作。
- 源清单101项、显式设计21项，DDR IDF子文件不重复加入；128引脚核对通过。新候选不能继承旧ADF时序、布线/复位修复或硬件验收。

## 离线检查

work/camera720-raw-sim/attempt-a/camera720-raw-simulation.json 实际4项通过、231.168秒、源码无漂移：

1. 全921600像素独立参考比较、完整PGFRAME1头/尾/CRC、57600读写拍、DDR停顿、UART反压及末停止位所有权。
2. 授权前阻断、授权丢失时已有事务排空并阻止后续事务。
3. 预览三次有效发布与bank复用，坏末行拒绝，8557834个实际扫描RGB样本逐项一致，最大bank地址14399。
4. 真实403动作SCCB/frontend验证两好帧、坏行拒绝、时钟停止粘滞故障；数字模拟不等于实际电气时序。

新主机接收器 camera720_capture.py 与既有native capture合并51项测试通过。新候选真实位流及下载回执核验之前拒绝建立live绑定，不能以transport或旧VGA回执冒充720原图。新raw位流/下载provider待本候选物理检查后实现。

准备器补齐自有进程清理helper哈希依赖后，9测试+4子测试通过。独立PDS build-a已结束，实际结果见下文；没有生成位流或访问硬件。工具exit0不等于时序通过。

## 几何转移与下一步

见[几何转移交接](CAMERA_720P_GEOMETRY_TRANSFER_20261101.md)。真实VGA参数保持冻结；仅在固定裁剪缩放成立时候选K720=A×KVGA、D不变。当前没有真实720配对照片，不把纯数学示例当标定。新工具33测试通过，明确棋盘对称可掩盖镜像、held-out不重拟合、重复几何拒绝及有限数/完整JSON写入。光学/硬件验收标志保持false。

下一步从本候选实际时序、资源、网表重新核验CDC、复位、输入延迟和IO，通过后准备独立采图位流。用户不在时可以先采普通场景检查完整帧，棋盘配对另待返回。相机固定在FPGA上、右下被硬件遮挡，不要求移动相机，也不把遮挡区作为已验收光学区域。

## 证据与边界

- 实际原生构建计划：distortion/work/camera720-raw/build-a/plan.json，最大1800秒。
- 源冻结：distortion/work/camera720-raw-source-freeze-a.json；审查：distortion/work/camera720-raw-source-review-note.md。其中准备器旧SHA属于补helper绑定前历史，以build-a实际计划为准。
- 主机程序未打开UART；新raw位流未生成/未下载；板上transport成功下载及用户确认仍有效。
- GitHub CI按用户要求暂缓；本轮新文件与交接尚未提交/推送。


## build-a 实际结果（17:22北京时间）

原生流程完整结束：414.995秒、exit0、源码无漂移、STA前后ADF一致。严格执行器仍记失败：60条C:Sdm-3003计数器缩位提示（15项在4日志重复），未删除或改成成功；正逐项审查，仅计划显式只读导出用于排查。没有E/F、没有新raw位流或下载。

实际最终ADF SHA256 799296ded7e2fd66969d4cfdf25a9a30e316c2d8ac9c520b659cb83576f8fed7。双角setup通过（slow +0.659ns，fast +3.466ns）；hold失败slow1/fast2，最差-0.276/-0.274ns；recovery失败245/231，最差-4.577/-3.376ns；removal及mpw通过。Hold两个不同逻辑端点分别为cam_href→预览接收pixel_valid、DDR group2 ck_dqs_diff→dq_loop1 TX_DATA[3]。待精确setup余量、网表/路由与复位作用范围核验。

CPU最后定向回归：raw source+capture+geometry共68通过；另构建准备器9+4subtests通过。性能计划已单独整理，见 [720p帧率计划](CAMERA_720P_PERFORMANCE_PLAN_20261101.md)，不会抢在实际矫正前修改帧率。

## 新候选原生诊断（实际完成，覆盖上方待查状态）

四个隔离PDS上下文已经结束：`export-a` 导出网表并重跑STA（96.602秒）、`discovery-a` 路由/对象发现（57.082秒）、`hold-exact-a` 逐个DDR packed Q精确时序（81.072秒）、`reset-query-a` 五组复位精确查询（43.088秒）。均无C/E/F、输入漂移或源ADF变化；没有访问UART/JTAG。

- 60条C:Sdm-3003为15项在4日志重复。独立审查验证13项公开RTL计数器边界；2项加密DDR内部计数器只有同配置来源及历史诊断一致性，未声称内部边界已证明。原始失败回执保留，只读排查授权不等于清除诊断。
- 最终布局资源8434 LUT、7590 FF、1 APM、28 DRM、128 IO、BKCL 6/6，仅属于本raw候选。
- `hold-b/hold-analysis.json` SHA256 `23ab0e0873e22e73f1e68a6679476738a7bd66416e5954372e890832f28bbdb8`：两个失败支路12份原文、逐Q双角setup/hold齐全。HREF精确setup slow/fast +14.277/+14.910ns；DDR L6Q +4.288/+5.467ns、L5Q +4.269/+5.450ns。DDR原有multicycle setup约束保留，不新增数据时序豁免。
- `route-candidates-b.json` SHA256 `635a0a237b69d39e7c4909bafceda3f8894335595e14fc206c0f295a2f32fbb1`：完整扫描17763条路线、297536节点。仅选择HREF `_N46` 末端分支及DDR `_N174` 单分支空闲NE绕线候选；HREF另外3条分支必须保持。该记录不证明可达性或时序已修复。
- `reset-proof-a/result.json` 实际网表与原生对象查询一致，入口为注册粘滞上电复位及两级同步，127组来源/端点关系已定位。`reset-vendor-bytes-a.json`重新验证75项DDR文件与原厂参考逐字节一致。未导入全局异步时钟组，未宣称加密内部复位语义已证明，未应用复位例外。
- `interface-inventory-a.json` SHA256 `4f0a9aa176ee29a1b1593c7886bf376c84da3abecb9ccdcb34b74692a92a506e`：128引脚一致，8×1500ps DVP延迟无旁路、连接32接收端；64条monitor Gray链、4条标量链、37个held snapshot位已枚举。Gray同BLE为0/64、同site为5/64，不据此判断时序通过或失败。37条ignored async_reg提示按4份重复日志保留。
- `discovery-a` 宽泛get_pins达到1000项截断，不能证明完整CDC覆盖。9类待查项保留，尤其Gray/held数据物理约束、复位与bank ownership；原transport通过不能继承。

第一轮绕线已经在原ADF副本执行完成（`physical-route-a`，67.368秒，无C/E/F/漂移），新ADF为 `afa6d6826bd5f5616044d3c0af546d2f5004731533934e4e86f399230f540b05`。fresh `physical-report-a` 确认DDR支路hold通过，fast最差+0.020ns；HREF仍slow -0.027ns、fast -0.088ns。全部setup通过，recovery仍245/231失败，removal/MPW及检查总数保持；这不是时序闭合。

`physical-export-a`新进程导出与原导出对比：19395个primitive的参数/端口、7590个FF位置及模块声明完全一致。初次严格路线比较仍失败：非route token哈希不同。独立逐引用调查 `route-cdb-reference-resolved-a.json`（SHA256 `357380f33059e24d337ea7f484dfe6e63f26f3c0532700e57c611f8f670f3156`）确认52个CDB定义和11357字节完整块不变；37个CDBENTRY在20个父对象下内容、解析后的引用相同，14个父对象仅条目排序改变，**不是ID重新编号**。8519对普通FILEID/LINENUM源注释被删除，37对约束来源保留，FILETABLE仅删除空路径记录；除已逐对象核对条目外其余非route token相同。

全17763条路线中仅两个目标变化，HREF另外3支逐节点保持；没有未解释的功能/放置token变化。原严格比较器未修改、原失败未抹除，独立语义诊断不等于硬件放行。第二轮从原ADF独立副本执行更远HREF绕线，保留DDR同一waypoint；新结果仍须自身fresh STA及全路线检查。

本轮定向CPU回归130测试和30子测试通过（`distortion/work/camera720-raw-final-pytest-a.xml`）。冻结边界复核：101项源码、115项构建输入和102项编译副本无漂移，当前transport位流/下载回执及VGA标定profile未变。新候选时序与CDC尚未完成，没有raw位流或新下载。

## 第二轮绕线：setup/hold已通过

`physical-route-b`从原ADF独立复制，实际68.482秒完成，无C/E/F或输入漂移。HREF新线对为`ZDNE[0]:SRB_12_138 → IDNE[0]:SRB_18_144`，DDR保持第一轮线对。结果ADF SHA256 `e43f5707209271cd35a534978315302092b2ad18ca4ecd41b6f0aed06b4847a3`；执行回执SHA256 `f201ed6abaccb90c80b65fbf197e7ef8507b118944fd4496191701d285f2c957`。

独立`physical-report-b`通过，`route-timing-comparison-b.json`（SHA256 `d0c436b2841f9116e7deb7e50a705815792daf01361ad43ba77081e4c1eab0ef`）核验全部10张表及逐时钟对：

| 检查 | slow最差(ns) | fast最差(ns) | 失败数slow/fast |
| --- | ---: | ---: | ---: |
| setup | +0.659 | +3.466 | 0 / 0 |
| hold | +0.064 | +0.020 | 0 / 0 |
| recovery | -4.577 | -3.376 | 245 / 231 |
| removal | +0.342 | +0.073 | 0 / 0 |
| mpw | +0.035 | +0.035 | 0 / 0 |

相机时钟对hold +0.152/+0.021ns，DDR目标时钟对 +0.291/+0.020ns。所有检查总数/时钟对身份保持，setup及recovery/removal/mpw逐对保持。`route-serialization-diagnostic-b.json`（SHA256 `114bfe0498abb4885d2fbf8c5abd805254f85f4401eb966248b7a79041aebd06`）重新验证17763路线：仅2目标变化，无非目标路线变化，CDB字节、各父对象解析引用及其他token一致。原strict comparator仍记录条目排序/源注释差异，不能声称原比较通过；诊断明确保留差异。

`physical-export-b`独立进程实际95.918秒完成，无C/E/F/漂移，ADF未改变。`route-functional-comparison-b.json`（SHA256 `3a7c84923194e28bb25833395deec83db690144d5aedd9888b081f2578c838ee`）重新比较全19395单元参数/端口、7590个FF位置和完整模块声明，全部完全一致；404项输入绑定。新导出自身STA也确认setup/hold双角零失败，recovery仍245/231；复位和CDC未完成，整体时序/硬件放行标志保持false。本阶段PDS进程已正常结束。

### 下一轮从这里继续

1. 完成本候选复位约束依据和精确范围验证；当前127关系已定位，未应用任何复位豁免，不用全局异步时钟组盖住recovery。
2. 对当前候选重新做完整CDC物理时序，尤其64位Gray、held snapshot、预览bank ownership/复位epoch；不能继承transport验收。
3. 核验当前候选DVP、输出/串口接口及编译诊断处置，生成独立raw位流与下载/捕获provider后才允许接收器live绑定。
4. 检查齐全后按现有授权直接SRAM下载，不重复询问上电；先取得真实720p普通场景完整帧，再等用户在场做VGA/720p同姿态几何验证和必要的光学补拍。
5. 720p实际镜头矫正完成后，依性能计划测采集/处理/显示等待，再优化帧率。不要把理论sensor15fps、旧VGA约24fps或HDMI30Hz当720p实测帧率。

本阶段没有UART/JTAG操作、没有新位流下载、没有git提交/推送；板上仍为已验收720p单位映射。用户持续上电且已授权检查通过后直接下载；若其随后断电或要求停止，以新反馈为准。

## 18:32 接续：复位应用和最终检查正在执行

- 当前用户要求继续，已确认持续上电且连接正常；仍使用本会话下载授权，不再次询问上电。未进入棋盘摆拍。
- 新复位范围 `reset-current-c/plan.json` 绑定当前 b 导出，127 个精确关系为入口 1、CPD 1、DQS 104、IOL 14、training 7。`reset-query-b/result.json` 原生查询通过，SHA256 `357ea06061a3ef8622a8f7ae98f728ba15aa4f020355e5fe76b06382d45f2df5`。原厂同配置文件、复位时钟与训练工作顺序已核对；加密内部逻辑不宣称独立形式证明。
- `reset-apply-a/stage-plan.json` SHA256 `7286fcd2ed2ffc41a877616635a641aab35101ee26495f8925b739fedd7e7425` 已启动执行，仅五组精确复位例外；必须等自身新报告、网表和全路线验效后才能判定通过。此时不把准备完成写成时序已通过。
- 新的 `camera720_raw_bitstream.py`、`camera720_raw_program.py` provider 已实现：实际复位、CDC/IO、诊断处置完整重核后封存全部输入；位流生成前再次实际 STA 和 C/E/F 日志检查，下载仅易失 SRAM、1 MHz JTAG，须有真实 scan、DONE 和清理回执。当前尚未生成 raw 位流、尚未调用硬件。
- 本轮定向回归 `work/camera720-raw-closure-regression-b.xml` 为 80 测试、15 子测试通过；包含 release/capture、复位、原厂依据及诊断验证。此前误用不存在测试名的 a 记录保留，不作为通过证据。
- `diagnostic-disposition-b.json` SHA256 `930b94f554b342983173acf49f5257dd2355d089648deba9925786993583536e` 仅支持在其余检查通过后的诊断采图。原 build-a 的 60 条 C:Sdm3003、`ExecutionCompletedWithoutError=false` 和 `BuildDiagnosticsCleared=false` 保留；不宣称内部计数器独立证明、综合形式等价或生产发布通过。
- `cdc-pilot-b` 因每次路径查询均重载模型，300 秒截止仍未完成；执行结果为 false，不得纳入通过证据。沙箱内进程树清理被拒绝后，已再次精确核验 PID 9508 的本任务 stage 命令并用提升权限终止该任务树；未终止其他工程。后续缩小批次，并显式限定 packed FF 的 Q，逐实际路径身份核对完整覆盖。

下一步依次完成最终复位报告/导出验效、当前候选 CDC 与 IO、raw 位流、SRAM 下载、COM7 只读接收完整 1280×720 原图。首张可以是普通场景，不能把 CRC 通过当光学标定通过。完成后再做当前镜头 VGA→720p 几何验证，保留“先清晰度与矫正，再帧率”的顺序。

## 18:54 最终复位验效通过，CDC 实测开始

`reset-report-a` 实际55.842秒成功，回执 SHA256 `aba98274f892eccc36a16bdd142df05dd3c0d7da2622641b0cacd2d453405958`；`reset-export-a`实际95.694秒成功，ADF未改变，无C/E/F或输入漂移。最终候选仍为 `e659b81fd687c7f8083f3980ea05a955976a9cde5f8a2350687a9231c2ba1dea`。

| 检查 | slow最差(ns) | fast最差(ns) | 失败数slow/fast |
| --- | ---: | ---: | ---: |
| setup | +0.659 | +3.466 | 0 / 0 |
| hold | +0.064 | +0.020 | 0 / 0 |
| recovery | +3.378 | +5.449 | 0 / 0 |
| removal | +0.342 | +0.073 | 0 / 0 |
| mpw | +0.035 | +0.035 | 0 / 0 |

`reset-effect-a.json` SHA256 `1f6339bd0e2fec2fd4d91157c4297e66fc11275bbea4d1db3444532691042504` 实际重算通过，588项输入无漂移。19395单元、7590FF、模块声明完全一致；17763条路线全部不变；每角精确245项复位检查例外与实际127来源/端点关系相符，setup/hold数据false-path为0，其余例外不变。此结论只表示内部复位验效，不代表整体硬件/光学验收。

为避免每次检查重复解析大型报告，新独立 `camera720_raw_reset_fast_inspect.py` 一次完整重核原应用后生成显式SHA的 `reset-source-authority-a.json`（`a4d879035c6df3334bde5a399f70d879ea803393a8912117fc9b51766aba6a3c`）。后续仍重核555项输入、67项工具、实际源日志/对象和全部产物；新报告/导出/查询仍为真实PDS、每次300秒上限。旧检查器及原失败记录均保留。实际计划明确传入SHA；公开API未使用的None参数加固项后续独立处理，不修改本轮冻结工具。

最终 `cdc-final-query-a/query-plan.json` 重算1127个精确物理身份、2390个角点/检查类别case，原完整报告已覆盖593，其余1797待测，当前0违规。查询缩为19命令，分8/8/3三个受限批次，另有128个实际IO站点和3条DVP/TX报告；首批 `cdc-final-native-00` 已执行。未把超时pilot结果纳入通过证据。

原图资格信号是同27MHz域的组合逻辑，经目的域两级同步和8秒连续采样等待；不宣称源信号无毛刺或资格下降立即撤销。短暂低采样会重新等待，已接受事务独立完成；完整帧尺寸、奇字节、首尾beat、source/writer CRC与host CRC另行检查。预览RAM独立，不作为原图payload。

## 19:20 最终 IO/CDC 完整通过

- `cdc-final-proof-a.json` SHA256 `bd70dff41d84759c1cff2ba5d3cf34314de452227486cf345683f03a101f599a`：1127精确物理路径身份、2390角点/类别case全部覆盖，Missing=[]、Violations=[]，822依赖无漂移。新producer冻结SHA `0f14df050c32c2471c1b495038b849e1c7d18ac96de3471770937dbe6a81dfd7`；43项定向测试通过。
- 当前实际最终ADF的128引脚/站点/声明电气配置一致，14 CAM2和71 DDR核对通过，DVP40项和TX56组最大延迟齐全。TX无Slack组合报告使用独立分块解析，补了回归；没有重跑已通过native，也没有将其当外部AC签核。
- 84位Gray中最大延迟0.848ns（对应源周期8ns）；monitor held最大3.370ns<74.074074ns，raw metadata 1.268ns<16ns，preview bank 0.849ns<26.936027ns，slow/fast双角覆盖完整。原生packed CLK别名严格按Q区分；三批主查询不足的538case由16条single-source多endpoint查询实际补齐，不作缺项豁免。
- 原始IO observation a生成后CPU producer曾更新，其闭包漂移，因此保留a但不用于授权。新的 `cdc-final-io-observation-b.json` SHA256 `a0fcaf4b45d22586e7b7c1f1d210ad8920d5484afd1103c195af7f6ce5b634f2` 重新绑定610依赖全部通过。
- `connection-review-a.json` SHA256 `4f29f0501eabfb6d74ecdc1475f00bcec1498696f5c47cd211f31eb2dcacd673` 已经接收器声明校验通过，依据当前实际IO、同CAM2/镜头、用户持续连接及已验收transport；明确不是实测电压或外部AC，不继承旧VGA的模式/标定/下载状态。
- `bit-request-a.json` SHA256 `0d03b98134ad6db90ca980244c4c82abf0664b26c81cb3733005caa56812888b` 已写入，当前执行首次完整authority重算，之后每次全部依赖哈希检查并实际fresh STA→runtime gate→bit生成。此时尚无raw位流/下载，板上仍为720p单位映射。

## 19:34 严格复核路径差异已定位，使用 proof-b

首次 bit authority 未生成：`camera720_raw_cdc.verify` 在完整重算后的严格JSON比较拒绝了 proof-a。独立保留冻结producer，通过异常栈局部值获得真实 actual/saved 并逐字段比较，差异恰为3136个Report路径字符串：InitialRecords593、Records2391、DVP40、TX112。首次CLI传入相对receipt导致保存Report为相对路径，verify从已保存绝对receipt重新计算得到绝对路径；所有对应文件resolve及SHA完全相同。无数值/顺序/类别差异，822依赖完全一致且无漂移。

`cdc-final-proof-b.json` SHA256 `ba9e5022f55375a61f36cb0ae59c65671329fbb4f383f3bbee5a59de495318ff` 为本次真实audit_value结果的逐字节副本，未手工修改proof-a或放宽比较。来源记录 `cdc-final-proof-b-provenance.json` SHA256 `5426d2738301eb65ef52b0b1a51a6abf09bef5e1b61867d0a96ddc8720ee71f6`；原因见 `cdc-recompute-path-diagnosis-a.md`。工具、RTL、native证据均未变。后续所有receipt、plan、work参数必须使用规范绝对路径。

新 `bit-request-b.json` SHA256 `edb1e7f3672200e89cd1605cde615929fd3ea164009292fe541dd1df0b68124a` 只改为引用proof-b，正在按原严格规则完整生成authority-b；在成功之前不执行位流或下载。
