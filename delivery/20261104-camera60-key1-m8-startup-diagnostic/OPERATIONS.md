# 同学最短实板验证顺序

1. 核对位流完整SHA和同型号板卡/引脚，先准备自己持有并校验过的可用回退位流。
   使用真实1080p60摄像头，按已有加载、供电和温度监测流程；不写Flash。
2. 摄像头接好后共同reset。首次结果前输出同步可保持静止；先等待初始化与首图。
   记录实际摄像头模式，区分59.94与60。输入59.94不能产生60个不同输入帧。
3. 记录完整raw串口、位流SHA、温度、序号、ticket/nonce、计数与故障码。
   本版是PGSTAT02 84字节；不是旧PGIQ/96字节协议。
   host/u_pgstat02.py只解码已保存wire。make_arm/request只生成SGA1/SGT1字节，不发送。
   端口和波特率须沿用与本版匹配的已有流程，不猜COM号。
   同一时刻只用一个串口程序；测量窗口内不要并行写旋转/Gamma配置。
4. KEY1按下和释放各超过20ms，做CORR→RAW→CORR。正常请求默认CORR。
   last_mode=3表示校正和Gamma开关为1，RAW为0；它是最后处理帧模式，不是当前显示模式。
   留出在途旧帧排空时间，检查画面、撕裂、卡帧、fault与新呈现计数。
5. presented在完整reader/scanner像素数、CRC、ID/epoch及FIFO排空验证后，与新ID释放事件一起递增。
   用它的差值区分新帧与repeat，不能用输出刷新率冒充新校正帧率。
   last_id是最后处理ID，不是显示ID。captured不是全部输入SOF；drop0不证明输入零丢帧。
6. 发生失图/故障先保留raw，再共同reset或恢复预选回退。启动对齐仅共同reset时生效，
   尚未验证运行中拔插自动恢复，也未证明真实DDR的预取期限。
   -7ps时序未闭合，任何稳定性结果都必须绑定这份诊断位流，不能称全签核。

模型覆盖固定0角、GammaOFF和冷启动首帧GammaON曲线0。暖帧自适应Gamma及非零角1080p性能未测。
last_cycles仅内部处理时间；没有输入SOF→扫描或光学端到端延迟证据。
parser会保留故障字节和坏包/截断；它不会自动认证测量epoch或计算可信FPS。

离线检查：python -X utf8 -B -m unittest discover -s tests -p test_u_pgstat02.py
离线解码：python -X utf8 -B host/u_pgstat02.py --wire saved-wire.bin
