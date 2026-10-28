"""CPU-only configuration checks; no simulator or hardware is started."""
from pathlib import Path
import copy
import hashlib
import json
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from simulation_tools import DEFAULT_VIVADO_BIN, prepare_compile_sources, resolve_vivado_bin, verify_compile_sources


@pytest.fixture(autouse=True)
def isolated_simulator_environment(monkeypatch):
    monkeypatch.delenv("FPGA_VIVADO_BIN", raising=False)


def test_existing_default_is_retained_without_local_configuration(tmp_path):
    assert resolve_vivado_bin(tmp_path) == DEFAULT_VIVADO_BIN


def test_local_configuration_supports_utf8_and_relative_paths(tmp_path):
    (tmp_path / "team-config.local.json").write_text(
        json.dumps({"vivado_bin": "工具/Vivado/bin"}, ensure_ascii=False), encoding="utf-8-sig")
    assert resolve_vivado_bin(tmp_path) == tmp_path / "工具/Vivado/bin"


def test_environment_override_takes_precedence_even_if_config_is_invalid(tmp_path, monkeypatch):
    (tmp_path / "team-config.local.json").write_text("invalid JSON", encoding="utf-8")
    expected = tmp_path / "environment-vivado/bin"
    monkeypatch.setenv("FPGA_VIVADO_BIN", str(expected))
    assert resolve_vivado_bin(tmp_path) == expected


def test_blank_environment_uses_absolute_configured_directory(tmp_path, monkeypatch):
    expected = tmp_path / "configured-vivado/bin"
    (tmp_path / "team-config.local.json").write_text(json.dumps({"vivado_bin": str(expected)}), encoding="utf-8")
    monkeypatch.setenv("FPGA_VIVADO_BIN", " ")
    assert resolve_vivado_bin(tmp_path) == expected


@pytest.mark.parametrize("value", [None, "", " "])
def test_empty_configured_path_uses_legacy_default(tmp_path, value):
    (tmp_path / "team-config.local.json").write_text(json.dumps({"vivado_bin": value}), encoding="utf-8")
    assert resolve_vivado_bin(tmp_path) == DEFAULT_VIVADO_BIN


@pytest.mark.parametrize("config", [[], {"vivado_bin": 17}, {"vivado_bin": False}])
def test_malformed_configuration_is_rejected(tmp_path, config):
    (tmp_path / "team-config.local.json").write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError):
        resolve_vivado_bin(tmp_path)


def test_only_bound_include_directives_are_relocated_without_mutating_rtl(tmp_path):
    project, work = tmp_path / "project", tmp_path / "work"
    (project / "rtl").mkdir(parents=True)
    work.mkdir()
    source = project / "rtl/unit.v"
    original = b'`include "D:/English/FPGA/distortion/rtl/crc.vh"\r\n// D:/English/FPGA must stay in comments\r\nmodule unit; endmodule\r\n'
    source.write_bytes(original)
    header = project / "rtl/crc.vh"
    header.write_bytes(b"// synthetic header\n")
    plain = project / "rtl/plain.v"
    plain.write_bytes(b"module plain; endmodule\n")
    compiled, bindings = prepare_compile_sources(project, ["rtl/unit.v", "rtl/plain.v"], ["rtl/crc.vh"], work)
    assert source.read_bytes() == original
    assert compiled[1] == plain
    assert set(bindings) == {"rtl/unit.v"}
    assert compiled[0].read_bytes() == original.replace(
        b'"D:/English/FPGA/distortion/rtl/crc.vh"', b'"relocated-headers/rtl/crc.vh"')
    assert (work / "relocated-headers/rtl/crc.vh").read_bytes() == header.read_bytes()
    assert bindings["rtl/unit.v"]["IncludePathReplacements"][0]["Header"] == "rtl/crc.vh"
    verify_compile_sources(project, ["rtl/unit.v", "rtl/plain.v"], ["rtl/crc.vh"], work, bindings)
    with pytest.raises(FileExistsError):
        prepare_compile_sources(project, ["rtl/unit.v"], ["rtl/crc.vh"], work)


@pytest.mark.parametrize("include", ["rtl/unbound.vh", "../outside.vh"])
def test_include_outside_frozen_header_closure_is_rejected(tmp_path, include):
    project, work = tmp_path / "project", tmp_path / "work"
    project.mkdir()
    work.mkdir()
    (project / "unit.v").write_text('`include "D:/English/FPGA/distortion/' + include + '"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="bound header closure"):
        prepare_compile_sources(project, ["unit.v"], [], work)


@pytest.mark.parametrize("change", ["missing-binding", "extra-binding", "source-rehashed", "header-rehashed"])
def test_relocated_files_cannot_be_relabelled_as_an_exact_transformation(tmp_path, change):
    project, work = tmp_path / "project", tmp_path / "work"
    project.mkdir()
    work.mkdir()
    (project / "unit.v").write_text('`include "D:/English/FPGA/distortion/header.vh"\nmodule unit; endmodule\n', encoding="utf-8")
    (project / "header.vh").write_text("// synthetic header\n", encoding="utf-8")
    _, bindings = prepare_compile_sources(project, ["unit.v"], ["header.vh"], work)
    if change == "missing-binding":
        bindings.clear()
    elif change == "extra-binding":
        bindings["extra.v"] = copy.deepcopy(bindings["unit.v"])
    elif change == "source-rehashed":
        item = bindings["unit.v"]
        path = Path(item["CompiledPath"])
        path.write_bytes(path.read_bytes() + b"// unauthorized RTL change\n")
        item["CompiledSHA256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    else:
        item = bindings["unit.v"]["IncludePathReplacements"][0]
        path = Path(item["CompiledHeaderPath"])
        path.write_bytes(b"// unauthorized header change\n")
        item["HeaderSHA256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="exact include-only transformation"):
        verify_compile_sources(project, ["unit.v"], ["header.vh"], work, bindings)
