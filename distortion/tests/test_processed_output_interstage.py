"""Actual targeted native reports must not pass after timing/inventory corruption."""
from pathlib import Path
import re
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import audit_processed_output_interstage as audit


@pytest.fixture(scope='module')
def native_report():
    root=Path(__file__).resolve().parents[1]/'build/processed-output/physical-cdc-interstage-20261031-a'
    paths=[p for p in root.rglob('*.rtr') if not p.name.endswith('_exception.rtr')]
    if len(paths)!=1:
        pytest.skip('targeted native evidence is local')
    return paths[0]


def test_actual_interstage_corners(native_report):
    rows=audit.records(native_report)
    assert len(rows)==12
    assert min(r['SlackNS'] for r in rows if r['Kind']=='setup')==35.165
    assert min(r['SlackNS'] for r in rows if r['Kind']=='hold')==0.4
    assert max(r['ClockToTargetInputNS'] for r in rows)==1.609


@pytest.mark.parametrize('mutation',['missing_chain','wrong_source','violated','duplicate'])
def test_corrupt_interstage_report_rejected(native_report,tmp_path,mutation):
    text=native_report.read_text(encoding='ascii')
    if mutation=='missing_chain':
        text=text.replace(audit.T1+'/I4',audit.T1+'/I2')
    elif mutation=='wrong_source':
        text=re.sub(r'(?m)^(Startpoint\s*:\s*)'+re.escape(audit.P0+'/CLK'),
                    lambda m:m[1]+'wrong_source/CLK',text,count=1)
    elif mutation=='violated':
        text=text.replace('Slack (MET)','Slack (VIOLATED)',1)
    else:
        block=re.search(r'(?ms)^Startpoint\s*:.*?^ Slack \(MET\)[^\n]*\n',text)
        assert block
        text+='\n'+block.group()
    path=tmp_path/'changed.rtr'
    path.write_text(text,encoding='ascii')
    with pytest.raises(ValueError):
        audit.records(path)
