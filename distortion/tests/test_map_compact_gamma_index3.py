"""Exact scratch derivation/default plan only. Never execute PDS."""
from pathlib import Path
import re,sys,pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import map_compact_gamma_index3 as probe


def test_derive_is_exact_and_stops_at_map(tmp_path):
    for kind,index in (("compact",3),("compact",5),("parity",3)):
        top,top_bytes,frame,frame_bytes,tcl=probe.derive(tmp_path,kind,index)
        original=(probe.ROOT/f"board/{probe.TARGET}.v").read_bytes()
        original_frame=(probe.ROOT/probe.core.prepared.FRAME).read_bytes()
        assert top_bytes==original and b"defparam" not in top_bytes
        if index==3:
            assert frame_bytes.count(b".INDEX_BITS(3)")==1
            assert frame_bytes.replace(b".INDEX_BITS(3)",b".INDEX_BITS(5)")==original_frame
            assert probe.core.prepared.FRAME not in tcl
        else:
            assert frame_bytes is None and frame==probe.ROOT/probe.core.prepared.FRAME
            assert frame.read_bytes()==original_frame
        assert str(top.as_posix()) in tcl and str(frame.as_posix()) in tcl
        if kind=="compact":
            assert probe.COMPACT in tcl and probe.core.prepared.PARITY not in tcl and probe.core.prepared.SERIAL not in tcl
        else:
            assert probe.COMPACT not in tcl and probe.core.prepared.PARITY in tcl and probe.core.prepared.SERIAL in tcl
        assert re.findall(r"(?m)^(compile|synthesize|dev_map)\b",tcl)==["compile","synthesize","dev_map"]
        assert not re.search(r"(?m)^(pnr|report_timing|gen_bit_stream|cfg_\w+)\b",tcl)
    with pytest.raises(ValueError):probe.derive(tmp_path,"arbitrary-source")
    with pytest.raises(ValueError):probe.derive(tmp_path,"compact",4)


def test_default_plan_preserves_main_and_does_not_launch(tmp_path,monkeypatch):
    monkeypatch.setattr(probe,"APPROVED",tmp_path)
    before=probe.core.prepared.verify_clone()["SourceSHA256"]
    def forbidden(*_,**__):raise AssertionError("default map plan invoked a process")
    monkeypatch.setattr(probe.subprocess,"Popen",forbidden)
    for kind,index in (("compact",3),("compact",5),("parity",3)):
        plan=probe.run_probe(tmp_path/("plan-"+kind+str(index)),cache_kind=kind,index_bits=index)
        assert plan["ExecuteMap"] is False and plan["Stage"]=="map_only" and plan["IndexBits"]==index
        assert plan["CacheKind"]==kind and plan["BitstreamGenerated"] is False and plan["FinalTimingPassed"] is False
        assert len(plan["MainSourceSHA256"])==123 and plan["ExpectedInputPins"]==130
        assert probe.sha(Path(plan["DerivedTop"]))==before[f"board/{probe.TARGET}.v"]
    assert before==probe.core.prepared.verify_clone()["SourceSHA256"]
