from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_through_probe as probe
from test_camera720_cdc_native import query, path, header


def actual_query():
    q = query(output='L6Q')
    q.update(Source=probe.SOURCE, LaunchOutput=probe.SOURCE_PARENT+'/L6Q', Endpoint=probe.ENDPOINT)
    return q


def report(tmp_path, command=None, corners=('slow','fast'), launch=None):
    q = actual_query()
    p = tmp_path/'native.rtr'
    command = probe.commands()[0] if command is None else command
    p.write_text(header()+'| Tcl Command : '+command+'\n'+''.join(path(q,c,launch=launch) for c in corners), encoding='ascii')
    return p, q


def test_actual_tco_each_corner_required(tmp_path):
    p,q = report(tmp_path)
    v = probe.parse_report(p,q,probe.commands()[0])
    assert v['LaunchObservedBothCorners'] and v['TimingAccepted'] is False
    assert {r['Corner'] for r in v['Records']} == {'slow','fast'}
    assert {r['LaunchOutput'] for r in v['Records']} == {probe.SOURCE_PARENT+'/L6Q'}


@pytest.mark.parametrize('option', ['from','through','to'])
def test_changed_or_dropped_selector_rejected(tmp_path, option):
    command = probe.commands()[0]
    pin = probe.selector(command, option)
    for changed in (command.replace('-'+option+' {'+pin+'}', ''), command.replace('-'+option+' {'+pin+'}', '-'+option+' {other/pin}')):
        p,q = report(tmp_path, changed)
        with pytest.raises(ValueError):
            probe.parse_report(p,q,command)


def test_alternate_packed_launch_never_counts(tmp_path):
    p,q = report(tmp_path, launch=probe.SOURCE_PARENT+'/L5Q')
    with pytest.raises(ValueError, match='identity'):
        probe.parse_report(p,q,probe.commands()[0])


def test_missing_corner_and_empty_report_fail(tmp_path):
    for corners in (('slow',), ()):
        p,q = report(tmp_path, corners=corners)
        with pytest.raises(ValueError, match='both actual launch corners'):
            probe.parse_report(p,q,probe.commands()[0])


def test_native_t_prefixes_are_normalized_without_dropping_through(tmp_path):
    command = probe.commands()[0]
    for option in ('from','through','to'):
        command = command.replace('-'+option+' {', '-'+option+' {t:')
    p,q = report(tmp_path, command)
    assert probe.parse_report(p,q,probe.commands()[0])['SelectorsRetained']


def test_nested_critical_warning_is_failure_even_with_no_error_lines(tmp_path):
    nested = tmp_path/'child'; nested.mkdir()
    (nested/'run.log').write_text('C: STA-3006: Object x is not a valid endpoint.\nW: ignored port warning\n', encoding='ascii')
    d = probe.scan_diagnostics(tmp_path)
    assert len(d) == 1 and d[0]['Log'] == 'child/run.log' and d[0]['Line'] == 1
    assert d[0]['Text'].startswith('C: STA-3006:')


def test_fixed_renderer_has_only_two_documented_queries(tmp_path):
    text = probe.render(tmp_path)
    assert text.count(probe.inspect.INIT) == 1
    assert text.count('report_path_timing ') == 2 and text.count(' -through ') == 2
    assert probe.commands()[0] in text and probe.commands()[1] in text
    assert 'L6Q} -to' in text and 'L5Q} -to' in text
    assert all(word not in text for word in ('bitstream', 'write_adf', 'set_max_delay', 'exec '))


def test_preparation_never_launches_pds_and_requires_fresh_directory(tmp_path, monkeypatch):
    source = tmp_path/'source.adf'; source.write_bytes(b'test source')
    work = tmp_path/'probe'
    digest = probe.sha(source)
    monkeypatch.setattr(probe, 'CANDIDATE_SHA', digest)
    def recipe(*args):
        value = {'WorkDirectory': str(work), 'SourceADF': str(source)}
        return value, probe.render(work), {source:digest}
    monkeypatch.setattr(probe, 'recipe', recipe)
    monkeypatch.setattr(probe.subprocess, 'Popen', lambda *a, **k: pytest.fail('prepare cannot execute PDS'))
    p = probe.prepare('seed', 'digest', work)
    assert p == work/'stage-plan.json' and probe.sha(work/'input.adf') == digest
    assert (work/'stage.tcl').read_bytes() == probe.render(work).encode('ascii')
    assert {p.name for p in work.iterdir()} == probe.FILES
    assert probe.sha(work/'executor-snapshot.py') == probe.sha(probe.SELF)
    with pytest.raises(ValueError, match='fresh'):
        probe.prepare('seed', 'digest', work)
