"""Synthetic CPU-only rowpipe closure checks; never run RTL/EDA or hardware."""
from pathlib import Path
import json
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import run_board1080_rowpipe_system_sim as runner


@pytest.fixture
def sources(tmp_path):
    original = tmp_path / runner.ORIGINAL_CACHE
    original.parent.mkdir(parents=True)
    original.write_bytes(b"// synthetic frozen cache\n")
    candidate = tmp_path / runner.CANDIDATE_CACHE
    candidate.write_bytes(b"// synthetic rowpipe cache\n")
    sampler = tmp_path / runner.ORIGINAL_SAMPLER
    sampler.write_bytes(b"module ddr_remap_sample_scatter4;\n    ddr_neighbour_cache_scatter4 #(1) cache();\nendmodule\n")
    (tmp_path / runner.CANDIDATE_SAMPLER).write_bytes(runner.SAMPLER_NOTE + sampler.read_bytes().replace(
        b"    ddr_neighbour_cache_scatter4 #(", b"    ddr_neighbour_cache_scatter4_rowpipe #("))
    proof = {"BaseSource": runner.ORIGINAL_CACHE, "BaseSHA256": runner.system.sha(original),
             "Candidate": runner.CANDIDATE_CACHE, "CandidateSHA256": runner.system.sha(candidate),
             "PublicFIFO2NormalizedBytesEqual": True, "SlowStateMachineBytesEqual": True,
             "AddedElasticStages": 1}
    path = tmp_path / runner.PROOF
    path.parent.mkdir()
    path.write_text(json.dumps(proof), encoding="utf-8")
    names = ("rtl/unrelated.v", runner.ORIGINAL_CACHE, runner.ORIGINAL_SAMPLER, runner.ORIGINAL_SYSTEM)
    frozen = {runner.ORIGINAL_CACHE: proof["BaseSHA256"], "rtl/unrelated.v": "unrelated-frozen-value"}
    return tmp_path, names, frozen, ("tools/old.py",), proof


def configure(sources):
    root, names, frozen, helpers, _ = sources
    return runner.configuration(root, names, frozen, helpers)


def test_exact_closure_replacement_preserves_other_frozen_sources_and_helpers(sources):
    result = configure(sources)
    assert result["COMPILE"] == ("rtl/unrelated.v", runner.CANDIDATE_CACHE,
                                  runner.CANDIDATE_SAMPLER, runner.CDC_SYSTEM)
    assert not {runner.ORIGINAL_CACHE, runner.ORIGINAL_SAMPLER, runner.ORIGINAL_SYSTEM}.intersection(result["COMPILE"])
    assert len(result["COMPILE"]) == len(set(result["COMPILE"]))
    assert result["FROZEN"] == {"rtl/unrelated.v": "unrelated-frozen-value",
                                runner.CANDIDATE_CACHE: sources[-1]["CandidateSHA256"]}
    assert result["HELPERS"] == ("tools/old.py", runner.SELF, runner.PROOF, runner.ORIGINAL_SAMPLER)
    assert sources[2][runner.ORIGINAL_CACHE] == sources[-1]["BaseSHA256"]


@pytest.mark.parametrize("part", ["candidate", "original-cache", "sampler", "proof"])
def test_unreviewed_source_changes_rejected(sources, part):
    root, _, _, _, proof = sources
    if part == "candidate":
        (root / runner.CANDIDATE_CACHE).write_bytes(b"changed rowpipe")
    elif part == "original-cache":
        (root / runner.ORIGINAL_CACHE).write_bytes(b"changed frozen base")
    elif part == "sampler":
        path = root / runner.CANDIDATE_SAMPLER
        path.write_bytes(path.read_bytes()+b"// unrelated sampler change\n")
    else:
        proof["PublicFIFO2NormalizedBytesEqual"] = False
        (root / runner.PROOF).write_text(json.dumps(proof), encoding="utf-8")
    with pytest.raises(ValueError):
        configure(sources)


def test_missing_original_cache_file_or_freeze_key_rejected(sources):
    root, names, frozen, helpers, _ = sources
    missing_key = dict(frozen)
    missing_key.pop(runner.ORIGINAL_CACHE)
    with pytest.raises(ValueError, match="original frozen cache"):
        runner.configuration(root, names, missing_key, helpers)
    (root / runner.ORIGINAL_CACHE).unlink()
    with pytest.raises(ValueError, match="original frozen cache"):
        configure(sources)


@pytest.mark.parametrize("change", ["missing-cache", "extra-candidate-sampler", "duplicate-sampler"])
def test_original_and_candidate_same_module_cannot_share_a_compile_closure(sources, change):
    root, names, frozen, helpers, _ = sources
    if change == "missing-cache":
        names = tuple(n for n in names if n != runner.ORIGINAL_CACHE)
    elif change == "extra-candidate-sampler":
        names += (runner.CANDIDATE_SAMPLER,)
    else:
        names += (runner.ORIGINAL_SAMPLER,)
    with pytest.raises(ValueError):
        runner.configuration(root, names, frozen, helpers)


def test_runner_configuration_is_restored_after_exception(sources, monkeypatch):
    root, names, frozen, helpers, _ = sources
    monkeypatch.setattr(runner, "ROOT", root)
    monkeypatch.setattr(runner, "BASE", root / "isolated-work")
    monkeypatch.setattr(runner.system, "COMPILE", names)
    monkeypatch.setattr(runner.system, "HELPERS", helpers)
    monkeypatch.setattr(runner.system.fixtures.previous, "FROZEN", frozen)
    saved = (runner.system.BASE, runner.system.COMPILE, runner.system.HELPERS,
             runner.system.fixtures.previous.FROZEN)
    with pytest.raises(RuntimeError, match="synthetic interruption"):
        with runner.configured_system():
            assert runner.system.BASE == root / "isolated-work"
            assert runner.CANDIDATE_CACHE in runner.system.COMPILE
            assert runner.ORIGINAL_CACHE not in runner.system.fixtures.previous.FROZEN
            raise RuntimeError("synthetic interruption")
    assert (runner.system.BASE, runner.system.COMPILE, runner.system.HELPERS,
            runner.system.fixtures.previous.FROZEN) == saved


def test_entrypoint_delegates_only_while_isolated_configuration_is_active(sources, monkeypatch):
    root, names, frozen, helpers, _ = sources
    monkeypatch.setattr(runner, "ROOT", root)
    monkeypatch.setattr(runner.system, "COMPILE", names)
    monkeypatch.setattr(runner.system, "HELPERS", helpers)
    monkeypatch.setattr(runner.system.fixtures.previous, "FROZEN", frozen)
    def no_simulator(args):
        assert runner.CANDIDATE_CACHE in runner.system.COMPILE
        assert runner.CANDIDATE_SAMPLER in runner.system.COMPILE
        assert runner.CDC_SYSTEM in runner.system.COMPILE
        return {"synthetic": True, "hardware_accessed": False}
    monkeypatch.setattr(runner.system, "run", no_simulator)
    assert runner.run(object()) == {"synthetic": True, "hardware_accessed": False}
    assert runner.system.COMPILE == names
