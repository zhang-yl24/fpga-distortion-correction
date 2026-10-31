"""Recheck completed exact-ADF export; no EDA or hardware."""
from run_review import *

def attrs(raw):
    result = {}
    for match in re.finditer(r'\(\*\s*([^*]*)\*\)\s*(input|output|inout)\s+(\w+)\s*;', raw):
        properties = dict(re.findall(r'(PAP_\w+)="([^\"]*)"', match[1]))
        if "PAP_IO_LOC" in properties:
            require(match[3] not in result, "duplicate port attributes")
            result[match[3]] = dict(Direction=match[2], Attributes=properties)
    return result

def verify():
    execution = json.loads((WORK / "execution.json").read_text(encoding="utf-8"))
    require(execution["ExportExecutionAccepted"] and execution["ReturnCode"] == 0, "export execution failed")
    for name, wanted in execution["OutputSHA256"].items():
        require(sha(WORK / name) == wanted, "export output changed: " + name)
    plan = json.loads((SOURCE / "bitstream-plan.json").read_text(encoding="utf-8"))
    adf = SOURCE / "audited-final.adf"
    netlist = WORK / "generate_netlist/hdmi_uart_input_diag_sim.v"
    raw, old = netlist.read_text(encoding="utf-8"), (WORK / "baseline-sim.v").read_text(encoding="utf-8")
    cells, ports, drivers, libraries = parse(raw)
    old_cells, old_ports, old_drivers, old_libraries = parse(old)
    placement, old_placement = sites(raw), sites(old)
    attributes, old_attributes = attrs(raw), attrs(old)
    require(cells == old_cells and ports == old_ports and drivers == old_drivers, "functional graph changed")
    require(placement == old_placement, "primitive placement changed")
    require(attributes == old_attributes, "scalar IO attributes changed")
    pin_by_site, expected, directions = {}, {}, {}
    for line in (WORK / "baseline-pins.prt").read_text(encoding="utf-8").splitlines():
        fields = line.split("|")
        if len(fields) >= 7:
            require(fields[1] not in pin_by_site, "duplicate package site")
            pin_by_site[fields[1]] = fields[0]
            if fields[4]:
                require(fields[6] == "YES", "inactive port")
                expected[fields[4]], directions[fields[4]] = fields[0], fields[5]
    require(expected == plan["SourcePins"] and len(expected) == 46, "pin closure differs")
    evidence, actual, actual_dirs = [], {}, {}
    for name, wanted in expected.items():
        if name in attributes:
            pin, direction = attributes[name]["Attributes"]["PAP_IO_LOC"], attributes[name]["Direction"]
            source = dict(Kind="native_scalar_port_attributes", **attributes[name])
        else:
            matches = [(key,cell) for key,cell in cells.items() if cell["Type"] == "V_OBUFT" and native.scalar(cell["Ports"]["O"]) == name]
            require(len(matches) == 1, "unique output primitive required: " + name)
            key, cell = matches[0]
            require(key in placement and placement[key] in pin_by_site, "output site missing")
            pin, direction = pin_by_site[placement[key]], "output"
            source = dict(Kind="native_output_primitive_site_to_package_pin", Instance=key, Site=placement[key], Parameters=cell["Parameters"])
        require(pin == wanted and direction == directions[name], "port mapping differs: " + name)
        actual[name], actual_dirs[name] = pin, direction
        evidence.append(dict(Port=name, Pin=pin, Direction=direction, Evidence=source))
    require(len(set(actual.values())) == 46, "duplicate package pin")
    prior = json.loads((WORK / "baseline-connectivity.json").read_text(encoding="utf-8"))
    for name,register in prior["registers"].items():
        key = register["native_instance"]
        require(cells[key]["Type"] == register["primitive"] and cells[key]["Ports"] == register["ports"] and cells[key]["Parameters"] == register["parameters"], "synchronizer changed: " + name)
        require(placement[key] == register["location"]["site"], "synchronizer moved")
    links = []
    for link in prior["stage_links"]:
        akey, bkey = prior["registers"][link["first"]]["native_instance"], prior["registers"][link["second"]]["native_instance"]
        a, b = cells[akey], cells[bkey]
        q, d = native.scalar(a["Ports"]["Q"]), native.scalar(b["Ports"]["D"])
        criteria = dict(DirectQToD=q == d, SoleDriver=drivers[d] == [(akey,"Q")],
            SameClock=native.scalar(a["Ports"]["CK"]) == native.scalar(b["Ports"]["CK"]),
            FirstEnabled=native.constant(native.scalar(a["Ports"]["CE"])) == 1,
            SecondEnabled=native.constant(native.scalar(b["Ports"]["CE"])) == 1, SameSite=placement[akey] == placement[bkey])
        require(all(criteria.values()), "stage connection changed")
        links.append(dict(First=link["first"], Second=link["second"], Criteria=criteria))
    require(len(prior["registers"]) == 161 and len(links) == 81, "sync inventory differs")
    bit.verify_inputs(ROOT, SOURCE, plan)
    require(sha(adf) == bit.ADF_SHA256 and sha(WORK / "input.adf") == bit.ADF_SHA256, "ADF changed")
    result = dict(Schema="hdmi-exact-final-netlist-review-v1", CreatedUTC=datetime.now(timezone.utc).isoformat(), AuditPassed=True,
        SourceADFSHA256=bit.ADF_SHA256, NativeNetlistSHA256=sha(netlist), BaselineNetlistSHA256=sha(WORK / "baseline-sim.v"),
        EntireParsedFunctionalGraphUnchanged=True, EntirePrimitivePlacementUnchanged=True, ScalarIOAttributesUnchanged=True,
        ParsedCellCount=len(cells), ActualPinCount=46, All46PinsAndDirectionsMatch=True, Pins=actual, Directions=actual_dirs, PinEvidence=evidence,
        VerifiedSynchronizerFFCount=161, VerifiedStageLinkCount=81, SameSiteStageLinkCount=81, StageLinks=links,
        EvidenceSHA256={str(p):sha(p) for p in [WORK / "execution.json",WORK / "export-plan.json",netlist,WORK / "baseline-pins.prt",WORK / "baseline-connectivity.json",WORK / "input.adf"]},
        PrimitiveLibrarySHA256=libraries, HardwareAccessed=False, HardwareReleaseAllowed=False, PhysicalCDCSignoff=False,
        Limits="Exact ADF functional connectivity, placement and IO mapping only. Output primitive sites map via the unchanged device/package pin report. No external AC, MTBF, board power or real input/pixel acceptance.")
    save("review.json", result)
    print(json.dumps({key:result[key] for key in ["AuditPassed","SourceADFSHA256","NativeNetlistSHA256","ParsedCellCount","ActualPinCount","VerifiedSynchronizerFFCount","VerifiedStageLinkCount"]}))


if __name__ == "__main__":
    verify()
