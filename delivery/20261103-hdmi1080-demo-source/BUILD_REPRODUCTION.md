# 源码校验与构建准备

本包首先提供**准确的已演示源码子集与精确依赖清单**。它不承诺一条命令生成最终同字节位流；完整原生依赖、合法工具环境、独立最终时序/IO 检查仍是后续构建前提。

Python 3.10+，标准库即可。进入本目录：

```powershell
python -X utf8 -B tools/verify_package.py
```

预期 `included_sources_verified=50`、`external_dependencies_required=80`。该命令拒绝缺文件、长度/哈希改变、未列源码及误放入待上传子集的外部依赖。

由获准来源取得完整原生 `native` 目录后：

```powershell
python -X utf8 -B tools/prepare_build.py --dependency-native C:/path/to/authorized/native --run-name check-01
```

脚本先核全部 130 项，然后生成 `_build/check-01/native/`、`map.tcl` 与 `preparation.json`。原版源码不改；仅在派生编译副本中将**有闭包绑定的绝对 include** 指向本次副本，记录原字节与编译副本哈希、每次路径替换。采用字节级替换以保留原厂文件的历史编码。IDF 及其生成子源保持原字节。未知绝对 include、未绑定相对 include、输入漂移或已有 run 目录均拒绝。

`map.tcl` 保留冻结 Map 流的 49 项 `add_design` 顺序、1 项源 FDC、相同 top/器件、`compile`、`synthesize -ads -selected_syn_tool_opt 2`、`dev_map`。本准备工具不会运行该脚本，**不含 PNR、STA、bitgen、JTAG、串口或 Flash 操作**。重做 Map 后仍需重新绑定该 Map 的 PCF、补充 UART 引脚位置、完成 PNR 和双角最终数据库 STA，并重新审计 CDC/外部 IO；旧 ADF 的成功或失败结论均不能替代新构建。

本次离板交付已执行：50 项源码校验 PASS；从只读冻结闭包绑定 80 项依赖、生成 130 项编译副本与 6 项 include 替换 PASS。原始版本/冻结版本未修改。最初编译副本准备因厂商源并非 UTF-8 失败，已改为只重写 ASCII include 的字节级实现；失败目录本地保留并被 `_build/` 排除。

`tests/` 另保留 3 秒模式控制器的历史短 bench、对应候选与参考模块；它只覆盖控制与 bank 模式保持，不代表全 DDR/像素、1080p60 或物理验收。本次未安装模拟器、未重新执行该 RTL 测试，也未重新运行 EDA。冻结版本既有数字/物理证据口径见 `evidence/`。
