"""Portable pin-contract regressions; generated text fixtures do not invoke PDS."""
from pathlib import Path
import copy
import json
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import audit_board1080_pin_contract as tool


@pytest.fixture
def data():
    root=Path(__file__).resolve().parents[1]
    result={"top":(root/"board/board1080_rowpipe_top.v").read_text(encoding="utf-8"),
            "fdc":(root/"board/board1080-cdc-reset-diagnostic.fdc").read_text(encoding="utf-8"),
            "reference":(root/"platform/video_base/HDMI_IN_DDR3_HDMI_OUT_top.fdc").read_text(encoding="utf-8"),
            "legacy_leds":json.loads((root/"board/bringup-pins.json").read_text()),
            "capture":(root/"rtl/experimental/hdmi1080_capture_cdc.v").read_text()}
    pins=tool.fdc_pins(result["fdc"])
    pcf,prt=[],[]
    functions={}
    for i,(positive,negative) in enumerate(tool.DIFFERENTIAL_PAIRS):
        functions.update({positive:f"DIFFIO_R4_G{i}_00P_DQS",negative:f"DIFFIO_R4_G{i}_00N_DQS"})
    for index,(name,row) in enumerate(pins.items()):
        attrs={"IOSTANDARD" if k=="STANDARD" else k:v for k,v in row.items() if k!="DIRECTION"}
        pcf.append("def_port {"+name+"} "+" ".join(k+"="+v for k,v in attrs.items()))
        occupied=name not in tool.OMITTED_RGB565
        bank="BANKL3" if row["VCCIO"]=="3.3" else "BANKR4"
        prt.append("|".join([row["LOC"],f"SITE_{index}",bank,functions.get(name,"SIO_00"),
                             name if occupied else "",row["DIRECTION"].lower() if occupied else "","YES" if occupied else ""]))
    result.update(pcf="\n".join(pcf),prt="\n".join(prt))
    return result


def test_all_declared_ports_and_only_explained_rgb565_omissions(data):
    result=tool.audit_texts(**data)
    assert result["DeclarationAndSourceBuildMappingPassed"]
    assert result["TopPortCount"]==result["ExplicitPackagePins"]==142
    assert result["AutoAssignedPCFPins"]==0 and result["RoutedPortCount"]==134
    assert set(result["OptimizedRGB565Inputs"])==tool.OMITTED_RGB565
    assert result["DDRExactReferenceAttributePorts"]==73
    assert result["OfficialReferenceMappedPorts"]==138
    assert len(result["DifferentialPairs"])==6
    assert not result["HardwareReleaseAllowed"]
    assert not result["FinalRepairedADFPinExportVerified"]
    assert not result["MeasuredBankVoltagesVerified"]


def test_electrical_differences_are_reported_not_called_identical(data):
    result=tool.audit_texts(**data)
    deltas=result["ReferenceElectricalAttributeDifferences"]
    assert {"Port":"b_out[0]","ReferencePort":"b_out[0]","Attribute":"SLEW",
            "Reference":"SLOW","Current":"FAST"} in deltas
    assert {"Port":"hd_sda","ReferencePort":"hd_sda","Attribute":"DRIVE",
            "Reference":"8","Current":"4"} in deltas
    assert not result["ReferenceElectricalSettingsIdentical"]


@pytest.mark.parametrize("mutation,reason",[
    ("top_missing","same142"),("top_direction","direction mismatch"),
    ("pcf_missing","same142"),("pcf_auto","AUTO"),("pcf_duplicate","duplicate native PCF"),
    ("pcf_attribute","electrical attributes"),("fdc_duplicate","duplicate pin attribute"),
    ("fdc_pad_conflict","duplicate, AUTO"),("routed_extra_missing","missing/extra routed"),
    ("routed_pad","location or direction"),("routed_direction","location or direction"),
    ("unoccupied_reused","missing/extra routed"),("rgb_selection","RGB565 bit selection"),
    ("rgb_order","RGB byte ordering"),("reference_voltage","differs from HDMI reference"),
    ("legacy_led","explicit reference mapping"),("diffpair","differential P/N"),
    ("bank_mixed","mixed declared VCCIO")])
def test_invalid_or_unexplained_pin_evidence_rejected(data,mutation,reason):
    data=copy.deepcopy(data)
    if mutation=="top_missing":data["top"]=data["top"].replace("clk_27m,clk_p","clk_p",1)
    elif mutation=="top_direction":data["top"]=data["top"].replace("input clk_27m","output clk_27m",1)
    elif mutation=="pcf_missing":data["pcf"]="\n".join(l for l in data["pcf"].splitlines() if not l.startswith("def_port {clk_27m}"))
    elif mutation=="pcf_auto":data["pcf"]=data["pcf"].replace("LOC=D18","LOC=AUTO",1)
    elif mutation=="pcf_duplicate":data["pcf"]+="\n"+data["pcf"].splitlines()[0]
    elif mutation=="pcf_attribute":data["pcf"]=data["pcf"].replace("LOC=D18 VCCIO=3.3","LOC=D18 VCCIO=2.5",1)
    elif mutation=="fdc_duplicate":data["fdc"]+="\ndefine_attribute {p:clk_27m} {PAP_IO_LOC} {D18}\n"
    elif mutation=="fdc_pad_conflict":data["fdc"]=data["fdc"].replace("{PAP_IO_LOC} {D18}","{PAP_IO_LOC} {C22}",1)
    elif mutation=="routed_extra_missing":data["prt"]=data["prt"].replace("|clk_27m|input|YES","|||",1)
    elif mutation=="routed_pad":
        a=data["prt"].splitlines();i=next(i for i,l in enumerate(a) if "|clk_27m|" in l);j=next(i for i,l in enumerate(a) if "|reset_n|" in l)
        a[i]=a[i].replace("D18|","C22|",1);a[j]=a[j].replace("C22|","D18|",1);data["prt"]="\n".join(a)
    elif mutation=="routed_direction":data["prt"]=data["prt"].replace("|clk_27m|input|YES","|clk_27m|output|YES",1)
    elif mutation=="unoccupied_reused":data["prt"]=data["prt"].replace("|||","|unknown|input|YES",1)
    elif mutation=="rgb_selection":data["capture"]=data["capture"].replace("pix_rgb[23:19]","pix_rgb[23:18]")
    elif mutation=="rgb_order":data["top"]=data["top"].replace(".pix_in_rgb({r_in,g_in,b_in})",".pix_in_rgb({b_in,g_in,r_in})")
    elif mutation=="reference_voltage":data["reference"]=data["reference"].replace("{p:mem_dq[0]} {PAP_IO_VCCIO} {1.5}","{p:mem_dq[0]} {PAP_IO_VCCIO} {3.3}")
    elif mutation=="legacy_led":data["legacy_leds"]["led[4]"]="A1"
    elif mutation=="diffpair":data["prt"]=data["prt"].replace("DIFFIO_R4_G0_00N_DQS","DIFFIO_R4_G9_00N_DQS")
    elif mutation=="bank_mixed":data["prt"]=data["prt"].replace("BANKR4","BANKL3",1)
    with pytest.raises(ValueError,match=reason):tool.audit_texts(**data)


def test_strict_port_parser_rejects_parameterized_or_ambiguous_interface():
    with pytest.raises(ValueError,match="one nonparameterized"):
        tool.top_ports("module board1080_top #(parameter W=3)(input [W:0] x); endmodule")
    with pytest.raises(ValueError,match="duplicate top port"):
        tool.top_ports("module board1080_top(input a,a); endmodule")


def test_native_duplicate_attributes_and_rows_reject(data):
    with pytest.raises(ValueError,match="duplicate native PCF attribute"):
        tool.pcf_pins("def_port {x} LOC=A1 LOC=B1")
    with pytest.raises(ValueError,match="duplicate routed package pad"):
        tool.routed_pads(data["prt"]+"\n"+data["prt"].splitlines()[0])


def test_real_local_native_pin_files_when_available():
    root=Path(__file__).resolve().parents[1]
    if not (root/"build/board1080-timing/fresh-1029-b/device_map/board1080_top.pcf").is_file():
        pytest.skip("local native mapping outputs are not distributed")
    result=tool.audit_files(root)
    assert result["RoutedPortCount"]==134
    assert result["Banks"]["BANKL4"]["RoutedPorts"]==23
    assert result["Banks"]["BANKR4"]["DeclaredVCCIO"]=="1.5"
