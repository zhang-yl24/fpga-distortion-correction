"""Fresh reset proposals must reconstruct this report, never old target counts."""
from collections import Counter
import copy
import json
from pathlib import Path
import sys
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import camera720_view_toggle_reset as reset


def rows():
    ip = 'u_ddr3_test_h/u_ddrphy_top/'
    sl = ip + 'ddrphy_slice_top/i_dqs_group[3].ddrphy_data_slice/'
    return [
        ('power_ready/opit_0/CLK', 'board27', 'rst_clk', ip+'u_ddrphy_rst_seq_rstn_sync/sig_async_r1[0]/opit_0/RS'),
        (ip+'ddrphy_cpd_ctrl/ddrphy_cpd_rstn/opit_0/CLK', 'rst_clk', 'phy_dq_sysclk_0', ip+'u_ddrphy_cpd/cpd_inst/RST'),
        (ip+'ddrphy_reset_ctrl/ddrphy_dqs_rst/opit_0/CLK', 'rst_clk', 'phy_dq_sysclk_1', sl+'dq_loop[7].u_iobuf_dq/opit_1/ISR_IOLHR'),
        (ip+'ddrphy_reset_ctrl/ddrphy_dqs_rst/opit_0/CLK', 'rst_clk', 'phy_dq_sysclk_1', sl+'dq_loop[6].u_iobuf_dq/opit_1/ISR_IOLHR'),
        (ip+'ddrphy_reset_ctrl/ddrphy_iol_rst/opit_0/CLK', 'rst_clk', 'phy_dq_sysclk_1', sl+'dq_loop[7].u_iobuf_dq/opit_1/TSR'),
        (ip+'ddrphy_training_ctrl/ddrphy_dqs_training_rstn/opit_0/CLK', 'ddrphy_sysclk', 'phy_dq_sysclk_1', sl+'u_ddc_x/opit_0/RST_TRAINING_N'),
    ]


def report_text():
    text = '| Design : '+reset.TARGET+'\n'
    grouped = Counter((launch, capture) for _, launch, capture, _ in rows())
    for corner in ('Slow', 'Fast'):
        text += 'Recovery Summary('+corner+' Corner):\n'
        for (launch, capture), count in grouped.items():
            text += f'{launch} {capture} 1.000 0.000 0 {count}\n'
    for corner in ('slow', 'fast'):
        for source, launch, capture, endpoint in rows():
            text += (f'Startpoint : {source}\nEndpoint : {endpoint}\nPath Group : {capture}\n'
                     f'Path Type : max ({corner} corner)\nPath Class : async timing path\n'
                     f' Clock {launch} (rising edge)\n node tco 0.100 0.100 r node\n'
                     f' Clock {capture} (rising edge)\n Recovery time 0.100\n Slack (MET) 1.000\n')
    return text


def test_complete_report_counts_are_derived_from_current_six_pairs(tmp_path):
    path = tmp_path/'timing.rtr'
    original = report_text()
    path.write_text(original, encoding='utf-8')
    inventory, adapter = reset.report_inventory(path)
    queries, body, fdc, commands = reset.exact_scope(inventory)
    assert inventory['Corners']['slow']['LogicalChecks'] == 6
    assert inventory['Corners']['fast']['LogicalChecks'] == 6
    assert len(queries) == 5
    assert sum(q['ExpectedTargetCount'] for q in queries) == 6
    assert {q['Family']:q['ExpectedTargetCount'] for q in queries}['dqs_reset'] == 2
    assert 'CAMERA720_VIEW_RESET_QUERY_' in body
    assert len(commands) == 5 and 'set_clock_groups' not in fdc
    assert adapter['NativeNamesAndLineNumbersUnchanged']
    assert path.read_text(encoding='utf-8') == original


def test_missing_report_path_cannot_reuse_summary_count(tmp_path):
    path = tmp_path/'timing.rtr'
    text = report_text()
    path.write_text(text[:text.rfind('Startpoint')], encoding='utf-8')
    with pytest.raises(ValueError, match='incomplete current recovery inventory'):
        reset.report_inventory(path)


@pytest.mark.parametrize('header', ['| Design : other\n', '',
                                  ('| Design : '+reset.TARGET+'\n')*2])
def test_wrong_missing_or_duplicate_design_rejected(tmp_path, header):
    path = tmp_path/'timing.rtr'
    path.write_text(header, encoding='utf-8')
    with pytest.raises(ValueError):
        reset.report_inventory(path)


def test_data_endpoint_is_never_made_a_reset_exception(tmp_path):
    path = tmp_path/'timing.rtr'
    path.write_text(report_text(), encoding='utf-8')
    inventory, _ = reset.report_inventory(path)
    changed = copy.deepcopy(inventory)
    check = next(c for c in changed['Corners']['slow']['Checks'] if c['Family']=='dqs_reset')
    check['Endpoint'] = check['Endpoint'].rsplit('/',1)[0]+'/D'
    with pytest.raises(ValueError, match='non-reset target'):
        reset.exact_scope(changed)


def test_adapter_changes_only_the_unique_module_token():
    text = 'module '+reset.TARGET+' (input clk);\n// '+reset.TARGET+'\nwire '+reset.TARGET+'_net;\nendmodule\n'
    assert reset.adapt_netlist(text) == text.replace('module '+reset.TARGET, 'module camera_vga_output_top',1)
    for invalid in ('module wrong (); endmodule', text+'module extra (); endmodule', 'wire x;'):
        with pytest.raises(ValueError, match='exactly one'):
            reset.adapt_netlist(invalid)


def test_prepared_scope_still_requires_native_binding_and_has_exact_file_hashes(tmp_path):
    report, netlist, adf = (tmp_path/n for n in ('timing.rtr','netlist.v','input.adf'))
    report.write_text(report_text(), encoding='utf-8')
    netlist.write_text('module '+reset.TARGET+' (); endmodule\n', encoding='utf-8')
    adf.write_bytes(b'test-only-adf')
    output = tmp_path/'scope'
    graph = {'Status':'pass','InternalFunctionalTargetsVerified':5}
    with mock.patch.object(reset.graph,'audit_text',return_value=graph):
        value = reset.prepare(report,netlist,adf,output)
    assert value['UniqueSourceEndpointPairs']==6
    assert value['ResetConnectivityVerified']
    for flag in ('ReportNativeADFBindingVerified','NativeQueriesVerified','TimingExceptionApproved',
                 'ConstraintsApplied','HistoricalEndpointInventoryUsed','EDAExecuted','HardwareAccessed',
                 'HardwareReleaseAllowed'):
        assert value[flag] is False
    assert json.loads((output/'proof.json').read_text(encoding='utf-8')) == value
    assert all(reset.sha(output/name)==digest for name,digest in value['FilesSHA256'].items())
    assert all(reset.sha(name)==digest for name,digest in value['InputSHA256'].items())
    with pytest.raises(ValueError,match='fresh reset output'):
        reset.prepare(report,netlist,adf,output)


def test_incomplete_graph_does_not_create_scope_files(tmp_path):
    report, netlist, adf = (tmp_path/n for n in ('timing.rtr','netlist.v','input.adf'))
    report.write_text(report_text(), encoding='utf-8')
    netlist.write_text('module '+reset.TARGET+' (); endmodule\n', encoding='utf-8')
    adf.write_bytes(b'test-only-adf')
    output = tmp_path/'scope'
    with mock.patch.object(reset.graph,'audit_text',return_value={'Status':'pass','InternalFunctionalTargetsVerified':4}):
        with pytest.raises(ValueError,match='every proposed internal endpoint'):
            reset.prepare(report,netlist,adf,output)
    assert not output.exists()
