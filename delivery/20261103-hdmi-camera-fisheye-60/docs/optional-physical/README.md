# DDR CA 控制网扇出诊断备选

此目录的 `ddr-ca-maxfan16.fdc` 需要手动加入候选构建。默认构建不会加载它。先观察 physical-b 新 RTL 的完整布局布线；若同一 DDR CA 控制路径仍失败，再单独启用本实验并比较结果。

## 精确目标与源码保持

约束为：

```tcl
define_attribute {n:u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/all_group_ca_dly} {syn_maxfan} {16}
```

`n:` 指定 net。目标是 `distortion/platform/video_base/ipcore/ddr3_test/rtl/ddrphy/ddr3_test_slice_top_v1_10.v` 第 285 行声明、第 385 行赋值的组合线网。该线网等于四个 `this_group_ca_dly` 状态的 OR。

真实 physical-a 综合网表确认上述完整层次仍存在；驱动单元为 `N61_4`，LUT4 的真值为 `16'hFFFE`，四个输入分别为 `debug_data[66]`、`[135]`、`[204]`、`[273]`。确认文件为：

```text
D:/f60-run/physical-a/prj_tasks/syn_1/synthesize/hdmi_camera_fisheye_top_syn.netlist
D:/f60-run/physical-a/prj_tasks/syn_1/synthesize/hdmi_camera_fisheye_top_syn.vm
```

此 FDC 对组合驱动器提出复制要求，保持原 IP 源文件、寄存级数、训练时序及厂商多周期约束。实际构建加入后必须重新综合，再执行 map、place、route、route optimize 和完整时序检查。

## 厂商文档和本机核验

文档位于本机安装目录 `E:/PDS_2025.2-ads-win64/pango/PDS_2025.2-ads/doc/`：

- `UG990102_ADS_Synthesis_User_Guide.pdf`，8.1.1，PDF 第 63–64 页（印刷 61–62）：FDC 属性在综合阶段生效，`{n:net}` 为 net 对象语法。
- 同手册 8.2.14，PDF 第 113–116 页（印刷 111–114）：`syn_maxfan` 与 `PAP_MAX_FANOUT` 等价，适用于 net 等对象，可复制组合逻辑驱动器；手册中的组合 `wire en=a&b` 例子展示复制 LUT 后降低扇出。该属性不适用于时钟及异步复位/置位网。
- `UG990002_Pango_Design_Suite_User_Guide.pdf`，PDF 第 140–145 页（印刷 138–143）：多种子布局、细化迭代和 Design Cells Duplication 的含义。
- 本机 `pds_shell.exe` 2025.2 build 211867 的 `place -help`、`pnr -help` 确认相关选项存在。当前 `-dc_duplication` 接受字符串，取值使用 `Global`；旧版 Tcl 手册的布尔参数写法不用于此版本。

`define_attribute` 在 FDC / Design Workspace 语境中解析，不能直接在未打开 Design Workspace 的顶层 shell 中执行。本方案使用已验证的 FDC 属性写法；未采用 `set_max_fanout`。

## 最小层次绑定验证

`probe/` 保存同层次、同 OR4 组合结构的 64 负载小工程证据，使用本目录同一份 FDC：

| 项目 | 无额外 FDC | 加入 maxfan16 FDC |
| --- | ---: | ---: |
| OR4 LUT 数 | 1 | 4 |
| 每个 OR4 输出负载 | 64 | 16、16、16、16 |
| 数据寄存器数 | 64 | 64 |
| 新增流水级 | 0 | 0 |

两次综合均成功。复制后的四条 net 均带 `PAP_MAX_FANOUT=16`，四个 LUT 真值相同。该验证证明层次对象绑定和组合复制机制；实际 DDR 工程的复制效果、资源和物理裕量需要完整构建确认。小工程仅运行 compile / synthesize，未施加 I/O 时序约束，日志中的未约束端口提示属于此验证范围。

## 保留源码的尝试顺序

physical-a 报告的实际选项为：`Design Cells Duplication=Global`、`Mode=normal`、种子 0 / 一次、`RefinePlacement Iteration=30`、`Placement Decongestion Mode=1`、`Placement Initial Method=Quad`。自动逻辑复制已经开启。

1. 先检查 physical-b，保持默认选项、全部厂商物理及多周期约束。
2. 如仅剩此类布线主导的小负裕量，可用本机支持的 `-gplace_seed`、`-gplace_times`、`-seed_step` 做少量固定种子对照，保存各次完整 setup / hold 报告；也可独立比较 `-refineplacement_iteration 60`。保留现有 route / hold 修复选项。
3. 若相同 OR 网持续高扇出，手动加入本 FDC，重新综合，检查目标网复制、每条复制网的负载及真实落点，再对照完整时序。

验收时同时检查芯片内各时钟域、PHY 相关路径和 hold；记录源文件、FDC、选项与结果的绑定。此备选未修改 IP、训练协议或时序要求，也未用于声明当前候选已收敛。
