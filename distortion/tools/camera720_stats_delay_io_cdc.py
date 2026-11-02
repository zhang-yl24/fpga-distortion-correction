"""Explicit new-target facade over unchanged pure statistics IO algorithms."""
import re

import camera720_stats_io_cdc as base

TARGET='camera720_calibrated_stats_delay_top'
SCHEMA='camera720-calibrated-stats-delay-io-structure-v1'
require=base.require
structure,native_io,io,cdc,grouped,video=base.structure,base.native_io,base.io,base.cdc,base.grouped,base.video
UART,PREFIX,CORE,UART_ATTRIBUTES=base.UART,base.PREFIX,base.CORE,base.UART_ATTRIBUTES


def normalize(text):
    clean=io.pin_parser.clean_verilog(text)
    require(re.findall(r'\bmodule\s+(\w+)',clean)==[TARGET],'one exact delayed statistics module required')
    value,count=re.subn(r'(\bmodule\s+)'+TARGET+r'\b',r'\g<1>'+base.TARGET,text)
    require(count==1,'ambiguous delayed statistics module token')
    return value


def source_inventory(top,fdc):
    value=base.source_inventory(normalize(top),fdc)
    return {**value,'Target':TARGET,'Schema':SCHEMA}


def graph(netlist):return base.graph(normalize(netlist))


def pin_audit(top,fdc,pcf,prt,netlist,official,camref,campins):
    value=base.pin_audit(normalize(top),fdc,pcf,prt,normalize(netlist),official,camref,campins)
    return {**value,'Target':TARGET}


cdc_inputs=base.cdc_inputs
uart_launches=base.uart_launches
cdc_query_bodies=base.cdc_query_bodies


def collect(queries,reports):
    # Report bytes stay unchanged; strict new design header precedes the same
    # record parser. The original target's collector remains frozen.
    from collections import Counter
    from pathlib import Path
    lookup={cdc.timing.identity(q):q for q in queries}
    require(len(lookup)==len(queries),'duplicate delayed candidate query')
    pairs={(q['Source'],q['Endpoint']) for q in queries};rows=[];violations=[];other=Counter();seen=set()
    for report in sorted({Path(p).resolve() for p in reports}):
        with report.open(encoding='gb18030') as stream:head=''.join(next(stream,'') for _ in range(18))
        require('2023.2-SP3 <build 154097>' in head and re.search(r'^\| Design\s*:\s*'+TARGET+r'\s*$',head,re.M),
                'delayed statistics report target/version differs')
        for lines,line in cdc.timing.native.blocks(report):
            text=''.join(lines);source=cdc.timing.field(r'^Startpoint\s*:\s*(.+?)\s*$',text,'source')
            endpoint=cdc.timing.field(r'^Endpoint\s*:\s*(.+?)\s*$',text,'endpoint')
            if (source,endpoint) not in pairs:continue
            try:
                key=(source,cdc.timing.launch_row(text)['LaunchOutput'],endpoint)
                if key not in lookup:other[key]+=1;continue
                value=cdc.timing.parse_record(lines,report,line,lookup[key])
            except ValueError as error:
                violations.append({'Source':source,'Endpoint':endpoint,'Report':str(report),'ReportLine':line,'Error':str(error)});continue
            if value['PathSHA256'] not in seen:seen.add(value['PathSHA256']);rows.append(value)
    return rows,violations,[dict(zip(cdc.timing.IDENTITY,k),ObservedVariants=n) for k,n in sorted(other.items())]
