# 当前镜头 VGA 标定会话（2026-10-31）

本目录已经准备流程，尚未采集图像、生成 K/D、运行 PDS 或访问 UART/JTAG。当前正确显示的 upright 位流不是原图采集位流，不要据此填入已经下载 raw-capture 的声明。

用户确认接手后未换镜头，不知道队友此前是否更换。此次只标定现在接着的镜头，不继承任何旧档案。棋盘是 7×10 个方格，对应 6×9 内角点；每格 25 mm，来自用户实物说明。固定当前 640×480 RGB565、传感器裁剪/时钟、3820=00 / 3821=06 方向、焦距和对焦。先完成此模式下的实际畸变矫正，清晰度和帧率升级后置。

## 文件及真实状态

- session-plan.json：当前镜头身份标签、棋盘规格、12 个训练与 6 个独立留出姿态。标签仅表示本轮操作员声明的实体，不声称已经取得硬件唯一序列号。
- binding.template.json：等待新 raw-capture 位流的真实 build/bit/pin/timing 哈希及实际接线/下载审核，所有四个 review 当前均为 false。它有意不能进入 live 接收。
- dataset.draft.json：空数据集，domain 仍待审查，没有伪造路径、SHA、K 或 D；它有意不能送入拟合器。
- capture_one.py：默认只打印某一姿态的具体接收命令。只有显式 --execute 且现有 live binding 全部验证通过后，才调用既有 native_camera_capture.py，随后调用 check_calibration_view.py。
- assemble_dataset.py：从明确选择的单帧 quality.json 重核原始 RGB565、PNG、CRC、metadata 和角点，生成可供既有拟合器使用的真实 manifest；它不拟合、不访问硬件。
- captures/、profiles/、reports/：本轮独立输出目录；不覆盖任何旧帧或失败尝试。

## 开始采图之前

root 需先完成独立 upright raw-capture 候选的源/引脚/时序/位流检查，并按当前会话操作完成 SRAM 下载，再创建真实 binding.json。native_camera_capture.py 要求 validated_build 中的 SHA256、TimingSHA256、SourceSHA256 及 RawCaptureContract 都绑定实际文件；RawCaptureContract 必须是 PGFRAME1、native_raw、geometry_applied=false、image_size=[640,480]。最终时序报告本身必须包含 All Constraints Met。只改 review 为 true 或沿用旧显示位流都不能代替这些证据。

确认实际 UART 端口时不要把旧 COM7 当成当前端口。程序是 921600 baud、只读接收；它不向 UART 发送命令。capture_one.py 每次只接收一帧，最多等 90 秒，默认不执行。

## 单姿态流程

1. 按 session-plan.json 的该姿态摆棋盘，整块棋盘和全部内角点保持可见，棋盘必须平整、没有明显反光或运动模糊。
2. 新姿态摆好后先稳定至少 10 秒，再开始接收，之后一直保持到接收与角点检查完成。这使当前自动循环输出的旧冻结帧先流完；PGFRAME1 的接收时刻不是曝光时刻。
3. 检查 quality.json 和 corners-overlay.png：应检测到 54 个内角点。overlay 只供检查，绝不能作为标定输入。注意小于 8 px 的格间距、模糊或近边缘警告；必要时同一 pose 用新 attempt 编号重拍。
4. 下一张必须重新移动、倾斜或改变距离；不能把连续收到的相同姿态算成多张独立样本。held-* 不参与拟合，且不能重复训练图姿态。

在仓库根目录，先仅生成计划（把 ACTUAL_PORT 换成核实后的端口）：

    .venv/Scripts/python.exe -B -X utf8 distortion/work/camera-vga-calibration-20261031/capture_one.py --view train-01 --attempt 1 --port ACTUAL_PORT

新 raw 位流和真实 binding.json 均准备好后，才用同一命令加 --execute。失败文件留存；重试必须增加 --attempt，例如 2。输出自动放在 captures/train-01-a01/。每个成功帧都保留原始 RGB565、无损 PNG、原始 metadata、接收 summary、quality 和单独 overlay。

## 姿态安排

训练 train-01..12：中央中距离、中央近距离、左、右、上、下、左上、右上、左下、右下、中央左右倾斜、中央上下倾斜。每个姿态完整说明在 session-plan.json。

验证 held-01..06：使用全新的距离/倾角，分别覆盖中央、左、右、上、下及较大中央区域。现有工具最少要求 12 个不同训练姿态、3 个独立验证姿态；本次安排 6 个验证姿态增加边缘覆盖机会，不保证仅 18 帧就一定通过。若 3×3 分区覆盖不足或角点质量差，应补拍，不能降低覆盖标准。

工具的已存在覆盖标准：每个要求的图像 3×3 分区，训练角点至少 15 个、留出角点至少 3 个。留出图不参与 K/D 拟合或参数调优；若更换模型/视场后使用验证图指导选择，应重新补真正独立的验收图。

## 组装、拟合和 FPGA 映射

逐一审查单帧报告后，明确列出每个 pose 的最终选中 quality.json，传给 assemble_dataset.py 的 --checks；不要用覆盖所有 attempts 的通配符。--maximum-ray-angle-deg 必须由当前图像/目标视场审查后选择且小于 90，它是请求的工程模型域，不是实测镜头 FOV。当前镜头型号和真实 FOV 均未知，本目录不预填此数值。

    .venv/Scripts/python.exe -B -X utf8 distortion/work/camera-vga-calibration-20261031/assemble_dataset.py --checks <explicit selected quality files> --maximum-ray-angle-deg <reviewed domain> --output D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-calibration-20261031/dataset-selected-a.json

四系数 fisheye 是已有工具可运行的候选模型，不因旧记录写过“鱼眼”就自动认定适用于当前镜头；需要结合当前数据及留出结果检查。若选用这个模型，现有拟合命令为：

    .venv/Scripts/python.exe -B -X utf8 distortion/tools/calibrate_fisheye_profile.py distortion/work/camera-vga-calibration-20261031/dataset-selected-a.json --output distortion/work/camera-vga-calibration-20261031/profiles/fisheye-profile-a.json

拟合器检查原图绑定、重复图像/跨 split 姿态泄漏、完整棋盘、覆盖、前向模型域和误差；只有实际物理来源和各项条件同时通过才产生 candidate_ready_for_profile_review=true。之后先审查真实视场和黑边，再用现有 Brown 定点近似工具检查与 FPGA 算术的偏差：

    .venv/Scripts/python.exe -B -X utf8 distortion/tools/wideangle_mapping_audit.py distortion/work/camera-vga-calibration-20261031/profiles/fisheye-profile-a.json --output distortion/work/camera-vga-calibration-20261031/reports/brown-mapping-a.json --angles 0 --output-size 640 480 --stride 1 --maximum-error-px 0.25

若默认输出内参导致黑边过大或映射误差过高，应明确选择新的输出内参并用 --output-k，或选择更适合的模型；不能为了通过而静默放宽阈值。该审计通过也不等于上板放行，仍需独立 calibrated VGA 候选的定点/RTL、资源、完整时序和实屏直线/边缘/运动验收。

本轮没有真实标定图，也没有已接受的 K/D。新原图位流完成前，这些脚本和配置都只是离板准备。
