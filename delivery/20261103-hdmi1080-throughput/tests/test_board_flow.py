"""CPU-only PDS pin-format and timing rejection regression; no EDA/hardware."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import re

PACKAGE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PACKAGE/"tools"))
import build_board_candidate as flow


class BoardFlowTest(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory=Path(self.temporary.name)
        self.pcf=PACKAGE/"evidence/board-tools/map-reference.pcf"
        self.prt=PACKAGE/"evidence/board-tools/map-reference.prt"
        recipe=flow.read_json(flow.prep.BASE/"manifests/build-recipe.json")
        text="\n".join((flow.prep.BASE/"native"/p).read_text(encoding="utf-8-sig") for p in recipe["constraints"])
        self.expected=flow.fdc_pins(text+flow.UART)

    def test_real_map_144_accept(self):
        result=flow.native_pin_audit(self.pcf,self.prt,self.expected,mapped_only=True)
        self.assertEqual(result["pin_count"],144)
        self.assertEqual(len(result["reserved_pads"]),144)
        self.assertFalse(result["routed_port_assignment_verified"])
        self.assertEqual(self.expected["telemetry_rx"]["LOC"],"B24")
        self.assertEqual(self.expected["telemetry_tx"]["LOC"],"C24")

    def test_map_cannot_claim_routed(self):
        with self.assertRaisesRegex(ValueError,"Routed 144-pin"):
            flow.native_pin_audit(self.pcf,self.prt,self.expected)

    def reject_pcf_change(self,before,after):
        text=self.pcf.read_text(encoding="utf-8-sig")
        self.assertIn(before,text)
        changed=self.directory/"changed.pcf"
        changed.write_text(text.replace(before,after,1))
        with self.assertRaisesRegex(ValueError,"PCF electrical/location mismatch"):
            flow.native_pin_audit(changed,self.prt,self.expected,mapped_only=True)

    def test_wrong_location_reject(self):
        self.reject_pcf_change("LOC=C24","LOC=B24")

    def test_wrong_supply_reject(self):
        self.reject_pcf_change("VCCIO=3.3","VCCIO=1.8")

    def test_wrong_standard_reject(self):
        self.reject_pcf_change("IOSTANDARD=LVCMOS33","IOSTANDARD=LVCMOS18")

    def test_missing_pad_reservation_reject(self):
        changed=self.directory/"changed.prt"
        changed.write_text("\n".join(l for l in self.prt.read_text().splitlines() if not l.startswith("C24|")))
        with self.assertRaisesRegex(ValueError,"Reserved package pads"):
            flow.native_pin_audit(self.pcf,changed,self.expected,mapped_only=True)

    def routed_fixture(self):
        # This is a synthetic fixture for adapter coverage, not PNR evidence.
        by_pad={v["LOC"]:k for k,v in self.expected.items()};lines=[]
        for line in self.prt.read_text().splitlines():
            fields=line.split("|")
            if len(fields)==7 and fields[-1]=="YES":
                fields[4]=by_pad[fields[0]]
                fields[5]=self.expected[fields[4]]["DIRECTION"].lower()
            lines.append("|".join(fields))
        result=self.directory/"synthetic-routed.prt"
        result.write_text("\n".join(lines))
        return result

    def test_complete_routed_format_accept(self):
        result=flow.native_pin_audit(self.pcf,self.routed_fixture(),self.expected)
        self.assertTrue(result["routed_port_assignment_verified"])
        self.assertEqual(len(result["pins"]),144)

    def test_wrong_routed_direction_reject(self):
        changed=self.routed_fixture()
        changed.write_text(changed.read_text().replace("telemetry_tx|output|YES","telemetry_tx|input|YES"))
        with self.assertRaisesRegex(ValueError,"Routed pin assignment mismatch"):
            flow.native_pin_audit(self.pcf,changed,self.expected)

    def timing_fixture(self,negative=None,omit=None):
        text="\n".join(["| Device : PG2L100H","| Speed Grade : -6","| Package : FBG676",
                        "| Design : board1080_top","Timing analysis mode : multi corner",
                        "Clock Summary:"])+"\n"
        for name,period in flow.EXPECTED_CLOCKS.items():
            kind="Declared" if name in ("board27","input_pixel","ref_clk") else "Generated (reference)"
            text+=f" {name} {period:.4f} {{0.0000 {period/2:.4f}}} {kind} 10 0 {{source}}\n"
        text+="Clock Groups:\n"
        for corner in ("Slow","Fast"):
            for kind in ("Setup","Hold","Recovery","Removal","Minimum Pulse Width","Skew"):
                identity=(corner,kind)
                if identity==omit: continue
                text+=kind+" Summary("+corner+" Corner):\n"
                text+=("board27" if kind=="Minimum Pulse Width" else "board27 board27")
                text+=" -0.001 -0.001 1 10\n" if identity==negative else " 0.100 0.000 0 10\n"
        output=self.directory/"synthetic-timing.rtr";output.write_text(text)
        return output

    def test_all_twelve_timing_kinds_accept(self):
        report=flow.parse_timing(self.timing_fixture())
        self.assertTrue(report["all_native_checks_met"])
        self.assertEqual(len(report["summaries"]),12)

    def test_each_negative_kind_preserved(self):
        for corner in ("Slow","Fast"):
            for kind in ("Setup","Hold","Recovery","Removal","Minimum Pulse Width","Skew"):
                with self.subTest(corner=corner,kind=kind):
                    report=flow.parse_timing(self.timing_fixture(negative=(corner,kind)))
                    self.assertFalse(report["all_native_checks_met"])
                    self.assertEqual(sum(r["failing_checks"] for r in report["summaries"].values()),1)

    def test_incomplete_corner_reject(self):
        with self.assertRaisesRegex(ValueError,"All twelve nonempty"):
            flow.parse_timing(self.timing_fixture(omit=("Fast","Recovery")))

    def test_wrong_device_reject(self):
        path=self.timing_fixture();path.write_text(path.read_text().replace("PG2L100H","PG2L200H"))
        with self.assertRaisesRegex(ValueError,"STA device/header mismatch"):
            flow.parse_timing(path)

    def test_wrong_clock_period_reject(self):
        path=self.timing_fixture();path.write_text(path.read_text().replace("ddrphy_sysclk 8.0000","ddrphy_sysclk 80.0000"))
        with self.assertRaisesRegex(ValueError,"Frozen clock period mismatch"):
            flow.parse_timing(path)

    def test_missing_clock_reject(self):
        path=self.timing_fixture();path.write_text("\n".join(l for l in path.read_text().splitlines() if not l.startswith(" cfg_clk ")))
        with self.assertRaisesRegex(ValueError,"Expected all eleven"):
            flow.parse_timing(path)

    def test_zero_endpoint_coverage_reject(self):
        path=self.timing_fixture();path.write_text(path.read_text().replace("0.100 0.000 0 10","0.100 0.000 0 0"))
        with self.assertRaisesRegex(ValueError,"positive endpoint coverage"):
            flow.parse_timing(path)

    def test_all_postmap_stages_import_fdc_and_pcf(self):
        with patch.object(flow,"receipt",return_value={"artifacts":{"pcf":{"path":str(self.pcf)}}}):
            for stage in ("route","sta","bitstream"):
                code=flow.stage_tcl(self.directory,stage,self.directory,self.directory/"input.adf")
                self.assertIn("board1080-diagnostic.fdc",code)
                self.assertIn("uart-pins.fdc",code)
                self.assertIn("map-reference.pcf} -pnr_set pnr_1",code)
                self.assertLess(code.index("add_constraint"),code.index({"route":"list place ","sta":"list report_timing ","bitstream":"list gen_bit_stream "}[stage]))

    def electrical_fixture(self):
        ports={}
        for line in self.pcf.read_text().splitlines():
            m=re.fullmatch(r"def_port \{([^{}]+)\} (.+)",line)
            if m: ports[m[1]]=dict(re.findall(r"(\w+)=([^\s]+)",m[2]))
        columns=["PORT","DIRECTION","CONSTRAINT"]+sorted({key for attrs in ports.values() for key in attrs})
        lines=["| "+" | ".join(columns)+" |"]
        for port,attrs in ports.items():
            row={**attrs,"PORT":port,"DIRECTION":self.expected[port]["DIRECTION"].lower(),"CONSTRAINT":"YES"}
            lines.append("| "+" | ".join(row.get(key,"NA") for key in columns)+" |")
        path=self.directory/"synthetic-electrical.rur";path.write_text("\n".join(lines))
        return path

    def test_final_electrical_all_attributes_accept(self):
        self.assertTrue(flow.routed_electrical_audit(self.pcf,self.electrical_fixture(),self.expected)["passed"])

    def test_final_slew_or_pullup_change_reject(self):
        for before,after in (("FAST","SLOW"),("PULLUP","NONE")):
            path=self.electrical_fixture();path.write_text(path.read_text().replace(before,after,1))
            with self.assertRaisesRegex(ValueError,"Routed electrical mismatch"):
                flow.routed_electrical_audit(self.pcf,path,self.expected)

    def test_native_twelve_summary_format(self):
        result=flow.parse_timing(PACKAGE/"evidence/board-tools/timing-summary-reference.rtr")
        self.assertEqual(len(result["summaries"]),12)
        self.assertEqual(len(result["all_rows"]["slow_skew"]),4)
        self.assertEqual(len(result["all_rows"]["slow_removal"]),13)
        self.assertEqual(result["summaries"]["slow_setup"]["failing_checks"],155)
        self.assertFalse(result["all_native_checks_met"])

    def test_native_final_route_electrical(self):
        result=flow.routed_electrical_audit(self.pcf,PACKAGE/"evidence/board-tools/route-reference.rur",self.expected)
        self.assertEqual(len(result["ports"]),144)

    def test_atomic_receipt_write_retains_previous_on_full_disk(self):
        path=self.directory/"receipt.json";path.write_text('{"previous":true}')
        with patch.object(Path,"write_text",side_effect=OSError(28,"No space left on device")):
            with self.assertRaises(OSError): flow.save(path,{"next":True})
        self.assertEqual(path.read_text(),'{"previous":true}')

    def test_native_timing_database_binding(self):
        database=self.directory/"routed.adf";database.write_bytes(b"database")
        report=self.directory/"input-binding.rtr"
        report.write_text("| Tcl Command : report_timing -input_db_file {"+database.as_posix()+"} -delay_type min_max\n")
        self.assertTrue(flow.timing_input_audit(report,database)["passed"])
        with self.assertRaisesRegex(ValueError,"native input DB differs"):
            flow.timing_input_audit(report,self.directory/"other.adf")

    def test_native_action_timing_header(self):
        database=self.directory/"routed.adf";database.write_bytes(b"database")
        report=self.directory/"action-binding.rtr"
        header="| Tcl Command : set_option -options { input_db_file {"+database.as_posix()+"} nworst {4} max_path {50} report_io_datasheet {true}} [get_actions report_timing -of_objects [get_tasks pnr_1]]\n"
        report.write_text(header)
        self.assertTrue(flow.timing_input_audit(report,database)["passed"])
        with self.assertRaisesRegex(ValueError,"native input DB differs"):
            flow.timing_input_audit(report,self.directory/"other.adf")
        report.write_text(header.replace("get_actions report_timing","get_actions route"))
        with self.assertRaisesRegex(ValueError,"Unrecognized STA native action"):
            flow.timing_input_audit(report,database)

    def test_bit_gate_reparses_report_despite_old_success_flag(self):
        db=self.directory/"route.adf";db.write_bytes(b"route")
        mapdb=self.directory/"map.adf";mapdb.write_bytes(b"map")
        report=self.timing_fixture(negative=("Slow","Setup"))
        report.write_text("| Tcl Command : report_timing -input_db_file {"+db.as_posix()+"}\n"+report.read_text())
        mapped={"artifacts":{"map_db":flow.ref(mapdb),"pcf":flow.ref(self.pcf),"pin_report":flow.ref(self.prt)}}
        routed={"input_db":flow.ref(mapdb),"stage_directory":str(self.directory),"explicit_constraints":[],
            "artifacts":{"route_db":flow.ref(db),"pcf":flow.ref(self.pcf),"pin_report":flow.ref(self.routed_fixture()),
                         "electrical_report":flow.ref(PACKAGE/"evidence/board-tools/route-reference.rur")}}
        timed={"input_db":flow.ref(db),"stage_directory":str(self.directory),"explicit_constraints":[],
            "timing":{"all_native_checks_met":True},"artifacts":{"timing":flow.ref(report)}}
        records={"map":mapped,"route":routed,"sta":timed}
        for stage,record in records.items(): flow.save(self.directory/(stage+"-result.json"),record)
        with patch.object(flow,"receipt",side_effect=lambda work,stage:records[stage]),patch.object(flow,"verify_device"),patch.object(flow,"verify_constraint_import"):
            result=flow.fresh_bit_audit(self.directory,{"expected_pins":self.expected})
        self.assertFalse(result["timing"]["all_native_checks_met"])


if __name__=="__main__":
    unittest.main()
