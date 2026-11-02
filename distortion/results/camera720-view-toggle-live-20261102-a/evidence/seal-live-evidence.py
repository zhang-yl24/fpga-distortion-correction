"""Copy original evidence bytes and verify every stored and decoded digest."""
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PROJECT = ROOT/'distortion'
OUT = PROJECT/'results/camera720-view-toggle-live-20261102-a'
SUMMARY = PROJECT/'results/camera720-view-toggle-live-20261102-a.json'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def reference(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    return {'Path': str(path), 'SHA256': digest(data), 'Bytes': len(data)}


def main():
    assert not OUT.exists() and not SUMMARY.exists(), 'fresh evidence package required'
    build = read(HERE/'build-a/plan.json')
    effect = read(HERE/'effect-a.json')
    program = read(HERE/'program-a/receipt.json')
    bitwork = Path(program['Bitstream']['Path']).parents[1]
    bit = read(bitwork/'verification.json')
    bitplan = read(bitwork/'bitstream-plan.json')
    requestpath = Path(bitplan['Request']['Path'])
    authoritypath = Path(bitplan['Authority']['Path'])
    cdcpath = Path(read(requestpath)['FinalCDCProof']['Path'])
    cdc = read(cdcpath)
    uart = read(HERE/'live-a/session.json')
    simroot = PROJECT/'work/camera720-view-toggle-sim/full-b'
    sim = read(simroot/'camera720-view-toggle-simulation.json')
    assert effect['AuditPassed'] and effect['AllInternalChecksMet']
    assert cdc['ScopedDigitalChecksPassed'] and cdc['Missing'] == cdc['Violations'] == []
    assert cdc['ObservedCases'] == cdc['ExpectedCases'] and cdc['Pins']['TopPortCount'] == 130
    assert bit['Verified'] and program['Passed'] and program['DoneConfirmed']
    assert program['FlashWritten'] is False and program['CleanupErrors'] == []
    assert reference(bit['Bitstream']['Path']) == {k:bit['Bitstream'][k] for k in ('Path','SHA256','Bytes')}
    assert program['Bitstream'] == bit['Bitstream']
    assert program['CandidateADFSHA256'] == bit['CandidateADFSHA256'] == effect['CandidateADFSHA256'] == cdc['CandidateADFSHA256']
    assert uart['ReceptionAndIdentityPassed'] and uart['IdentityMismatches'] == uart['RejectedPackets'] == 0
    assert uart['ExpectedBuildID'] == build['BuildID'] and uart['ExpectedProfileID'] == build['ProfileID']
    assert sim['Passed'] and sim['SimulationExecuted'] and sim['ActualScanPixelsCompared'] == 3686400
    tests = ET.parse(HERE/'final-cpu-tests.xml').getroot()
    checks = {'Passed':0, 'Failed':0}
    for suite in tests.iter('testsuite'):
        checks['Passed'] += int(suite.get('tests','0'))-int(suite.get('failures','0'))-int(suite.get('errors','0'))-int(suite.get('skipped','0'))
        checks['Failed'] += int(suite.get('failures','0'))+int(suite.get('errors','0'))
    assert checks['Passed'] and checks['Failed'] == 0
    OUT.mkdir(parents=True)
    rows = []
    stored = {}

    def store(path, name):
        path = Path(path).resolve()
        raw = path.read_bytes()
        compressed = len(raw) > 200000 or path.suffix in ('.sbit','.adf')
        data = gzip.compress(raw, compresslevel=9, mtime=0) if compressed else raw
        name += '.gz' if compressed else ''
        if name in stored:
            assert stored[name] == (str(path), digest(raw)), "conflicting package path"
            return
        stored[name] = (str(path), digest(raw))
        target = OUT/name
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(data)
        rows.append({'File':name,'SourcePath':str(path),'SourceBytes':len(raw),'SourceSHA256':digest(raw),
                     'Encoding':'gzip' if compressed else 'identity','Bytes':len(data),'SHA256':digest(data)})

    for folder in ('build-a','export-a','hold-query-a','route-a','hold-route-c','repaired-export-a','repaired-route-a',
                   'reset-save-a','final-export-a','final-route-a',bitwork.name,'program-a'):
        for name in ('plan.json','stage-plan.json','execution-result.json','result.json','receipt.json',
                     'bitstream-plan.json','pre-bit-audit.json','verification.json','stdout.log','stderr.log',
                     'execution-stdout.log','execution-stderr.log','stage.tcl','scan.tcl','program.tcl','bitstream.tcl'):
            p = HERE/folder/name
            if p.is_file(): store(p,'native/'+folder+'/'+name)
    for folder in [HERE/'cdc-final-query-io-a',*sorted(HERE.glob('cdc-shard-query-*-b'))]:
        for name in ('stage-plan.json','result.json','stdout.log','stderr.log','stage.tcl'):
            if (folder/name).is_file():store(folder/name,'native/'+folder.name+'/'+name)
    for p in HERE.glob('program-a/*.log'):store(p,'native/program-a/'+p.name)
    for name in ('effect-a.json','cdc-final-proof-b.json','build-diagnostics-disposition.json','route-plan-a.json',
                 'route-request-a.json','bit-request-b.json','bit-authority-b.json','release-cpu-tests-a.xml',
                 'cpu-checks.xml','final-cpu-tests.xml','reset-pipeline-driver-a.json','reset-effect-driver-b.json','final-cdc-driver-a.json',
                 'run-reset-pipeline-a.py','run-reset-effect-b.py','run-final-cdc-a.py','run-bit-authority-b.py',
                 'bit-authority-driver-b.json','run-cdc-shards-b.py','cdc-shard-driver-b.snapshot.py',
                 'cdc-shard-driver-b.json','cdc-batch-a-owned-cleanup.json','bit-authority-driver-b.snapshot.py',
                 'release-tool-freeze-a.json','seal-live-evidence.py'):
        if (HERE/name).is_file():store(HERE/name,'evidence/'+name)
    for p in (requestpath,authoritypath,cdcpath):store(p,'evidence/'+p.name)
    for pattern in ('run-bit-authority-*.py','bit-authority-driver-*.json','bit-authority-driver-*.snapshot.py'):
        for p in sorted(HERE.glob(pattern)):store(p,'evidence/'+p.name)
    store(HERE/'verify-live-package.py','verify_bundle.py')
    store(HERE/'reset-save-a/input.adf','candidate/'+build['Target']+'.adf')
    store(bit['Bitstream']['Path'],'candidate/'+build['Target']+'.sbit')
    for name in (build['Target']+'.rtr',build['Target']+'_exception.rtr'):
        store(HERE/'final-export-a/report_timing'/name,'timing/'+name)
    store(HERE/'final-export-a/generate_netlist'/(build['Target']+'_sim.v'),'candidate/'+build['Target']+'_sim.v')
    for folder in ('pre-program-live-a','live-a'):
        for p in sorted((HERE/folder).iterdir()):
            if p.is_file():store(p,'uart/'+folder+'/'+p.name)
    for name in ('camera720-view-toggle-simulation.json','summary.json','events.csv','simulation.log','config.vh'):
        store(simroot/name,'simulation/'+name)
    for p in sorted((PROJECT/'tools').glob('*camera720_view_toggle*.py')):store(p,'source/tools/'+p.name)
    for p in sorted((PROJECT/'tests').glob('*camera720_view_toggle*')):
        if p.is_file():store(p,'source/tests/'+p.name)
    for p in (PROJECT/'board/camera720-view-select.vh',PROJECT/'rtl/experimental/camera720_view_control.v',
              PROJECT/'tests/test_camera720_view_control.py',PROJECT/'tests/tb_camera720_view_control.sv'):
        store(p,'source/'+p.relative_to(PROJECT).as_posix())
    for p in (HERE/'build-a/compiled/board').iterdir():
        if p.is_file() and ('view' in p.name or 'lens' in p.name):store(p,'candidate/compiled/board/'+p.name)
    manifest = {'Schema':'camera720-view-toggle-evidence-manifest-v1','CreatedUTC':datetime.now(timezone.utc).isoformat(),
                'Files':rows,'Limits':'Original bytes with hashes; selected evidence snapshot, not a complete standalone PDS replay closure.'}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+chr(10),encoding='utf-8')
    summary = {'Schema':'camera720-view-toggle-live-summary-v1','Target':build['Target'],'BuildID':build['BuildID'],
        'ProfileID':build['ProfileID'],'Bitstream':bit['Bitstream'],'CandidateADFSHA256':bit['CandidateADFSHA256'],
        'Programming':{'Passed':program['Passed'],'DoneConfirmed':program['DoneConfirmed'],'FlashWritten':False,
                       'StartedUTC':program['StartedUTC'],'EndedUTC':program['EndedUTC'],'CleanupErrors':[]},
        'CPUChecks':checks,'SystemSimulation':{'Passed':True,'ActualPixelsCompared':sim['ActualScanPixelsCompared'],
            'Frames':3,'Summary':sim['Summary']},'InternalTiming':effect['CornerSummaries'],
        'DigitalCDC':{'Passed':True,'ExpectedCases':cdc['ExpectedCases'],'ObservedCases':cdc['ObservedCases'],'Pins':130},
        'UART':{'ReceptionAndIdentityPassed':True,'CompletePackets':uart['CompletePackets'],
                'ValidCounterWindows':uart['ValidCounterWindows'],'SelectedWindows':uart['SelectedWindows'],
                'IdentityMismatches':0,'RejectedPackets':0,'UARTTransmitBytes':uart['UARTTransmitBytes']},
        'VisualAcceptance':'Pending user KEY1 raw/corrected and stripe comparison',
        'ImageQualityParametersChanged':False,'FrameRateOptimizationPerformed':False,
        'EvidenceManifest':reference(OUT/'manifest.json'),
        'OmittedLargeLocalArtifacts':{name:reference(simroot/name) for name in ('scan-pixels.mem','expected.mem')},
        'Limits':['SRAM programming and UART digital evidence; user optical/stripe acceptance remains pending.',
                  'No Flash write, bitwise SRAM configuration readback or external AC/analog MTBF claim.',
                  'UART accepted/processed/unique-presented counters use nominal 125MHz, not HDMI refresh or all sensor frames.']}
    SUMMARY.write_text(json.dumps(summary,indent=2,ensure_ascii=False)+chr(10),encoding='utf-8')
    fps = uart['SelectedWindows']
    readme = f"""# 720p 原图／矫正切换实板证据（2026-11-02）

本包对应 `camera720_view_toggle_top`，BuildID `{build['BuildID']}`、ProfileID `{build['ProfileID']}`。

易失 SRAM 下载及独立 DONE 检查通过，Flash 未写，owned JTAG 进程清理通过。位流 SHA256 `{bit['Bitstream']['SHA256']}`，{bit['Bitstream']['Bytes']} 字节；最终 ADF SHA256 `{bit['CandidateADFSHA256']}`。

- KEY1（C23）每按一次切换原图／矫正，默认矫正。长按只切一次，松开后可再次切换。
- LED0 是请求模式：亮为矫正、灭为原图；显示在完整帧发布边界后生效。KEY0 保持复位。
- 相机、镜头参数、插值、曝光／增益及防频闪均未调整。提帧仍后置。

最新 CPU 回归 {checks['Passed']} 项通过。完整三帧系统仿真逐像素检查 3686400 个实际显示像素，3 唯一帧及 1 重复帧，零欠流／CRC 不符，最终排空通过。最终双角十表时序、精确复位验效、130 引脚及 {cdc['ObservedCases']}/{cdc['ExpectedCases']} 个物理查询 case 均通过；KEY1 同逻辑块的两级链由当前网表／器件原生时序模型单独归类，不虚构独立 FF 路径 slack。

COM7/115200 新版本身份通过，{uart['CompletePackets']} 包，{uart['ValidCounterWindows']} 有效窗口，身份不符／拒包均 0。选定窗口接受、处理、唯一输出分别 {fps['SourceAcceptedFPS']:.3f}/{fps['ProcessedFPS']:.3f}/{fps['UniquePresentedFPS']:.3f} fps（标称 125MHz）。这些计数不等于传感器全部帧或 HDMI 刷新率；没有新增光学／横纹定因验收。

用户实际按 KEY1 的切换观察与原图／矫正细横纹对照仍待反馈，DONE 和 UART 不能代替画质观察。

`manifest.json` 保存每份原始来源、存储及解压后字节数与 SHA256。大文件采用 gzip，原件未改写。包为选定证据快照，未包括完整厂商运行环境、所有 work 依赖和 3686400 行扫描像素；所省大文件在汇总中以原始哈希引用。复现仍需要本机绑定闭包。历史失败回执与被排除的超时批次保留在 work，未冒充通过结果。
"""
    (OUT/'README.md').write_text(readme,encoding='utf-8',newline=chr(10))

    for row in rows:
        data = (OUT/row['File']).read_bytes()
        assert len(data) == row['Bytes'] and digest(data) == row['SHA256']
        raw = gzip.decompress(data) if row['Encoding'] == 'gzip' else data
        assert len(raw) == row['SourceBytes'] and digest(raw) == row['SourceSHA256']
    assert read(SUMMARY)['EvidenceManifest'] == reference(OUT/'manifest.json')
    print(json.dumps({'Sealed':True,'Files':len(rows),'StoredBytes':sum(r['Bytes'] for r in rows),
                      'Summary':str(SUMMARY),'CPUChecks':checks},ensure_ascii=False))


if __name__ == '__main__':
    main()
