"""Select an isolated checked-I2C source closure; no compile or PDS preparation.

The existing FDC still declares SCL as an output. Keeping it in this source-only
inventory is not approval for the new inout interface or prior STA reuse.
"""
from pathlib import Path
import argparse
import copy
import json

import prepare_board1080_hdmi30 as hdmi30
import prepare_board1080_checked_top as top
import run_ms72xx_checked_sim as controller

PROJECT = Path(__file__).resolve().parents[1]
BASE = hdmi30.MANIFEST
MANIFEST = 'board/board1080-checked-sources.json'
REPLACEMENTS = {
    'platform/video_base/source/hdmi/iic_dri.v': 'rtl/experimental/iic_dri_checked.v',
    'platform/video_base/source/hdmi/ms7210_ctl.v': 'rtl/experimental/ms7210_checked_ctl.v',
    'platform/video_base/source/hdmi/ms72xx_ctl.v': 'rtl/experimental/ms72xx_checked_ctl.v',
    'board/board1080_rowpipe_top.v': 'board/board1080_checked_top.v',
}
sha = hdmi30.timing.sha


def require(condition, message):
    if not condition:
        raise ValueError(message)


def expected_manifest(project=PROJECT):
    project = Path(project).resolve()
    roles = hdmi30.validate_profile(project)
    base_path = project / BASE
    before = sha(base_path)
    base = json.loads(base_path.read_text(encoding='utf-8-sig'))
    names = base['source_files']
    require(len(names) == len(set(names)) == 109, 'exact 109-source baseline required')
    require(all(names.count(old) == 1 and new not in names for old, new in REPLACEMENTS.items()),
            'exactly four fresh replacements required')
    top_audit = top.audit(project)
    require(top_audit['Baseline'] == top.BASELINE and top_audit['Candidate'] == top.CANDIDATE,
            'checked top audit identity differs')
    tx_audit = controller.audit_tx_copy(project / 'platform/video_base/source/hdmi/ms7210_ctl.v',
                                      project / 'rtl/experimental/ms7210_checked_ctl.v')
    require(tx_audit['ExactTransformationVerified'] is True, 'checked TX source audit failed')
    helpers = (Path(__file__), Path(hdmi30.__file__), Path(hdmi30.timing.__file__),
               Path(hdmi30.edid.__file__), Path(top.__file__), Path(controller.__file__))
    tool_hashes = {p.resolve().relative_to(PROJECT).as_posix(): sha(p) for p in helpers}
    replacements = {new: sha(project / new) for new in REPLACEMENTS.values()}
    require(top_audit['CandidateSHA256'] == replacements[top.CANDIDATE], 'checked top changed during audit')
    result = copy.deepcopy(base)
    result.update(Schema='board1080-checked-source-selection-v1',
        Candidate='Checked I2C source selection only; SCL inout constraints and PDS integration unverified',
        source_files=[REPLACEMENTS.get(name, name) for name in names],
        SourceSHA256={REPLACEMENTS.get(name, name): replacements[REPLACEMENTS[name]]
                      if name in REPLACEMENTS else digest for name, digest in base['SourceSHA256'].items()},
        BaseManifest={'Path': 'distortion/' + BASE, 'SHA256': before},
        CheckedControllerReplacements=dict(REPLACEMENTS), ValidationToolsSHA256=tool_hashes,
        CheckedTopSourceAudit={'BaselineSHA256': top_audit['BaselineSHA256'],
                              'CandidateSHA256': top_audit['CandidateSHA256'], 'ExactTransformationVerified': True},
        CheckedTXSourceAudit=tx_audit, SourceClosureSelected=True, CompiledIntegrationVerified=False,
        ElectricalConstraintStatus='UnverifiedForSCLInout', FDCAndRCFUnchanged=True,
        PDSExecuted=False, EligibleForPDSOrHardware=False, HardwareAccessed=False,
        TimingAccepted=False, PhysicalTimingReady=False, HardwareReleaseAllowed=False,
        PreviousCandidateTimingReusable=False, PreviousCandidateBitstreamReusable=False)
    require(hdmi30.validate_profile(project) == roles and sha(base_path) == before,
            'HDMI30 baseline changed during selection')
    require(all(sha(project / name) == digest for name, digest in replacements.items()),
            'checked source changed during selection')
    require(all(sha(PROJECT / name) == digest for name, digest in tool_hashes.items()),
            'selection auditor changed during audit')
    return result


def validate_profile(project=PROJECT):
    project = Path(project).resolve()
    actual = json.loads((project / MANIFEST).read_text(encoding='utf-8-sig'))
    require(actual == expected_manifest(project), 'checked manifest differs from exact four-source selection')
    return actual


def write_manifest(project=PROJECT):
    project = Path(project).resolve()
    require(not (project / MANIFEST).exists(), 'manifest already exists')
    result = expected_manifest(project)
    with (project / MANIFEST).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False); stream.write('\n')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-manifest', action='store_true')
    args = parser.parse_args(argv)
    result = write_manifest() if args.write_manifest else validate_profile()
    print(json.dumps({'SourceClosureSelected': True, 'Sources': len(result['source_files']),
                      'CompiledIntegrationVerified': False, 'PDSExecuted': False, 'HardwareReleaseAllowed': False}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
