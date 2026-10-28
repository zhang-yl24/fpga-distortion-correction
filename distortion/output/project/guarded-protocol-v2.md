# Guarded V2 线协议与命令语义

精确offset、字段长度、枚举和合同以同目录`guarded-protocol-v2.json`及`tools/guarded_protocol.py`为共同机器来源；本文件不引入第二套字段布局。旧PGFRAME1与旧构建不修改。

命令固定16字节：`A5 5A`、version=2、opcode、seq LE16、session LE32、arg LE32、CRC16/CCITT-FALSE LE16。CRC初值FFFF、多项式1021、不反射、xorout0，覆盖字节2至13。OPEN=0F、GRANT=10、STOP=11、QUERY=12。

OPEN需要非零session、arg0、完全idle、无外部fault且没有待反馈GRANT；新session在此时建立新的序号基准。计数不因换session清零。session0无法GRANT/STOP/QUERY；QUERY也需先OPEN。跨boot/session不提供密码认证，不凭CRC证明主机或相机身份。

同session的16位seq按半范围前进：差值1..32767可接受，差0仅完全相同的last-seen `(opcode,seq,session,arg)`返回DUPLICATE且不再执行；同seq改字段返回SEQ_CONFLICT，差值32768..65535返回OLD_SEQ。**每个有效forward命令即使被业务拒绝，也消耗last_received_seq及last-seen tuple**。格式/版本/CRC错误和异session命令不推进当前session的序号基准。全部计数按32位自然回绕。

GRANT参数为`arg[7:0]=1..3帧`、`arg[31:8]=1..24000ms`；125MHz下乘125000得到最多3000000000周期。只有can_grant和grant_ready均成立才输出一拍grant_valid；随后command_busy保持，等待下游真实grant_accepted/grant_rejected。解析成功不等于授予成功：等待期间last_result=NONE、不增加accepted，不发accepted回复。下游拒绝优先于接受；1024周期无反馈则GRANT_TIMEOUT并发STOP脉冲。迟到反馈在无pending时忽略。

待GRANT反馈时，其他forward命令返回BUSY；有效STOP可抢占并撤销pending，该被撤销GRANT计一次reject，STOP自己计accepted。STOP和QUERY均要求arg0，均不能续租或增加预算。STOP只停止新admission，已经接受的DDR/UART事务由独立lease/core drain；command engine不复位在途事务。QUERY在无pending时回复状态且计accepted。

accepted计成功的OPEN/STOP/QUERY和得到真实下游接受的GRANT；rejected计有效包的业务/顺序拒绝；duplicate独立计相同last-seen重传；rx_error独立计CRC/版本/framing/收包间隔超时。last_accepted_seq仅随真正成功的命令变化。requested_frames/lease_ms记录最新forward GRANT请求；非法超宽lease在16位状态字段仅保留低16位，不能据此当作已接受的预算。

状态固定128字节：PGSTAT02、len=128、version=2、默认buildtag=52473201；0..119字节由CRC32-IEEE覆盖，120..123保存LE32 CRC，124..127为ST02。flags精确16位见JSON。snapshot_seq是状态包序号；completed_frames为boot全局累计，仅复位清零；admitted_frames是每grant计数。remaining_frames可在停止/过期后保留，armed及stop_reason决定是否仍可admit；不能以剩余数非零推断仍有授权。

状态与PGFRAME1只在完整包边界交替。有效PGFRAME1头声明的payload区域由该帧独占，即使像素包含PGSTAT02/PGFRAME1也不能扫描切开；完整payload验证失败后整帧丢弃。status CRC和frame CRC只说明数字完整性，不证明曝光时刻、物理身份、镜头标定、真实fps或密码认证。

纯Python`GuardedCommandModel`是数字oracle；实际安全由独立硬件lease/温度联锁/银行所有权执行。UART超时默认1250000 core周期，GRANT反馈超时默认1024周期。主机未再发GRANT不能续租；自动化不得把QUERY、重复包或解析成功当作新授权。

状态codec仅支持三个显式构建标签：CAM2自然场景`0x52473201`、CAM1自然场景`0x52473101`、CAM2传感器内部彩条`0x52473242`。`decode_status(data, expected_build_tag=...)`和`GuardedStreamParser(expected_build_tag=...)`必须选择与构建相同的单个标签，彼此默认拒绝；`encode_status(fields, build_tag=...)`用于对应的数字fixture。默认始终是CAM2自然场景；默认合同JSON、字段布局、CRC和RTL接口不变。不允许运行时修改全局BUILD_TAG。彩条是传感器内部数字输出诊断，不能作为自然场景或光学标定证据；CAM1/2仅表示连接器槽位，不代表物理左/右眼或同步。
