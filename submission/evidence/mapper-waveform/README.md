# KB4映射流水线真实RTL仿真波形

2026-11-04为报告重新运行已发布映射器单元测试，仅增加xsim波形观察。全部RTL、参数头文件和原testbench与发布提交`a6558c9`逐字一致；没有修改原RTL、原testbench、现有位流或旧仿真目录，也没有访问硬件。

## 测试配置与结果

- Vivado xsim 2017.4；核心时钟125 MHz，周期8 ns。
- 原testbench：`tb_hdmi_camera_fisheye_mapper_small`，内部实例`test_case`。
- 校正部分32×16，共512个坐标；另含4096个identity坐标和1024个边界/极值坐标。
- 总计5632个坐标、有效标记与标签全部匹配；844次反压保持检查、2次忙时配置拒绝；最长连续输入接受47次。
- 原testbench确认23个使能周期延迟和II=1。完整报告在`waveform-run.json`，源码SHA、原验证目录身份及所有执行命令均保留。
- 独立解析真实VCD，在每个时钟上升沿取边沿前信号核对握手、标签顺序和fixture坐标，再次全部通过，见`waveform-analysis.json`。

这是一组映射器单元波形，说明流水线时序与反压一致性；不代表整帧HDMI延迟、DDR时延、1080p系统帧率或实板物理时序。报告中的整帧仿真与位流板测仍按各自证据说明。

## 推荐报告窗口

### 首坐标输出时序 48–300 ns

- tag=0输入在76 ns上升沿满足`in_valid && in_ready`，被接受。
- `out_valid`在252 ns上升沿后置位。
- tag=0输出在260 ns上升沿满足`out_valid && out_ready`，被接受。
- 两次接受边沿相差184 ns，即23个8 ns周期。请不要把252 ns有效信号置位误当260 ns输出握手；这是同步仿真中边沿前采样与非阻塞赋值更新的区别。

推荐绘制`clk`、`in_valid`、`in_ready`、`in_tag`、`out_valid`、`out_ready`、`out_tag`，标出76 ns和260 ns。

### 反压保持 680–744 ns

- 704 ns：`out_ready`降为0，`in_ready`随之降为0。
- 708、716 ns两个上升沿不接受新输入，也不消费输出；`out_valid=1`，`out_tag=50`、`out_x=0x0013AF`、`out_y=0xFFFF40`保持。
- 720 ns：ready恢复。
- 724 ns：输入tag=72和输出tag=50被接受，随后输出推进到tag=51。

推荐绘制`clk`、`out_ready`、`in_ready`、`in_valid`、`out_valid`、`out_tag`、`out_x`、`out_y`，突出704–720 ns反压区间。坐标总线为有符号24位Q8；图中用十六进制可避免将负坐标显示成大正数。mapper边界输出并不等价于最终显示像素坐标合法性，采样边界由后续模块处理。

### 可选 忙时配置拒绝 988–1052 ns

1012、1020 ns上升沿`cfg_valid=1`而`cfg_ready=0`，忙时配置未被接受。此窗口可说明配置必须等流水线排空。

## 文件

- `mapper.vcd`：真实xsim输出，21个选择性信号，单位1 ps。
- `selected-transitions.json`：逐信号原始变化，`[time_ps,value]`；未知值为null。
- `edge-samples.csv`：上升沿前采样值及`in_accept/out_accept/output_stall`。
- `waveform-analysis.json`：独立不变量与精确窗口。
- `waveform.tcl`：open_vcd/log_vcd/run/close_vcd观察脚本。
- `simulation.log`：原testbench PASS日志。
- `run_waveform.py`：完整新目录执行与来源绑定；不得在已有完成目录直接重跑。
- `analyze_waveform.py`：只读VCD并输出派生分析。

波形SHA256：`962a29800b573ea272addef03aa4435f71177917655756f3f742be45fc439f9b`。
