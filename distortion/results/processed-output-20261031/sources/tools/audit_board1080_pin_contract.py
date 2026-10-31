"""Compare board1080 top/FDC/native PCF/routed pads and reference declarations.

This reads the fresh source-build mapping artifacts, not a final-bitstream pin
export. Matching declared voltages does not measure the board supply rails.
No EDA, hardware access, constraints, RTL or release decisions are performed.
"""
from collections import Counter, defaultdict
from pathlib import Path
import argparse
import hashlib
import json
import re


PROJECT = Path(__file__).resolve().parents[1]
PORT = r"[A-Za-z_]\w*(?:\[\d+\])?"
PAD = re.compile(r"[A-Z]{1,2}[1-9][0-9]*\Z")
OMITTED_RGB565 = frozenset([f"{c}_in[{i}]" for c,n in (("r",3),("g",2),("b",3)) for i in range(n)])
ALIASES = {"clk_27m":"sys_clk", "reset_n":"rst_in", "led[0]":"heart_beat_led",
           "led[1]":"ddr_init_done", "led[2]":"init_over_rx", "led[3]":"hdmi_int_led"}
DIFFERENTIAL_PAIRS = [("clk_p","clk_n"),("mem_ck","mem_ck_n"),
                      *((f"mem_dqs[{i}]",f"mem_dqs_n[{i}]") for i in range(4))]
KEYS = ("LOC", "VCCIO", "STANDARD", "DIRECTION")
SOURCE_ADF_SHA256 = "0f6101036b3c3981544e032ec93c3ad2b5468c79e55fa4f8f6a8014265fb15be"
SOURCE_PRT_SHA256 = "1f917eb61f0dffbc235eb932c117a4776e162ecdd0bcae35660cc64628070242"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clean_verilog(text):
    return re.sub(r"/\*.*?\*/|//[^\n]*|\(\*.*?\*\)", "", text, flags=re.S)


def top_ports(text):
    clean = clean_verilog(text)
    matches = re.findall(r"\bmodule\s+board1080_top\s*\((.*?)\)\s*;", clean, re.S)
    require(len(matches) == 1, "one nonparameterized board1080_top interface required")
    ports, direction, bounds = {}, None, None
    for part in matches[0].split(","):
        declaration = re.fullmatch(r"\s*(?:(input|output|inout)\s+)?(?:wire\s+|reg\s+)?"
                                   r"(?:\[\s*(\d+)\s*:\s*(\d+)\s*\]\s*)?([A-Za-z_]\w*)\s*", part)
        require(declaration is not None, "unsupported top port declaration")
        typ, hi, lo, name = declaration.groups()
        if typ:
            direction, bounds = typ.upper(), None
        require(direction is not None, "port direction is missing")
        if hi is not None:
            bounds = (int(hi), int(lo))
            require(bounds[0] >= bounds[1], "ascending port range is unsupported")
        names = [name] if bounds is None else [f"{name}[{i}]" for i in range(bounds[1], bounds[0]+1)]
        for pin in names:
            require(pin not in ports, "duplicate top port")
            ports[pin] = direction
    return ports


def fdc_pins(text):
    pins = {}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if "define_attribute" not in line or "PAP_IO_" not in line:
            continue
        match = re.fullmatch(r"\s*define_attribute\s+\{p:("+PORT+r")\}\s+"
                             r"\{PAP_IO_(\w+)\}\s+\{([^{}]+)\}\s*", line)
        require(match is not None, "unsupported physical pin attribute syntax")
        name, key, value = match.groups()
        row = pins.setdefault(name, {})
        require(key not in row, "duplicate pin attribute: " + name + ":" + key)
        row[key] = value
    require(pins, "physical pin attributes missing")
    return pins


def pcf_pins(text):
    pins = {}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#") or line.startswith("def_inst_site "):
            continue
        match = re.fullmatch(r"def_port \{("+PORT+r")\} (.+)", line)
        require(match is not None, "unsupported native PCF line")
        name, body = match.groups()
        require(name not in pins, "duplicate native PCF port")
        attrs = {}
        for token in body.split():
            attr = re.fullmatch(r"(\w+)=([^=\s]+)", token)
            require(attr is not None, "unsupported native PCF attribute")
            key = "STANDARD" if attr[1] == "IOSTANDARD" else attr[1]
            require(key not in attrs, "duplicate native PCF attribute")
            attrs[key] = attr[2]
        require(PAD.fullmatch(attrs.get("LOC", "")), "AUTO or missing package pin in native PCF")
        pins[name] = attrs
    require(pins, "native PCF has no ports")
    return pins


def routed_pads(text):
    pads, ports = {}, {}
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split("|")
        require(len(parts) == 7 and PAD.fullmatch(parts[0]), "invalid native routed pad row")
        pad, site, bank, function, port, direction, assigned = parts
        require(pad not in pads, "duplicate routed package pad")
        require(re.fullmatch(r"BANK[LR]\d+", bank) and site and function, "routed bank/site/function missing")
        if port:
            require(re.fullmatch(PORT, port) and port not in ports, "duplicate or invalid routed port")
            require(direction in ("input", "output", "inout") and assigned == "YES",
                    "routed port direction or assignment status invalid")
        else:
            require(not direction and not assigned, "unoccupied pad has partial assignment")
        record = dict(Pad=pad, Site=site, Bank=bank, Function=function,
                      Port=port, Direction=direction.upper(), Assignment=assigned)
        pads[pad] = record
        if port:
            ports[port] = record
    return pads, ports


def audit_texts(top, fdc, pcf, prt, reference, legacy_leds, capture):
    ports, declared, generated = top_ports(top), fdc_pins(fdc), pcf_pins(pcf)
    pads, routed = routed_pads(prt)
    official = fdc_pins(reference)
    require(len(ports) == 142 and set(ports) == set(declared) == set(generated),
            "top/FDC/PCF must contain the same142 individual ports")
    locations = [row.get("LOC") for row in declared.values()]
    require(len(set(locations)) == len(locations) and all(PAD.fullmatch(p or "") for p in locations),
            "duplicate, AUTO or missing declared package pin")
    for name, direction in ports.items():
        row = declared[name]
        require(set(KEYS) <= row.keys() and row["DIRECTION"] == direction, "top/FDC direction mismatch: " + name)
        require(generated[name] == {k:v for k,v in row.items() if k != "DIRECTION"},
                "native PCF differs from declared electrical attributes: " + name)
    missing = set(ports) - set(routed)
    require(missing == OMITTED_RGB565 and set(routed) <= set(ports), "unexpected missing/extra routed port")
    source = re.sub(r"\s+", "", clean_verilog(capture))
    require("wire[15:0]pixel565={pix_rgb[23:19],pix_rgb[15:10],pix_rgb[7:3]};" in source,
            "expected RGB565 bit selection changed")
    require(".pix_in_rgb({r_in,g_in,b_in})" in re.sub(r"\s+", "", clean_verilog(top)),
            "top RGB byte ordering changed")
    banks = defaultdict(list)
    for name, row in declared.items():
        pad = row["LOC"]
        require(pad in pads, "declared package pad missing from routed table")
        native = pads[pad]
        if name in missing:
            require(not native["Port"], "optimized RGB input pad reused by another port")
        else:
            require(routed[name]["Pad"] == pad and routed[name]["Direction"] == ports[name],
                    "routed location or direction differs: " + name)
        banks[native["Bank"]].append(name)
    bank_summary = {}
    for bank, names in sorted(banks.items()):
        volts = {declared[n]["VCCIO"] for n in names}
        require(len(volts) == 1, "mixed declared VCCIO in " + bank)
        bank_summary[bank] = {"DeclaredPorts":len(names), "RoutedPorts":sum(n in routed for n in names),
                              "DeclaredVCCIO":next(iter(volts)),
                              "Standards":dict(Counter(declared[n]["STANDARD"] for n in names))}
    differential = []
    for positive, negative in DIFFERENTIAL_PAIRS:
        p, n = routed[positive], routed[negative]
        require(p["Bank"] == n["Bank"] and p["Function"].replace("P_", "N_").replace("P", "N") == n["Function"],
                "differential P/N pads do not form a native pair")
        differential.append({"PositivePort":positive, "NegativePort":negative,
                             "PositivePad":p["Pad"], "NegativePad":n["Pad"], "Bank":p["Bank"]})
    deltas, compared = [], []
    for name, row in declared.items():
        other = ALIASES.get(name, name)
        if other in official:
            require(all(row[key] == official[other].get(key) for key in KEYS),
                    "location/voltage/standard/direction differs from HDMI reference: " + name)
            compared.append(name)
            for attr in sorted(set(row) | set(official[other])):
                if row.get(attr) != official[other].get(attr):
                    deltas.append({"Port":name,"ReferencePort":other,"Attribute":attr,
                                   "Reference":official[other].get(attr),"Current":row.get(attr)})
        else:
            require(name in {f"led[{i}]" for i in range(4,8)} and legacy_leds.get(name) == row["LOC"],
                    "port lacks an explicit reference mapping: " + name)
    require(len(compared) == 138, "expected138 official reference mappings")
    all_ddr = [name for name in declared if name.startswith("mem_") or name in ("clk_p", "clk_n")]
    require(len(all_ddr) == 73 and all(declared[n] == official[n] for n in all_ddr),
            "DDR physical attributes differ from official reference")
    return {"Schema":"board1080-pin-contract-v1", "DeclarationAndSourceBuildMappingPassed":True,
            "TopPortCount":len(ports),"ExplicitPackagePins":len(generated),"AutoAssignedPCFPins":0,
            "RoutedPortCount":len(routed),"OptimizedRGB565Inputs":sorted(missing),
            "Directions":dict(Counter(ports.values())),"Banks":bank_summary,
            "DifferentialPairs":differential,"OfficialReferenceMappedPorts":len(compared),
            "AdditionalLegacyLEDMapPorts":4,"DDRExactReferenceAttributePorts":len(all_ddr),
            "ReferenceElectricalAttributeDifferences":deltas,
            "ReferenceElectricalSettingsIdentical":not deltas,
            "DeclaredPinInventory":[{"Port":n,**declared[n],"Routed":n in routed,
               "Bank":pads[declared[n]["LOC"]]["Bank"],"NativeFunction":pads[declared[n]["LOC"]]["Function"]} for n in sorted(ports)],
            "FinalRepairedADFPinExportVerified":False,"ActualBoardRevisionVerified":False,
            "MeasuredBankVoltagesVerified":False,"ExternalIOTimingAccepted":False,
            "HardwareAccessed":False,"HardwareReleaseAllowed":False,
            "Limitations":["PCF and routed pads are from the fresh source-build before the targeted repair; final ADF pin export is separate.",
              "Official HDMI demo and legacy LED declarations are references, not proof of actual board revision or supply rails.",
              "Drive/slew/pull attribute deltas are reported without approving their electrical effects.",
              "This checks pad declarations and mapping, not HDMI AC timing, PCB skew, power integrity or hardware operation."]}


def audit_files(project=PROJECT, *, pcf=None, prt=None):
    project = Path(project).resolve()
    paths = {"top":project/"board/board1080_rowpipe_top.v",
             "fdc":project/"board/board1080-cdc-reset-diagnostic.fdc",
             "pcf":Path(pcf) if pcf else project/"build/board1080-timing/fresh-1029-b/device_map/board1080_top.pcf",
             "prt":Path(prt) if prt else project/"build/board1080-timing/fresh-1029-b/place_route/board1080_top_prr_route_optimize.prt",
             "reference":project/"platform/video_base/HDMI_IN_DDR3_HDMI_OUT_top.fdc",
             "legacy_leds":project/"board/bringup-pins.json",
             "capture":project/"rtl/experimental/hdmi1080_capture_cdc.v"}
    before = {str(path.resolve()):sha(path) for path in paths.values()}
    texts = {key:path.read_text(encoding="utf-8-sig") for key,path in paths.items()}
    texts["legacy_leds"] = json.loads(texts["legacy_leds"])
    result = audit_texts(**texts)
    receipt_path = project/"results/board1080-fresh-rebuild-20261029.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
    require(receipt.get("Schema") == "board1080-fresh-source-rebuild-v1" and
            receipt.get("ProcessSucceeded") is True and receipt["SourceBinding"]["InputDrift"] == [],
            "fresh source-build receipt is missing or failed")
    require(sha(paths["prt"]) == SOURCE_PRT_SHA256, "routed pad table is not the recorded fresh profile")
    require(receipt["EvidenceSHA256"].get("distortion/build/board1080-timing/fresh-1029-b/place_route/board1080_top_prr_route_optimize.prt") == SOURCE_PRT_SHA256,
            "routed pad hash lacks fresh source-build binding")
    for key in ("top", "fdc", "capture"):
        name = paths[key].relative_to(project.parent).as_posix()
        require(receipt["SourceBinding"]["OriginalAndCompiledSHA256"].get(name) == sha(paths[key]),
                "source/constraint differs from recorded build: " + name)
    adf = project.parent/receipt["FinalRoutedADF"]["Path"]
    require(receipt["FinalRoutedADF"]["SHA256"] == SOURCE_ADF_SHA256 and sha(adf) == SOURCE_ADF_SHA256,
            "source-build ADF identity differs")
    before.update({str(receipt_path):sha(receipt_path),str(adf):sha(adf)})
    require(all(sha(path) == digest for path,digest in before.items()), "input changed during pin audit")
    result.update(InputSHA256=before, AuditToolSHA256=sha(__file__),
                  SourceBuildReceiptBound=True, SourceADFSHA256=SOURCE_ADF_SHA256,
                  SourceNativeRoutedPadSHA256=SOURCE_PRT_SHA256)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pcf",type=Path)
    parser.add_argument("--prt",type=Path)
    parser.add_argument("--output",type=Path,required=True)
    args = parser.parse_args(argv)
    result = audit_files(pcf=args.pcf,prt=args.prt)
    with args.output.open("x",encoding="utf-8",newline="\n") as stream:
        json.dump(result,stream,indent=2,ensure_ascii=False);stream.write("\n")
    print(json.dumps({k:result[k] for k in ("DeclarationAndSourceBuildMappingPassed","TopPortCount","RoutedPortCount","HardwareReleaseAllowed")}))


if __name__ == "__main__":
    main()
