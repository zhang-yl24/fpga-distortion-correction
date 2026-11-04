"""Resolve local simulation tools without starting an EDA process."""
from pathlib import Path
import hashlib
import json
import os
import re


DEFAULT_VIVADO_BIN = Path("E:/Vivado/Vivado/2017.4/bin")


def resolve_vivado_bin(workspace):
    """Use FPGA_VIVADO_BIN, then workspace config, then the legacy default."""
    workspace = Path(workspace).resolve()
    override = os.environ.get("FPGA_VIVADO_BIN", "").strip()
    if override:
        value = override
    else:
        config_path = workspace / "team-config.local.json"
        config = json.loads(config_path.read_text(encoding="utf-8-sig")) if config_path.is_file() else {}
        if not isinstance(config, dict):
            raise ValueError("team-config.local.json must contain a JSON object")
        value = config.get("vivado_bin")
        if value is not None and not isinstance(value, str):
            raise ValueError("vivado_bin must be a path string")
        value = value.strip() if value is not None else ""
        if not value:
            return DEFAULT_VIVADO_BIN
    path = Path(value)
    return path if path.is_absolute() else workspace / path


def _compile_sources(project, names, headers, work, *, write):
    """Relocate only legacy include directives into fresh generated copies.

    Original RTL stays byte-identical. Each replaced include must name a header
    already present in the caller's bound source closure.
    """
    project, work = Path(project).resolve(), Path(work).resolve()
    allowed = set(headers)
    compiled, bindings, staged_headers = [], {}, {}
    pattern = re.compile(rb'(?m)^([ \t]*`include[ \t]+")D:/English/FPGA/distortion/([^"\r\n]+)(")')
    for name in names:
        source = (project / name).resolve()
        if not source.is_relative_to(project) or not source.is_file():
            raise ValueError("compiled source is missing or outside the project")
        original = source.read_bytes()
        replacements = []

        def replace(match):
            relative = match.group(2).decode("utf-8")
            header = (project / relative).resolve()
            if relative not in allowed or not header.is_relative_to(project) or not header.is_file():
                raise ValueError("legacy include is outside the bound header closure: " + relative)
            if relative not in staged_headers:
                copy = work / "relocated-headers" / relative
                if write:
                    copy.parent.mkdir(parents=True, exist_ok=True)
                    with copy.open("xb") as stream:
                        stream.write(header.read_bytes())
                staged_headers[relative] = copy
            copy = staged_headers[relative]
            replacements.append({"Original": match.group(0).decode("utf-8"),
                                 "Header": relative,
                                 "HeaderSHA256": hashlib.sha256(header.read_bytes()).hexdigest(),
                                 "CompiledHeaderPath": str(copy)})
            # Include tokens stay relative to the simulator workdir, so old
            # Verilog preprocessors never need to decode a Unicode disk path.
            return match.group(1) + copy.relative_to(work).as_posix().encode("utf-8") + match.group(3)

        effective = pattern.sub(replace, original)
        target = source
        if replacements:
            target = work / "relocated-sources" / name
            if write:
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as stream:
                    stream.write(effective)
            bindings[name] = {"OriginalSHA256": hashlib.sha256(original).hexdigest(),
                              "CompiledPath": str(target),
                              "CompiledSHA256": hashlib.sha256(effective).hexdigest(),
                              "IncludePathReplacements": replacements}
        compiled.append(target)
    return compiled, bindings


def prepare_compile_sources(project, names, headers, work):
    """Create fresh copies with only bound legacy include paths relocated."""
    return _compile_sources(project, names, headers, work, write=True)


def verify_compile_sources(project, names, headers, work, bindings):
    """Recompute the complete allowed transformation; never trust self-reported hashes."""
    _, expected = _compile_sources(project, names, headers, work, write=False)
    if bindings != expected:
        raise ValueError("relocated compilation bindings differ from the exact include-only transformation")
    for item in expected.values():
        source = Path(item["CompiledPath"])
        if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != item["CompiledSHA256"]:
            raise ValueError("relocated compilation source changed")
        for entry in item["IncludePathReplacements"]:
            header = Path(entry["CompiledHeaderPath"])
            if not header.is_file() or hashlib.sha256(header.read_bytes()).hexdigest() != entry["HeaderSHA256"]:
                raise ValueError("relocated compilation header changed")
