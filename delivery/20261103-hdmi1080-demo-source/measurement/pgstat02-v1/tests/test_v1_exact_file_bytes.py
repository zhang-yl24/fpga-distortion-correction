from pathlib import Path
import copy
import json
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'host'))
from measurement_report import analyze_run
import test_live_metadata_binding as live_cases


class ExactFileByteTests(unittest.TestCase):
    def test_live_API_requires_exact_bytes_not_only_equivalent_dictionaries(self):
        data=list(live_cases.LiveMetadataBindingTests().fixture())
        with self.assertRaisesRegex(ValueError,'actual manifest/plan/attestation'):
            analyze_run(*data[:5])
        changed=copy.deepcopy(data)
        changed[5]['manifest'] += b'\n'
        # Same parsed object, different file bytes: redumping JSON must not pass.
        self.assertEqual(json.loads(changed[5]['manifest']),changed[1])
        with self.assertRaisesRegex(ValueError,'input-file SHA mismatch'):
            analyze_run(*changed[:5],input_file_bytes=changed[5])
        changed=copy.deepcopy(data)
        changed[1]['input_binding']='Different parsed metadata supplied alongside old bytes'
        with self.assertRaisesRegex(ValueError,'file bytes differ from parsed'):
            analyze_run(*changed[:5],input_file_bytes=changed[5])

    def test_report_CLI_binds_actual_input_file_bytes_and_rejects_whitespace_edit(self):
        raw,manifest,plan,attestation,meta,inputs=live_cases.LiveMetadataBindingTests().fixture()
        work=ROOT/'work/OFFLINE_FAKE_LIVE_CLI_TEST';work.mkdir(exist_ok=True)
        for key,contents in inputs.items():(work/(key+'.json')).write_bytes(contents)
        (work/'uart.raw.bin').write_bytes(raw)
        (work/'capturemeta.json').write_text(json.dumps(meta),encoding='utf-8')
        args=[sys.executable,str(ROOT/'host/measurement_report.py'),'--wire',str(work/'uart.raw.bin'),
              '--manifest',str(work/'manifest.json'),'--plan',str(work/'plan.json'),
              '--run-attestation',str(work/'run_attestation.json'),
              '--capture-meta',str(work/'capturemeta.json'),'--output',str(work/'OFFLINE_FAKE_LIVE_REPORT.json')]
        p=subprocess.run(args,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=10)
        (work/'CLI-positive.log').write_text(p.stdout,encoding='utf-8')
        self.assertEqual(p.returncode,0,p.stdout)
        result=json.loads((work/'OFFLINE_FAKE_LIVE_REPORT.json').read_text())
        self.assertTrue(result['integrity']['capture_input_file_binding']['verified'])
        # Real file edit, no raw/CRC/request/JSON-value change. Old capture hash
        # must reject it, rather than being recomputed from canonical JSON.
        (work/'manifest.json').write_bytes(inputs['manifest']+b'\n')
        p=subprocess.run(args,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=10)
        (work/'CLI-negative.log').write_text(p.stdout,encoding='utf-8')
        self.assertNotEqual(p.returncode,0)
        self.assertIn('manifest_sha256',p.stdout)
        (work/'SCOPE.json').write_text(json.dumps(dict(data='Synthetic fake transport; LIVE validation branch only',
             hardware='NOT_ACCESSED',COM_opened=False,real_UART_requests=0),indent=2)+'\n')


if __name__=='__main__':unittest.main()
