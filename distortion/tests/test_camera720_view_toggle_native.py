"""Reject edits that would change the read-only native inspection's scope."""
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_view_toggle_native as native


@pytest.mark.parametrize('field,value', [
    ('Command', ['unreviewed.exe']), ('MaximumSeconds', 3600),
    ('Mode', 'program'), ('ExpectedStages', ['Generate Bitstream']),
    ('WorkDirectory', 'another-directory'),
])
def test_scope_change_rejected_before_process_launch(tmp_path, field, value):
    work = tmp_path.resolve()
    executable = str(work/'pds_shell.exe')
    plan = {'Schema':'camera720-view-toggle-inspection-v1','Target':native.TARGET,
            'BuildPlan':str(work/'build-plan.json'), 'WorkDirectory':str(work),
            'Mode':'report','ExpectedStages':[],'MaximumSeconds':300,
            'Command':[executable,'-file',(work/'stage.tcl').as_posix(),
                       '-work_dir',work.as_posix(),'-project_name',native.TARGET]}
    plan[field] = value
    with mock.patch.object(native, 'read', return_value=plan), \
         mock.patch.object(native, 'os', SimpleNamespace(name='nt')), \
         mock.patch.object(native.build, 'work_path', return_value=work), \
         mock.patch.object(native.build, 'validate', return_value={'PDS':{'Executable':executable}}), \
         mock.patch.object(native.subprocess, 'Popen', side_effect=AssertionError('process launched')):
        with pytest.raises(ValueError, match='command, deadline, mode or directory'):
            native.execute(work/'stage-plan.json')
