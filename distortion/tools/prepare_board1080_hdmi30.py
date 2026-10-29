"""Prepare the isolated 1080p30 EDID profile; preserve the audited baseline.

Exactly one controller is replaced in the 109-source closure. The established
source-role preparer handles IDF ownership, include copies and PDS declarations.
No EDA, prior timing-result reuse, bit generation or hardware action occurs.
"""
from pathlib import Path
import argparse
import json

import board1080_edid as edid
import prepare_board1080_timing as timing

PROJECT = Path(__file__).resolve().parents[1]
BASE = "board/board1080-rowpipe-sources.json"
MANIFEST = "board/board1080-hdmi30-sources.json"
ORIGINAL = "platform/video_base/source/hdmi/ms7200_ctl.v"
REPLACEMENT = "rtl/experimental/ms7200_1080p30_ctl.v"


def expected_manifest(project=PROJECT):
    project = Path(project).resolve()
    timing.validate_manifest(project, BASE)
    base = json.loads((project / BASE).read_text(encoding="utf-8"))
    edid.audit_controller(project / REPLACEMENT, project / ORIGINAL)
    if base["source_files"].count(ORIGINAL) != 1 or REPLACEMENT in base["source_files"]:
        raise ValueError("one baseline RX controller replacement required")
    result = dict(base)
    result.update(
        Schema="board1080-hdmi30-edid-closure-v1",
        Candidate="1080p30-only HDMI EDID candidate; new synthesis, route and board validation required",
        source_files=[REPLACEMENT if name == ORIGINAL else name for name in base["source_files"]],
        SourceSHA256={REPLACEMENT if name == ORIGINAL else name:
                      timing.sha(project / REPLACEMENT) if name == ORIGINAL else digest
                      for name, digest in base["SourceSHA256"].items()},
        BaseManifest={"Path": "distortion/" + BASE, "SHA256": timing.sha(project / BASE)},
        HDMIControllerReplacement={"Original": ORIGINAL, "Replacement": REPLACEMENT,
                                   "Scope": "EDID bytes only; non-EDID registers and FSM preserved",
                                   "PreferredMode": "1920x1080p30", "PixelClockHz": 74250000,
                                   "PriorTimingOrBitstreamReusable": False})
    return result


def validate_profile(project=PROJECT):
    project = Path(project).resolve()
    actual = json.loads((project / MANIFEST).read_text(encoding="utf-8"))
    if actual != expected_manifest(project):
        raise ValueError("HDMI30 manifest differs from its single-controller replacement")
    return timing.validate_manifest(project, MANIFEST)


def prepare(project, work_dir, *, repo_alias="P:/", pds_shell="D:/pango/PDS_2023.2/bin/pds_shell.exe"):
    project = Path(project).resolve()
    validate_profile(project)
    watched = {Path(__file__).resolve(): timing.sha(__file__),
               Path(edid.__file__).resolve(): timing.sha(edid.__file__)}
    plan = timing.prepare(project, work_dir, manifest_name=MANIFEST, repo_alias=repo_alias,
                          pds_shell=pds_shell, clock_tree_hold_target_ps=200)
    for path, digest in watched.items():
        if timing.sha(path) != digest:
            raise ValueError("HDMI profile helper changed during preparation")
        plan["InputSHA256"][path.relative_to(project).as_posix()] = digest
    plan.update(Schema="board1080-hdmi30-timing-preparation-v1",
                HDMIEDIDProfileVerified=True, PreviousCandidateTimingReused=False,
                PreviousCandidateBitstreamReused=False, HardwareReleaseAllowed=False)
    path = Path(work_dir) / "plan.json"
    path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-manifest", action="store_true")
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--repo-alias", default="P:/")
    parser.add_argument("--pds-shell", default="D:/pango/PDS_2023.2/bin/pds_shell.exe")
    args = parser.parse_args(argv)
    if args.write_manifest:
        if args.work_dir is not None:
            parser.error("write the manifest or prepare a build, not both")
        result = expected_manifest()
        with (PROJECT / MANIFEST).open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(result, stream, indent=2, ensure_ascii=False); stream.write("\n")
        print(json.dumps({"Manifest": MANIFEST, "SourceCount": len(result["source_files"])}))
    elif args.work_dir is not None:
        result = prepare(PROJECT, args.work_dir, repo_alias=args.repo_alias, pds_shell=args.pds_shell)
        print(json.dumps({"PreparedOnly": True, "EDAExecuted": False,
                          "Manifest": result["Manifest"], "WorkDirectory": result["WorkDirectory"]}))
    else:
        validate_profile()
        print(json.dumps({"ProfileValid": True, "EDAExecuted": False, "HardwareAccessed": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
