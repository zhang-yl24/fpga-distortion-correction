"""Reject ambiguous/incomplete native pad-delay evidence."""
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import prepare_processed_output_tx_delays as delay


@pytest.fixture
def native_query():
    path = delay.tx.BUILD / 'physical-tx-probe-20261031-a/stdout.log'
    if not path.is_file():
        pytest.skip('native probe is local')
    log = path.read_text()
    body = log.split('TX_G0_MIN_FAST\n', 1)[1].split('TX_CLOCK_MIN_FAST\n', 1)[0]
    job = {'Marker': 'TEST_QUERY', 'Start': 'system/output_video/g[0]/opit_0_L8Q_perm/CLK',
           'End': 'g_out[0]', 'StartEdge': 'rise', 'EndEdge': 'fall', 'Condition': 'min'}
    return 'TEST_QUERY_BEGIN\n' + body + 'TEST_QUERY_END\n', job


def test_actual_native_probe(native_query):
    log, job = native_query
    record, = delay.parse_jobs(log, [job])
    assert record['DelayNS'] == 3.250
    assert record['NativePaths'][0]['Rows'] == 7


@pytest.mark.parametrize('mutation', ['missing_marker', 'duplicate_marker', 'wrong_edge',
                                     'wrong_boundary', 'extra_path_start'])
def test_ambiguous_native_evidence_is_rejected(native_query, mutation):
    log, job = native_query
    if mutation == 'missing_marker':
        log = log.replace('TEST_QUERY_END', 'OTHER_END')
    elif mutation == 'duplicate_marker':
        log = log + log
    elif mutation == 'wrong_edge':
        job = {**job, 'EndEdge': 'rise'}
    elif mutation == 'wrong_boundary':
        job = {**job, 'Start': delay.PLL}
    else:
        log = log.replace('TEST_QUERY_END', 'Path start...\nTEST_QUERY_END')
    with pytest.raises(ValueError):
        delay.parse_jobs(log, [job])
