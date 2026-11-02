"""A hold-route experiment needs every actual launch's setup/hold evidence."""
import json
from pathlib import Path
import sys
from unittest import mock

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_view_toggle_hold as hold


def baseline(tmp_path):
    report=tmp_path/'timing.rtr'
    report.write_text('native timing bytes',encoding='ascii')
    value={'Schema':'camera720-view-toggle-hold-analysis-v1','Target':hold.TARGET,
           'MissingExactSetup':[],'MissingLaunchCases':[],
           'InputReports':[{'Path':str(report),'SHA256':hold.sha(report)}],
           'Paths':[{'Margins':{'slow':{'ExactSetupSlackNS':1.0},'fast':{'ExactSetupSlackNS':1.5}},
                     'PhysicalRepairCandidate':{'Net':'_N1'}}]}
    return report,value


@pytest.mark.parametrize('kind', ['missing_setup','missing_through','zero_setup','source_drift'])
def test_incomplete_or_changed_measurement_never_selects_route(tmp_path,kind):
    report,value=baseline(tmp_path)
    if kind=='missing_setup':
        value['MissingExactSetup']=[{'Corner':'fast'}]
    elif kind=='missing_through':
        value['MissingLaunchCases']=[{'Through':'L6Q','Kind':'setup','Corner':'fast'}]
    elif kind=='zero_setup':
        value['Paths'][0]['Margins']['slow']['ExactSetupSlackNS']=0.0
    else:
        report.write_text('changed bytes',encoding='ascii')
    analysis=tmp_path/'analysis.json'
    analysis.write_text(json.dumps(value),encoding='ascii')
    with mock.patch.object(hold.routes,'inspect',side_effect=AssertionError('route parsed before evidence passed')):
        with pytest.raises(ValueError):
            hold.derive_waypoints(analysis,tmp_path/'route.txt')


def test_another_design_header_is_rejected(tmp_path):
    report=tmp_path/'timing.rtr'
    report.write_text('| Design : camera720_calibrated_stats_delay_top\n',encoding='ascii')
    with pytest.raises(ValueError,match='exact view-toggle'):
        hold.report_identity(report)
