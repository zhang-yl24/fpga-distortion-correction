"""CPU-only, unapplied inventory of this pixel candidate's own native graph.

Unknown clocks, primitives, endpoints or crossing roles are blocking findings.
Typed RAM/DSP/PHY boundaries are retained explicitly, never called primary
inputs or ordinary flip-flops. This tool cannot modify constraints or release
a build, bitstream or hardware. Native timing acceptance is a separate task.
"""
import argparse
import ast
from collections import Counter,defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import itertools

import hdmi_camera_pixel_build as build
import hdmi_camera_pixel_native as native
import hdmi_camera_raw_audit as raw
import hdmi_camera_raw_reset_audit as reset_boolean
import camera720_stats_native_mux as mux
import audit_camera720_io_cdc as syntax
import audit_board1080_pin_contract as pin_parser
import camera720_cdc_clm as clm
import camera720_calibrated_cdc as calibrated
import audit_camera720_monitor as monitor
import numpy
import cv2

SELF=Path(__file__).resolve()
TARGET=build.TARGET
SCHEMA='hdmi-camera-pixel-unapplied-audit-v1'
MODEL_ROOT=Path('D:/pango/PDS_2023.2/arch/vendor/pango/verilog/bsim')
require,sha,read,write=build.require,build.sha,build.read,build.write
canon=raw.canon
CAP='system/input_link/input_dma/capture/'
DMA='system/input_link/input_dma/'
OUT='system/output_video/'
PADS=tuple(['vs_in','hs_in','de_in']+[f'{c}_in[{i}]'for c in 'rgb'for i in range(8)])
UNUSED_RGB={f'{c}_in[{i}]'for c,bits in [('r',range(3)),('g',range(2)),('b',range(3))]for i in bits}
MODEL_SHA={
 'V_FFSYN':'ae4094a9a478a8ae9e5c67a0fcf982ff1e61a6e1e66588d849dd815d713c1f8c',
 'V_FFASYN':'e2fcf0de9085fd056c4daa14b2f73bd9235cdb52c90e68a2b58114024e048b24',
 'V_BUF':'774fb1a08820223eef6c66217e510d3a5eb328edebffb488a25467fe3e623836',
 'V_INV':'b1242601ab1cc80fbc152a149eaf3d73b140e541392d8af727260cadc7b378ef',
 'V_MUX2':'77540b86085dc742e5a5102578cb3f0a8753989b3b800d6a75f23e6d46515b95',
 'V_LUT6CARRY':'aa7ca57e8ce35845b0d61b02358d4a546facc52be65ec1ca5e68fe37a8bdcf98',
 'V_GRS':'42302a081bc28e3d89b99997abd11c3411b2d5afd71aa48d2444bc779c384762',
 'V_OBUFT':'cfc024e819351fe3dd04cabd22f2860c5eac6d528f413c78ab56b1b0f2dd8017',
 'V_OBUFTDS':'014f6191a60dbf086f0c2bb90687ff09067d0e21c335652fa42bd8d59e0c7b23',
 'V_IBUF':'18814ef6d6f140b763c88871640498cacfaa420f4e5038b4fc751beedf69d4f4',
 'V_IBUFDS':'590b7fbfaae0a506671f22894fcf4aa32cabc2bd44592027fd4190442e2f973a',
 'V_USCM':'3f35757740a6498560e3531ae7bfe44147b05016d6a80e504fc3f27934f486fc',
 'V_GPLL':'1cbab1c034d8129f9164edeff911deb36a0201fb67cd8f336512e4ddc21d9ed0',
 'V_PPLL':'8cb6eb356fd9ba0691aa03e83c81cdb35c806cc7a6d3081726d4454f624b7e1c',
 'V_APM_E2':'b2403492e98454365e6cfaed681cbef2902cbe8a378cb693a0c3cfbbee35e48c',
 'V_DRM36K_E1':'224ad428a209ba704b58c24a505b9290648a95e4ae585494b80296bc9e0f1c96',
 'V_DRM18K_E1':'c7c271c7c372ccd9f7e3701db5a79a94e106ac28b7b735c60f3a8f43d78429da',
 'V_RAM32X2':'7cee56e7385cc148c6ea6168736b47ae149d0ecb0c06a4542706c7ac8bf7b7d8',
 'V_RAM64X1':'9db9dff12cad2f7b36faf95fd36cb41cb2c959c4108b033d0dcf69ee729ae8ed',
 'V_DDC_E2':'c027722638f7db1d08da558b75b15096b38c2d6051dc3b4fc701ad70c6c861b7',
 'V_DLL_E2':'2b211722146a320cebad8b766aab0a9c9ce8dc2904a836e49c9dddd4fc619c58',
 'V_OSERDES_E2':'ba0c851b5b92fa7e058de09170f75732077fbc89f5c52920200f0be5f69b7c4b',
 'V_IOCLKDIV_E3':'79f352b067925c9bfbeef56c3e8004ad337c90c6a54375bd96b4738708aab959',
 'V_ISERDES_E2':'c2143c03bd2d45fdaf0433aeac186ed8029c0ea876e725a88607a290fe624243',
 'V_IODELAY_E2':'aaac47969e218e9fdcf5142b954916f6c0e6e5d5729189e6004ba04f3cb48d7a',
 'V_CLKPD':'abcf4732014b8d3729ac9f8cd4db26e4b4d3ff04b3e8ac8eed33f9c814e4d25c',
}
PHY={'V_DDC_E2','V_DLL_E2','V_OSERDES_E2','V_ISERDES_E2','V_CLKPD'}
MACRO_CLOCKS={
 'V_APM_E2':('CLK',),'V_RAM32X2':('WCLK',),'V_RAM64X1':('WCLK',),
 'V_DRM18K_E1':('CLKA','CLKB'),'V_DRM36K_E1':('CLKA','CLKB'),
 'V_OSERDES_E2':('OCLK','OCLKDIV','SERCLK'),'V_ISERDES_E2':('ICLK','ICLKB','ICLKDIV','OCLK','DESCLK'),
 'V_DDC_E2':('CLKA','CLKB','DQSI','DQSIB'),'V_DLL_E2':('CLKIN','SYS_CLK'),
 'V_CLKPD':('CLK_CTRL','CLK_PHY','CLK_SAMPLE'),
}


class Findings:
    def __init__(self):self.rows=[];self.seen=set()
    def add(self,code,obj,detail):
        row={'Code':code,'Object':str(obj),'Detail':str(detail)};key=json.dumps(row,sort_keys=True)
        if key not in self.seen:self.seen.add(key);self.rows.append(row)


def atoms(value):
    """Scalarize exported buses without confusing a missing macro driver with IO."""
    value=canon(value)
    result=[]
    for item in value.replace('{','').replace('}','').split(','):
        if not item:continue
        if re.fullmatch(r"(?:\d+)?'[sS]?[bBoOdDhH][0-9a-fA-F_xXzZ?]+|\d+",item):
            if re.search(r'[xXzZ?]',item):result.append('@unknown_constant:'+item)
            continue
        match=re.fullmatch(r'(.+)\[(\d+):(\d+)\]',item)
        if match:
            hi,lo=int(match[2]),int(match[3]);step=-1 if hi>=lo else 1
            result.extend(match[1]+f'[{i}]'for i in range(hi,lo+step,step));continue
        require(re.fullmatch(r'[A-Za-z_$][\w$./-]*(?:\[\d+\])*(?:[\w$./-]+(?:\[\d+\])*)*',item),
                'unsupported scalar net expression: '+item)
        result.append(item)
    return result


def model_ports(text,kind):
    text=re.sub(r'/\*.*?\*/|//[^\n]*','',text,flags=re.S)
    match=re.search(r'\bmodule\s+'+re.escape(kind)+r'\b',text)
    require(match is not None,'vendor model module absent: '+kind)
    body=text[match.end():text.index('endmodule',match.end())].lstrip()
    def group(value):
        require(value.startswith('('),'vendor port/parameter group absent')
        depth=0
        for i,char in enumerate(value):
            depth+=(char=='(')-(char==')')
            if depth==0:return value[1:i],value[i+1:]
        raise ValueError('unterminated vendor header')
    if body.startswith('#'):_,body=group(body[1:].lstrip());body=body.lstrip()
    header,tail=group(body)
    ansi=bool(re.search(r'\b(?:input|output|inout)\b',header))
    names=None if ansi else {p.strip()for p in header.split(',')}
    body=header+';' if ansi else tail
    result={}
    pattern=r'\b(input|output|inout)\b(.*?)(?=\binput\b|\boutput\b|\binout\b|;|\)\s*;)'
    for direction,declaration in re.findall(pattern,body,re.S):
        declaration=re.sub(r'\[[^\]]*\]|\b(?:wire|reg|signed|tri|tri0|tri1)\b','',declaration)
        for item in declaration.strip(' \r\n\t,').split(','):
            item=item.strip()
            require(re.fullmatch(r'[A-Za-z_]\w*',item),'unsupported vendor port declaration: '+item)
            if names is not None and item not in names:continue
            if item in result:continue
            result[item]=direction.upper()
    require(result,'no vendor primitive port directions: '+kind)
    return result


def functional(text):
    require(re.findall(r'(?m)^module\s+(\w+)',text)==[TARGET],'one flat current pixel module required')
    adapted,count=re.subn(r'(?m)^(module\s+)'+TARGET+r'\b',r'\g<1>'+syntax.prep.TARGET,text)
    require(count==1,'ambiguous pixel module adaptation')
    return syntax.functional(adapted)


def clock_definitions(text):
    rows={}
    for line in text.splitlines():
        if not line.startswith(('create_clock ','create_generated_clock ')):continue
        name=re.search(r'-name\s+\{?([\w]+)\}?',line)
        require(name is not None and name[1] not in rows,'duplicate/unnamed pixel clock')
        row={'Name':name[1],'Statement':line,'Generated':line.startswith('create_generated_clock ')}
        command='get_pins' if row['Generated'] else 'get_ports'
        targets=re.findall(r'\['+command+r'\s+\{?([^}\]]+(?:\][^}\]]*)?)\}?\]',line)
        # Braced hierarchical pins contain genblk array brackets. Keep their
        # full literal token using the brace form before trying plain syntax.
        targets=re.findall(r'\['+command+r'\s+\{([^}]+)\}\]',line) or targets
        require(targets,'clock target absent: '+name[1]);row['Target']=targets[-1].strip()
        if not row['Generated']:
            period=re.search(r'-period\s+\{?([0-9.]+)',line);require(period,'clock period absent')
            row['PeriodNS']=float(period[1]);row['Master']=name[1]
        else:
            master=re.search(r'-master_clock\s+\[get_clocks\s+\{?([\w]+)',line)
            source=re.search(r'-source\s+\[get_(ports|pins)\s+\{([^}]+)\}\]',line) or re.search(r'-source\s+\[get_(ports|pins)\s+(\S+)\]',line)
            require(source,'generated clock source absent');row['SourceType'],row['Source']=source[1],source[2]
            row['Master']=master[1] if master else None
            multiply=re.search(r'-multiply_by\s+\{?([0-9.]+)',line);divide=re.search(r'-divide_by\s+\{?([0-9.]+)',line)
            edges=re.search(r'-edges\s+\{([0-9 ]+)\}',line)
            row['Multiply']=float(multiply[1]) if multiply else None
            row['Divide']=float(divide[1]) if divide else None
            row['Edges']=[int(x)for x in edges[1].split()] if edges else None
        rows[name[1]]=row
    for _ in range(len(rows)):
        for row in rows.values():
            if 'PeriodNS'in row:continue
            sources=[r for r in rows.values() if r['Target']==row['Source'] and 'PeriodNS'in r]
            if len(sources)!=1:continue
            source=sources[0];row['Master']=row['Master'] or source['Master']
            if row['Edges']:
                require(len(row['Edges'])==3,'three generated clock edges required')
                row['PeriodNS']=(row['Edges'][2]-row['Edges'][0])*source['PeriodNS']/2
            else:
                require(row['Multiply'] and row['Divide'],'clock ratio absent')
                row['PeriodNS']=source['PeriodNS']*row['Divide']/row['Multiply']
    require(rows and all('PeriodNS'in r for r in rows.values()),'unresolved generated clock periods')
    return rows


def hierarchy(value):return canon(value).replace('.','/')


class PixelGraph(mux.Graph):
    def __init__(self,parsed,ports,clocks,models,findings=None):
        super().__init__(parsed)
        self.ports,self.clocks,self.models=ports,clocks,models
        self.findings=findings or Findings();self.scalar_outputs=defaultdict(list);self.scalar_refs=defaultdict(list)
        self.support_cache={};self.macro_rows={};self.clock_cache={}
        self.input_cache={}
        for name,c in self.cells.items():
            kind=c['Primitive'];directions=models.get(kind,{}).get('Ports',{})
            if not directions:self.findings.add('UnknownPrimitive',name,kind)
            if set(c['Ports'])-set(directions):self.findings.add('UnknownPrimitivePorts',name,sorted(set(c['Ports'])-set(directions)))
            for pin,value in c['Ports'].items():
                for net in atoms(value):
                    self.scalar_refs[net].append((name,pin))
                    if directions.get(pin)=='OUTPUT':self.scalar_outputs[net].append((name,pin))

    def driver(self,net):
        values=self.scalar_outputs.get(canon(net),[])
        require(len(values)==1,'unique typed driver required: '+canon(net)+': '+str(values))
        return values[0]

    def clock(self,net,visited=()):
        net=canon(net)
        if net in self.clock_cache:return self.clock_cache[net]
        require(net not in visited,'clock cycle')
        primary=[r for r in self.clocks.values()if not r['Generated'] and r['Target']==net]
        if primary:
            require(len(primary)==1,'ambiguous primary clock');r=primary[0]
            value={'Domain':r['Name'],'Root':net,'PeriodNS':r['PeriodNS'],'Master':r['Master'],'Trace':[]}
        else:
            name,pin=self.driver(net);c=self.cells[name];p=c['Ports'];kind=c['Primitive']
            row={'Cell':name,'Primitive':kind,'Pin':pin,'Net':net}
            if kind in ('V_BUF','V_IBUF','V_IBUFDS'):
                value={**self.clock(p['I'],visited+(net,))};value['Trace']=[row]+value['Trace']
            elif kind=='V_USCM':
                require(c['Parameters'].get('USCM_MODE')=='"BUF_A"' and pin=='CLKOUT','dynamic clock mux')
                value={**self.clock(p['CLK0'],visited+(net,))};value['Trace']=[row]+value['Trace']
            else:
                require(kind in ('V_GPLL','V_PPLL','V_IOCLKDIV_E3'),'unreviewed clock driver '+kind+'/'+pin)
                matches=[]
                for r in self.clocks.values():
                    if not r['Generated'] or '/'not in r['Target']:continue
                    wrapper,output=r['Target'].rsplit('/',1)
                    if pin.lower()==output.lower() and (hierarchy(name)==hierarchy(wrapper) or hierarchy(name).startswith(hierarchy(wrapper)+'/')):matches.append(r)
                require(len(matches)==1,'unbound native generated clock '+name+'/'+pin)
                r=matches[0]
                if kind=='V_IOCLKDIV_E3':
                    factor=int(c['Parameters'].get('DIV_FACTOR','"0"').strip('"'))
                    phase=int(c['Parameters'].get('PHASE_SHIFT','"-1"').strip('"'))
                    require(factor in (4,8) and 0<=phase<8 and phase<factor,'unsupported E3 clock divider mode')
                    upstream=self.clock(p['CLKIN'],visited+(net,))
                    require(abs(r['PeriodNS']-factor*upstream['PeriodNS'])<1e-6,'clock divider/FDC ratio differs')
                value={'Domain':r['Name'],'Root':name+'/'+pin,'PeriodNS':r['PeriodNS'],'Master':r['Master'],'Trace':[row]}
        self.clock_cache[net]=value;return value

    def macro(self,name,pin):
        key=name+'/'+pin
        if key in self.macro_rows:return self.macro_rows[key]
        c=self.cells[name];kind=c['Primitive'];p=c['Ports'];parameters=c['Parameters']
        if kind.startswith('V_DRM'):
            mode=parameters.get('RAM_MODE');require(mode in ('"TRUE_DUAL_PORT"','"SIMPLE_DUAL_PORT"','"SINGLE_PORT"'),'unsupported DRM mode')
            require(parameters.get('RAM_CASCADE','"NONE"')=='"NONE"' and parameters.get('ECC_READ_EN','"FALSE"')=='"FALSE"'
                    and parameters.get('ECC_WRITE_EN','"FALSE"')=='"FALSE"','unreviewed DRM cascade/ECC support')
            width=int(parameters['DATA_WIDTH_B']);wide=width>36 if kind=='V_DRM36K_E1' else width>=32
            side='B' if wide or pin.startswith('DOB') else 'A'
            clock_pins=('CLK'+side,);nature='synchronous_read_memory'
        elif kind in ('V_RAM32X2','V_RAM64X1'):
            clock_pins=('WCLK',);nature='asynchronous_read_memory'
        elif kind=='V_APM_E2':clock_pins=('CLK',);nature='mixed_registered_and_combinational_DSP'
        elif kind in PHY:clock_pins=MACRO_CLOCKS[kind];nature='vendor_multi_clock_PHY_boundary'
        elif kind in ('V_GPLL','V_PPLL'):clock_pins=();nature='PLL_analog_status_or_APB'
        else:raise ValueError('unreviewed typed macro '+kind+'/'+pin)
        clocks=[];errors=[]
        for cp in clock_pins:
            if not atoms(p.get(cp,"1'b0")):continue
            tied=abstract_value(self,p[cp],{},{})
            if len(tied)==1:
                clocks.append({'Pin':cp,'Nature':'constant_unused_clock_input','Value':next(iter(tied))});continue
            try:clocks.append({'Pin':cp,**self.clock(p[cp])})
            except ValueError as e:errors.append({'Pin':cp,'Net':p[cp],'Error':str(e)});self.findings.add('UnknownMacroClock',key+'/'+cp,e)
        value={'Cell':name,'Output':pin,'Primitive':kind,'Nature':nature,'Model':self.models[kind]['Reference'],
            'ClockBindings':clocks,'UnresolvedClocks':errors,'ParametersSHA256':hashlib.sha256(json.dumps(parameters,sort_keys=True).encode()).hexdigest(),
            'OrdinaryFFClaimed':False,'TimingAccepted':False,'ExceptionEligible':False}
        if kind in PHY:
            value['DetailedModeProofComplete']=False
            self.findings.add('PHYModeNeedsReview',key,'bound exact E2/CPD model, multi-clock/latch/cascade details not silently accepted')
        if kind=='V_APM_E2':
            value['DetailedModeProofComplete']=False
            self.findings.add('APMOutputModeNeedsReview',key,'mixed register/bypass/control support retained; exact output-stage proof remains required')
        self.macro_rows[key]=value;return value

    def support(self,value,active=()):
        result=set()
        for net in atoms(value):result|=self._support(net,active)
        return result

    def _support(self,net,active):
        if net in self.support_cache:return self.support_cache[net]
        if net.startswith('@unknown_constant:'):
            self.findings.add('UnknownConstant',net,'X/Z is not accepted as a digital source');return {('unresolved',net)}
        drivers=self.scalar_outputs.get(net,[])
        if not drivers:
            if self.ports.get(net) in ('INPUT','INOUT'):return {('primary',net)}
            self.findings.add('UndrivenInternalNet',net,'no primary-input fallback');return {('unresolved',net)}
        require(len(drivers)==1,'ambiguous typed net driver: '+net)
        name,pin=drivers[0];c=self.cells[name];kind=c['Primitive'];p=c['Ports']
        if name in self.ff:return {('ff',name)}
        if kind=='V_OBUFT'and self.ports.get(net)=='INOUT':
            result={('resolved_inout',net)}
            for value in (p['I'],p['T']):result|=self.support(value,active+(net,))
            self.support_cache[net]=result;return result
        if kind in ('V_BUF','V_INV','V_IBUF','V_IBUFDS'):
            dependencies=[p['I']]
            if kind=='V_IBUFDS':dependencies.append(p['IB'])
        elif kind in ('V_LUT6CARRY','V_MUX2'):
            key=(name,pin)
            if key not in self.input_cache:self.input_cache[key]=tuple(mux.inputs(c,pin))
            dependencies=self.input_cache[key]
        elif kind=='V_IODELAY_E2':
            require(c['Parameters'].get('DELAY_STEP_SEL') in ('"PORT"','"PARAMETER"'),'unknown E2 delay selector')
            dependencies=[v for k,v in p.items()if self.models[kind]['Ports'].get(k)=='INPUT']
        elif kind in MACRO_CLOCKS or kind in ('V_GPLL','V_PPLL'):
            boundary=self.macro(name,pin);token=('macro',name+'/'+pin)
            # DSP bypasses and asynchronous LUT-RAM read addresses remain
            # explicit dependencies. A macro token is never called an FF Q.
            dependencies=[]
            if kind=='V_APM_E2':dependencies=[v for k,v in p.items()if self.models[kind]['Ports'].get(k)=='INPUT' and k not in MACRO_CLOCKS[kind]]
            if kind in ('V_RAM32X2','V_RAM64X1'):dependencies=[p['RADDR']]
            if net in active:return {token}
            result={token}
            for value in dependencies:result|=self.support(value,active+(net,))
            self.support_cache[net]=result;return result
        else:
            self.findings.add('UnsupportedConePrimitive',name,kind+'/'+pin);return {('unresolved',name+'/'+pin)}
        require(net not in active,'combinational Boolean cycle: '+net)
        result=set()
        for value in dependencies:result|=self.support(value,active+(net,))
        self.support_cache[net]=result;return result


def static_helpers(root=SELF):
    """Source-declared local imports only; independent of the calling process."""
    pending=[Path(root).resolve()];seen=set();directory=SELF.parent
    while pending:
        path=pending.pop()
        if path in seen:continue
        seen.add(path);tree=ast.parse(path.read_text(encoding='utf-8-sig'))
        for node in ast.walk(tree):
            names=[]
            if isinstance(node,ast.Import):names=[n.name for n in node.names]
            elif isinstance(node,ast.ImportFrom):
                if node.module:names.append(node.module)
                if node.module=='tools':names.extend(n.name for n in node.names)
            for name in names:
                candidate=directory/(name.split('.')[-1]+'.py')
                if candidate.is_file() and candidate not in seen:pending.append(candidate)
    return sorted(seen)


def load_models(kinds,watched):
    result={}
    for kind in sorted(kinds):
        if kind not in MODEL_SHA:
            result[kind]={'Reference':None,'Ports':{}};continue
        path=MODEL_ROOT/(kind+'.v');require(sha(path)==MODEL_SHA[kind],'vendor primitive model differs: '+kind)
        native.add(watched,path)
        result[kind]={'Reference':native.ref(path),'Ports':model_ports(path.read_text(encoding='utf-8-sig'),kind)}
    return result


def imported_runtime(watched):
    """Bind explicit binary dependencies of the reused parser import chain."""
    paths={Path(sys.executable).resolve(),Path(numpy.__file__).resolve(),Path(cv2.__file__).resolve()}
    for package in (numpy,cv2):paths.update(Path(package.__file__).resolve().parent.rglob('*.pyd'))
    for path in sorted(paths):native.add(watched,path)


def pin_inventory(build_dir,g,plan,watched):
    source=build_dir/'compiled'/build.TOP;fdcpath=build_dir/'compiled'/build.FDC
    pcfpath=build_dir/'device_map'/(TARGET+'.pcf')
    prtpath=build_dir/'place_route'/(TARGET+'_prr_route_optimize.prt')
    for path in (source,fdcpath,pcfpath,prtpath):native.add(watched,path)
    declared=build.top_ports(source.read_text(encoding='utf-8-sig'))
    fdc=pin_parser.fdc_pins(fdcpath.read_text());pcf=pin_parser.pcf_pins(pcfpath.read_text())
    _,routed=pin_parser.routed_pads(prtpath.read_text())
    planned=plan['Pins']['PinInventory']
    require(set(declared)==set(fdc)==set(pcf)==set(planned),'declared/FDC/PCF/plan pins differ')
    missing=set(declared)-set(routed)
    require(missing<=UNUSED_RGB and not set(routed)-set(declared),'unexpected missing/extra routed pixel pads')
    rows=[]
    for port,direction in sorted(declared.items()):
        require(fdc[port]['DIRECTION']==direction and fdc[port]['LOC']==planned[port]['LOC'],'pin direction/location differs: '+port)
        for key,value in fdc[port].items():
            if key!='DIRECTION':require(pcf[port].get(key)==value,'native pin attribute differs: '+port+'/'+key)
        connections=[{'Cell':n,'Pin':p,'Primitive':g.cells[n]['Primitive']}
                     for n,p in g.scalar_refs.get(port,[])]
        if port in missing:
            require(not connections,'unrouted RGB LSB retains native consumer: '+port)
            disposition='RGB565_quantization_no_native_consumer'
        elif pcf[port].get('UNUSED')=='TRUE':disposition='native_explicit_UNUSED'
        else:disposition='routed_active'
        if port in routed:
            require(routed[port]['Direction']==direction and routed[port]['Pad']==fdc[port]['LOC'],'routed pad differs: '+port)
        rows.append({'Port':port,'Direction':direction,'Attributes':pcf[port],
            'Route':routed.get(port),'Disposition':disposition,'FunctionalConnections':connections})
    return {'Declared':len(declared),'Routed':len(routed),'Active':sum(r['Disposition']=='routed_active'for r in rows),
        'Unused':sorted(r['Port']for r in rows if r['Disposition']!='routed_active'),
        'MissingRoutedRGBBits':sorted(missing),'Inventory':rows,'NativeElectricalParametersVerified':False}


def ff_identity(g,name):
    """Actual functional Q, never the packed parent register's spelling."""
    return canon(g.ff[name]['Ports']['Q'])


def rtl_alias_inventory(build_dir,g,watched):
    """Recover only literal net/port aliases, with frozen RTL provenance.

    No register update, bit position in an instance name, or Boolean equality
    is treated as an alias. Optimizer-merged state still needs its own proof.
    """
    specifications=[('',build.TOP),('system/','rtl/experimental/hdmi1080_video_system_cdc_reset.v'),
        ('system/input_link/','rtl/experimental/hdmi1080_input_write_link.v'),
        (DMA,'rtl/experimental/hdmi1080_input_dma.v'),(CAP,'rtl/experimental/hdmi1080_capture_cdc.v'),
        (OUT,'rtl/experimental/ddr_video_output_1080_board.v')]
    parents={};evidence=[];texts={};shapes={}
    def find(n):
        parents.setdefault(n,n)
        if parents[n]!=n:parents[n]=find(parents[n])
        return parents[n]
    def join(a,b,proof):
        if a==b:return
        x,y=find(a),find(b)
        if x!=y:parents[y]=x
        evidence.append({'Left':a,'Right':b,**proof})
    for scope,name in specifications:
        path=build_dir/'compiled'/name;native.add(watched,path)
        text=re.sub(r'/\*.*?\*/|//[^\n]*','',path.read_text(encoding='utf-8-sig'),flags=re.S)
        texts[scope]=text;bounds={}
        for hi,lo,names in re.findall(r'\b(?:input|output|wire|reg)\s+(?:(?:wire|reg|signed)\s+)*\[(\d+):(\d+)\]\s+([^;\n]+)',text):
            for item in names.split(','):
                m=re.match(r'\s*([A-Za-z_]\w*)\b',item)
                if m:bounds[m[1]]=(int(hi),int(lo))
        shapes[scope]=bounds
    def scalar(expr,scope,width=None):
        expr=canon(expr)
        if re.fullmatch(r'[A-Za-z_]\w*',expr)and(expr in shapes[scope]or width and width>1):
            hi,lo=shapes[scope][expr]if expr in shapes[scope]else(width-1,0)
            return [scope+expr+f'[{i}]'for i in range(hi,lo-1,-1)]
        if expr.startswith('{'):
            return [n for part in expr[1:-1].split(',')for n in scalar(part,scope)]
        try:values=atoms(expr)
        except ValueError:return []
        return [scope+x for x in values]
    for scope,text in texts.items():
        for lhs,rhs in re.findall(r'\bassign\s+([^;=]+?)\s*=\s*([^;]+);',text):
            if not re.fullmatch(r'[\w\s{},:\[\]]+',lhs+rhs):continue
            left=scalar(lhs,scope);right=scalar(rhs,scope)
            if left and len(left)==len(right):
                for x,y in zip(left,right):join(x,y,{'Scope':scope,'Kind':'literal_wire_assign','Statement':lhs.strip()+' = '+rhs.strip()})
    links=[('','system','hdmi1080_video_system','system/'),('system/','input_link','hdmi1080_input_write_link','system/input_link/'),
        ('system/input_link/','input_dma','hdmi1080_input_dma',DMA),(DMA,'capture','hdmi1080_capture_cdc',CAP),
        ('system/','output_video','ddr_video_output_1080_board',OUT)]
    for parent,instance,module,child in links:
        matches=re.findall(r'\b'+module+r'\s*(?:#\s*\(.*?\)\s*)?'+instance+r'\s*\((.*?)\)\s*;',texts[parent],re.S)
        require(len(matches)==1,'frozen RTL instance alias binding absent: '+child)
        for formal,actual in re.findall(r'\.(\w+)\s*\(([^()]*)\)',matches[0]):
            if not re.fullmatch(r'[\w\s{},:\[\]]+',actual):continue
            hi,lo=shapes[child].get(formal,(0,0));width=hi-lo+1
            left=scalar(formal,child,width);right=scalar(actual,parent,width)
            if left and len(left)==len(right):
                for x,y in zip(left,right):join(x,y,{'Scope':parent,'Kind':'literal_instance_port','Instance':instance,'Formal':formal,'Actual':actual.strip()})
    # A top output's IOB buffer introduces an internal native wire, not a
    # register alias guessed from the spelling nt_led or nt_r_out.
    for pad,direction in g.ports.items():
        if direction!='OUTPUT':continue
        drivers=g.scalar_outputs.get(pad,[])
        if len(drivers)!=1:continue
        n,p=drivers[0];c=g.cells[n]
        if c['Primitive']=='V_OBUFT'and c['Ports'].get('T')=="1'b0":
            join(pad,canon(c['Ports']['I']),{'Kind':'native_output_buffer','Cell':n,'Output':p})
    groups=defaultdict(set)
    for n in list(parents):groups[find(n)].add(n)
    aliases={n:sorted(values)for values in groups.values()for n in values}
    g.rtl_aliases=aliases
    return {'LiteralAliasEvidence':evidence,'AliasGroups':[sorted(v)for v in groups.values()if len(v)>1],
        'RegisterNextStateEquivalenceInferred':False}


def logical_ff_candidates(g,logical):
    aliases=getattr(g,'rtl_aliases',{}).get(logical,[logical]);result=[]
    for name in g.ff:
        if ff_identity(g,name)in aliases:result.append(name)
    return result


def discover_chains(g):
    families=[x+'_ref'for x in ('cfg_lock','video_lock','rx_done','tx_done','cfg_failed','ddr_init','ddr_pll',
                                  'system_failed','processed','pclk_activity','hs_activity')]
    families+=['board_failed_core','system/request_sync','system/grant_ack_sync','system/done_sync',
        'system/scan_abort_sync','system/scan_enable_sync','system/scan_failed_sync',CAP+'enable_pix',CAP+'grant_sync',
        CAP+'done_sync',CAP+'ack_sync',OUT+'grant_sync',OUT+'done_ack_sync']
    pairs=[(family+'[0]',family+'[1]','scalar')for family in families]
    gray=[]
    for prefix,width in ((CAP+'pixels/',7),('system/display_fifo/',10)):
        for direction,first,second in (('wr','wr_gray_r1','wr_gray_r2'),('rd','rd_gray_w1','rd_gray_w2')):
            for bit in range(width):
                pairs.append((prefix+first+f'[{bit}]',prefix+second+f'[{bit}]','gray'))
                gray.append({'FirstLogical':pairs[-1][0],'ExpectedSource':prefix+direction+f'_gray[{bit}]',
                    'PermittedMSBIdentity':prefix+direction+f'_binary[{bit}]'if bit==width-1 else None,'Width':width,'Bit':bit})
    for bit in range(32):
        pairs.append((CAP+f'no_grant_s1[{bit}]',CAP+f'no_grant_s2[{bit}]','gray'))
        gray.append({'FirstLogical':pairs[-1][0],'ExpectedSource':CAP+f'no_grant_gray[{bit}]',
            'PermittedMSBIdentity':CAP+f'no_grant_binary[{bit}]'if bit==31 else None,'Width':32,'Bit':bit})
    byq=defaultdict(list)
    for n in g.ff:byq[ff_identity(g,n)].append(n)
    rows=[]
    for firstq,secondq,role in pairs:
        seconds=logical_ff_candidates(g,secondq)
        if len(seconds)!=1:
            if role=='gray'and not any(q in g.scalar_refs for q in (firstq,secondq)):
                # The diagnostic count is not consumed by this top. Absence
                # creates no endpoint and is never replaced by an old count.
                continue
            g.findings.add('SynchronizerMappingMissing',secondq,seconds);continue
        second=seconds[0];sc=g.clock(g.ff[second]['Ports']['CK'])['Domain']
        actual_firsts=set(logical_ff_candidates(g,firstq))
        candidates=[n for kind,n in g.support(g.ff[second]['Ports']['D'])if kind=='ff' and n!=second
            and g.clock(g.ff[n]['Ports']['CK'])['Domain']==sc and
            (n in actual_firsts or n.startswith(firstq+'/'))]
        if not candidates:
            candidates=[n for kind,n in g.support(g.ff[second]['Ports']['D'])if kind=='ff' and n!=second
                and g.clock(g.ff[n]['Ports']['CK'])['Domain']==sc and n.startswith(secondq+'/')]
        if len(candidates)!=1:
            g.findings.add('SynchronizerMappingMissing',firstq,candidates);continue
        first=candidates[0];inputs=sorted(n for kind,n in g.support(g.ff[first]['Ports']['D'])if kind=='ff')
        rows.append({'FirstLogical':firstq,'SecondLogical':secondq,'First':first,'Second':second,'Role':role,
            'DestinationClock':sc,'FirstActualQ':ff_identity(g,first),'SecondActualQ':ff_identity(g,second),
            'FirstDSourceFFs':inputs,'InterstageTimingExcepted':False,
            'StructuralChainVerified':True,'NativeMetastabilityAcceptanceClaimed':False})
    byfirst={r['FirstLogical']:r for r in rows}
    for item in gray:
        if item['FirstLogical']in byfirst:
            row=byfirst[item['FirstLogical']]
            row.update(ExpectedSource=item['ExpectedSource'],PermittedMSBIdentity=item['PermittedMSBIdentity'])
            item.update(row)
    return rows,gray


def held_role(source,destination):
    """Candidate protocol inventory includes real control fanout, also SR."""
    groups=[(CAP+r'grant_(?:bank_hold|id_hold\[\d+\])',CAP,'capture_grant_held'),
        (DMA+r'cap_done_(?:good|bank|id\[\d+\]|pixels\[\d+\]|crc\[\d+\]|fault\[\d+\])',DMA,'capture_end_held'),
        (r'system/scan_request_epoch\[\d+\]',r'system/','scan_request_epoch_held'),
        (r'system/grant_(?:valid|epoch\[\d+\]|checksum\[\d+\]|id\[\d+\]|bank)',OUT,'scan_grant_held'),
        (r'system/(?:scan_done_(?:good|bank|epoch\[\d+\]|id\[\d+\])|pix_done_crc\[\d+\]|consumed_pixels\[\d+\])',r'system/','scan_done_held'),
        (r'board_fault\[\d+\]',r'system/','board_fault_held'),
        (r'system/system_fault\[\d+\]',OUT,'system_fault_held')]
    # Data may control business state but cannot bypass a synchronizer/reset chain.
    if re.search(r'(?:reset|_sync|_ref|enable_pix|no_grant_s)[^/]*\[',destination):return None
    for pattern,prefix,role in groups:
        if re.fullmatch(pattern,source) and destination.startswith(prefix):return role
    return None


def crossing_inventory(g,chains):
    firsts={r['First']:r for r in chains};rows=[];other=[];local=[];clock_counts=Counter()
    clocks={}
    for n,c in sorted(g.ff.items()):
        try:clocks[n]=g.clock(c['Ports']['CK']);clock_counts[clocks[n]['Domain']]+=1
        except ValueError as e:g.findings.add('UnknownFFClock',n,e)
    for destination,cell in sorted(g.ff.items()):
        if destination not in clocks:continue
        dc=clocks[destination]['Domain'];dq=ff_identity(g,destination)
        for pin in ('D','CE','SR'):
            if pin not in cell['Ports']:continue
            for kind,source in sorted(g.support(cell['Ports'][pin])):
                if kind!='ff':
                    other.append({'SourceKind':kind,'Source':source,'DestinationFF':destination,'DestinationPin':pin,
                        'DestinationClock':dc});continue
                if source not in clocks:continue
                sc=clocks[source]['Domain']
                if sc==dc:continue
                sq=ff_identity(g,source);role=None
                source_aliases=getattr(g,'rtl_aliases',{}).get(sq,[sq]);destination_aliases=getattr(g,'rtl_aliases',{}).get(dq,[dq])
                if destination in firsts and pin=='D':
                    chain=firsts[destination]
                    if chain['Role']!='gray'or sq in (chain['ExpectedSource'],chain['PermittedMSBIdentity']):
                        role=chain['Role']+'_first_stage'
                if not role:
                    roles={held_role(sa,da)for sa in source_aliases for da in destination_aliases}-{None}
                    if len(roles)==1:role=next(iter(roles))
                if not role and pin=='SR' and cell['Primitive']=='V_FFASYN':role='async_reset_requires_guard_review'
                if not role:role='unclassified';g.findings.add('UnclassifiedForeignRelationship',source+' -> '+destination+'/'+pin,sq+' -> '+dq)
                rows.append({'SourceFF':source,'DestinationFF':destination,'DestinationPin':pin,'SourceClock':sc,
                    'DestinationClock':dc,'SourceLogicalQ':sq,'DestinationLogicalQ':dq,'Role':role,
                    'ProtocolProved':False})
    return rows,other,dict(sorted(clock_counts.items()))


class PixelMapper(clm.Mapper):
    def support(self,net,active=()):return {n for kind,n in self.g.support(net)if kind=='ff'}

    def boundaries(self,target,pin):
        key=target,pin
        if key in self.boundary_cache:return self.boundary_cache[key]
        site=self.g.g['FFPlacement'][target]['Site'];target_parent=raw.parent(target);rows={}
        def external(parent,np,net,trail,alias=None):
            endpoint=parent+'/'+np
            require((parent,np)in self.route['Pins'],'native boundary pin missing: '+endpoint)
            row=rows.setdefault(endpoint,{'Endpoint':endpoint,'BoundaryNet':canon(net),'FunctionalBoundaryNet':net,
                'NativeBoundaryNet':self.route['Pins'][parent,np],'NetAliasProof':alias,
                'PhysicalCLMSite':site,'BoundaryToLogicalFF':[]})
            require(row['BoundaryNet']==canon(net),'ambiguous native boundary functional net')
            row['BoundaryToLogicalFF'].append(trail)
        def visit(net,trail,active,consumer):
            net=canon(net);require(net not in active,'cycle inside receiving physical CLM')
            if not self.support(net):return
            cn,cp=consumer
            if cn in self.g.ff:
                expected={'D':'D','CE':'CE','SR':'RS'}[pin]
                if self.route['Pins'].get((target_parent,expected))==net:
                    external(target_parent,expected,net,trail);return
            elif self.g.cells[cn]['Primitive']=='V_LUT6CARRY':
                require(cn in self.placements and self.placements[cn]['Site']==site,'local control/data cone escapes CLM before native boundary')
                parent,actual,native_net,alias=self.connection(cn,cp)
                require(canon(actual)==net,'native receiving LUT net differs')
                if cp!='CIN'or clm.ble(self.placements[cn])=='A':
                    external(parent,cp,net,trail,alias);return
                driver,op=self.g.driver(net)
                require(driver in self.placements and op=='COUT','internal native carry lacks actual source')
                a,b=self.placements[driver],self.placements[cn]
                require(a['Site']==b['Site']==site and ord(clm.ble(a))+1==ord(clm.ble(b)),'carry crosses nonadjacent BLE')
                dp=driver.rsplit('/',2)[0]
                require(self.route['Pins'].get((dp,'COUT'))==native_net,'native carry source/consumer NET differs')
            driver,op=self.g.driver(net);cell=self.g.cells[driver]
            require(driver not in self.g.ff,'sequential launch internal to unresolved receiving boundary')
            require(cell['Primitive']in ('V_LUT6CARRY','V_BUF','V_INV','V_MUX2'),'unreviewed local physical cone primitive')
            if cell['Primitive']=='V_LUT6CARRY':
                require(driver in self.placements and self.placements[driver]['Site']==site,'receiving data/control cone left physical CLM')
            if cell['Primitive']=='V_MUX2':
                # No undocumented native MUX timing pin is invented.
                raise ValueError('native local MUX2 boundary requires mode-specific physical mapping')
            for ip in clm.endpoints.input_pins(cell,op):
                step={'Cell':driver,'Primitive':cell['Primitive'],'Output':op,'Input':ip,'Parameters':cell['Parameters']}
                visit(cell['Ports'][ip],trail+[step],active+(net,),(driver,ip))
        visit(self.g.ff[target]['Ports'][pin],[],(),(target,pin))
        require(rows,'no receiving native boundary for actual logical consumer')
        self.boundary_cache[key]=[rows[k]for k in sorted(rows)]
        return self.boundary_cache[key]


def native_route(path,wanted):
    """Reuse the balanced ADIF lexer, retaining exact scalar and ARRAY ports.

    The older CLM-only reader rejects the current native RAM/APM interfaces.
    Expanding an explicit numeric ARRAY interface creates no new net or pin.
    """
    adif=clm.endpoints.adif;cells={};instances={};pins={};active=None;depth=0;held=[]
    for line in Path(path).open(encoding='utf-8-sig'):
        tokens=adif.TOKEN.findall(line)
        require(not adif.TOKEN.sub('',line).strip(),'unparsed native route tokens')
        start=depth;depth+=tokens.count('(')-tokens.count(')');require(depth>=0,'unbalanced native route')
        if active is None and tokens[:2]==['(','CELL'] and tokens[2].startswith('gop'):active=('CELL',start);held=[]
        elif active is None and tokens[:2]==['(','INSTANCE'] and canon(tokens[2])in wanted:active=('INSTANCE',start);held=[]
        elif active is None and tokens[:2]==['(','NET']:active=('NET',start);held=[]
        if active is None:continue
        held+=tokens
        if depth!=active[1]:continue
        node=adif.expression(held)
        if active[0]=='CELL':
            require(node[1]not in cells,'duplicate native CELL');cells[node[1]]=node
        elif active[0]=='INSTANCE':
            name=canon(node[1]);require(name not in instances and node[2][:2]==['VIEWREF','OPER'],'native instance shape')
            ref=node[2][2];require(ref[0]=='CELLREF'and ref[2][0]=='OPERAREF','native cell reference shape')
            instances[name]={'Cell':ref[1],'Operator':ref[2][1]}
        else:
            array=isinstance(node[1],list)
            if array:require(node[1][0]=='ARRAY','unknown native NET array')
            for conn in node[2:]:
                if conn[0]=='ATTRIBUTE':require(len(conn)>=3,'native NET attribute shape');continue
                require(conn[0]=='CONNECT','unknown native NET child')
                refs=conn[1:]
                if array:
                    require(refs and refs[0][0]=='NETREF','native array NETREF missing')
                    net=clm.endpoints.indexed(refs[0][1]);refs=refs[1:]
                else:net=clm.endpoints.indexed(node[1])
                for p in refs:
                    require(p[0]=='PORTREF','unknown native connect')
                    if len(p)==2:continue
                    require(len(p)==3 and p[2][0]=='INSTREF','native connect shape')
                    inst=canon(p[2][1])
                    if inst not in wanted:continue
                    key=inst,clm.endpoints.indexed(p[1]);require(key not in pins,'native pin connected twice');pins[key]=net
        active=None;held=[]
    require(depth==0 and active is None and set(instances)==set(wanted),'incomplete native route selection')
    definitions={}
    for name in {v['Cell']for v in instances.values()}:
        require(name in cells,'native CELL absent');node=cells[name]
        views=[v for v in node[3:]if v[0]=='VIEW'];require(len(views)==1 and views[0][1]=='OPER','native VIEW shape')
        interfaces=[v for v in views[0][2:]if v[0]=='INTERFACE'];require(len(interfaces)==1,'native INTERFACE shape')
        ports={}
        for p in interfaces[0][1:]:
            require(p[0]=='PORT','unknown native INTERFACE child');name0=p[1]
            directions=[x[1]for x in p[2:]if x[0]=='DIRECTION'];require(len(directions)==1 and directions[0]in ('INPUT','OUTPUT','INOUT'),'native direction shape')
            if isinstance(name0,list):
                require(len(name0)==4 and name0[0]=='ARRAY'and all(re.fullmatch(r'\d+',x)for x in name0[2:]),'unsupported native port ARRAY')
                hi,lo=map(int,name0[2:]);step=-1 if hi>=lo else 1
                names=[canon(name0[1])+f'[{i}]'for i in range(hi,lo+step,step)]
            else:names=[canon(name0)]
            for port in names:require(port not in ports,'duplicate native interface pin');ports[port]=directions[0]
        definitions[name]={'Operator':node[2][1],'Ports':ports,'Parameters':[x for x in node[3:]if x[0]=='PARAMETER']}
    for inst,value in instances.items():require(definitions[value['Cell']]['Operator']==value['Operator'],'native operator differs')
    for (inst,pin),net in pins.items():require(pin in definitions[instances[inst]['Cell']]['Ports'],'native pin outside interface')
    return {'Cells':definitions,'Instances':instances,'Pins':pins}


def exact_scopes(g,rows,mapper):
    mapped=[];scopes={}
    for index,row in enumerate(rows):
        try:
            item=mapper.map(row)
            parent=raw.parent(row['SourceFF']);placement=item['SourcePlacement']
            slot=re.search(r'/(FFAPP|FF)([0-3])/FF$',row['SourceFF'])
            require(slot is not None,'unknown FF physical slot')
            physical=placement['Site']+('/CR'if slot[1]=='FFAPP'else'/Q')+slot[2]
            item.update(SourcePhysicalQ=physical,SourceNativeCLKNet=mapper.route['Pins'][parent,'CLK'])
            mapped.append(item)
            if row['Role']in ('unclassified','async_reset_requires_guard_review'):continue
            source_period=g.clock(g.ff[row['SourceFF']]['Ports']['CK'])['PeriodNS']
            destination_period=g.clock(g.ff[row['DestinationFF']]['Ports']['CK'])['PeriodNS']
            maximum=source_period if row['Role']=='gray_first_stage'else destination_period
            for boundary in item['NativeBoundaries']:
                key=item['SourceNativeClockPin'],item['SourceNativeOutputPin'],boundary['Endpoint']
                scope=scopes.setdefault(key,{'FromCLK':key[0],'LaunchQ':key[1],'Endpoint':key[2],
                    'Role':row['Role'],'Roles':[],'MaximumNS':maximum,
                    'BoundBasis':'Gray source-period bound'if row['Role']=='gray_first_stage'else
                    'Proposed one destination period; protocol/settling acceptance remains required',
                    'RelationshipIndexes':[],'NativeObjects':{k:[]for k in
                    ('SourceFFs','DestinationFFs','SourcePhysicalQ','SourceCLKNet')}})
                scope['MaximumNS']=min(scope['MaximumNS'],maximum);scope['RelationshipIndexes'].append(index)
                scope['Roles'].append(row['Role'])
                for key2,value in [('SourceFFs',row['SourceFF']),('DestinationFFs',row['DestinationFF']),
                                   ('SourcePhysicalQ',physical),('SourceCLKNet',item['SourceNativeCLKNet'])]:
                    scope['NativeObjects'][key2].append(value)
        except (ValueError,KeyError) as e:
            g.findings.add('NativeRelationshipMappingIncomplete',row['SourceFF']+' -> '+row['DestinationFF']+'/'+row['DestinationPin'],e)
            mapped.append({**row,'NativeMappingError':str(e)})
    for row in scopes.values():
        row['Roles']=sorted(set(row['Roles']));row['RelationshipIndexes']=sorted(set(row['RelationshipIndexes']))
        row['NativeObjects']={k:sorted(set(v))for k,v in row['NativeObjects'].items()}
    return mapped,[scopes[k]for k in sorted(scopes)]


def source_sampling(g):
    rows=[]
    for pad in PADS:
        if pad in UNUSED_RGB:
            refs=g.scalar_refs.get(pad,[])
            if refs:g.findings.add('DiscardedRGBPadConsumer',pad,refs)
            rows.append({'Port':pad,'Disposition':'RGB565_quantization_no_native_consumer','ConsumerCount':len(refs)});continue
        terminals=[];pending=[pad];seen=set()
        while pending:
            net=pending.pop()
            if net in seen:continue
            seen.add(net)
            for n,p in g.scalar_refs.get(net,[]):
                c=g.cells[n];direction=g.models[c['Primitive']]['Ports'].get(p)
                if direction=='OUTPUT':continue
                if n in g.ff:terminals.append((n,p));continue
                if c['Primitive']not in ('V_IBUF','V_BUF','V_INV'):
                    g.findings.add('UnsampledPixelPadConsumer',pad,n+'/'+p);continue
                for op,value in c['Ports'].items():
                    if g.models[c['Primitive']]['Ports'].get(op)=='OUTPUT':pending+=atoms(value)
        terminals=sorted(set(terminals));valid=len(terminals)==1 and terminals[0][1]=='D'
        if not valid:g.findings.add('PixelSamplerNotUnique',pad,terminals)
        row={'Port':pad,'Disposition':'single_native_sampling_FF'if valid else'unresolved','NativeTerminals':terminals}
        if valid:
            n=terminals[0][0];row.update(FF=n,ActualQ=ff_identity(g,n),Clock=g.clock(g.ff[n]['Ports']['CK']),
                Placement=g.g['FFPlacement'][n],Parameters=g.ff[n]['Parameters'])
            if row['Clock']['Domain']!='input_pixel':g.findings.add('PixelSamplerClock',pad,row['Clock'])
        rows.append(row)
    return {'DeclaredBundleBits':len(PADS),'DiscardedRGBBits':sorted(UNUSED_RGB),
        'ActualSamplingFFCount':sum(r['Disposition']=='single_native_sampling_FF'for r in rows),
        'Bits':rows,'ExternalACAccepted':False,'PixelOpticalAcceptanceClaimed':False}


def abstract_value(g,value,fixed_ff,cache,active=()):
    """Sound Boolean over-approximation; lost correlations can only fail proof."""
    net=canon(value)
    if net in ("1'b0","1'b1"):return frozenset({int(net[-1])})
    if net in cache:return cache[net]
    require(net not in active,'cycle in local guard Boolean cone')
    drivers=g.scalar_outputs.get(net,[])
    if len(drivers)!=1:return frozenset({0,1})
    name,pin=drivers[0];c=g.cells[name];p=c['Ports'];kind=c['Primitive']
    child=lambda n:abstract_value(g,n,fixed_ff,cache,active+(net,))
    if name in g.ff:values=frozenset({fixed_ff[name]})if name in fixed_ff else frozenset({0,1})
    elif kind in ('V_BUF','V_IBUF'):values=child(p['I'])
    elif kind=='V_INV':values=frozenset(1-x for x in child(p['I']))
    elif kind=='V_MUX2':values=frozenset(v for s in child(p['SEL'])for v in child(p['I'+str(s)]))
    elif kind=='V_LUT6CARRY':
        names=sorted({p[x]for x in ('I0','I1','I2','I3','I4','I5','CIN')})
        values=frozenset(monitor.lut_value(c,pin,dict(zip(names,bits)))
            for bits in itertools.product(*(child(n)for n in names)))
    else:values=frozenset({0,1})
    cache[net]=values;return values


def forced_next_q(g,name,fixed_ff,cache=None):
    c=g.ff[name];p=c['Ports'];parameters=c['Parameters'];cache={}if cache is None else cache
    require(c['Primitive']in ('V_FFSYN','V_FFASYN'),'unknown FF transition model')
    lrs=parameters.get('LRS_EN','"FALSE"');polarity=parameters.get('SET_RESET','"SET"')
    require(lrs in ('"TRUE"','"FALSE"')and polarity in ('"SET"','"RESET"'),'unknown native CE/SR priority parameters')
    sr=abstract_value(g,p['SR'],fixed_ff,cache)if lrs=='"TRUE"'else {0}
    ce=abstract_value(g,p['CE'],fixed_ff,cache);data=abstract_value(g,p['D'],fixed_ff,cache)
    old={fixed_ff[name]}if name in fixed_ff else {0,1}
    values={int(polarity=='"SET"')if s else d if e else q
        for s,e,d,q in itertools.product(sr,ce,data,old)}
    return next(iter(values))if len(values)==1 else None


def local_reset_guards(g,relationships):
    guard_names=['input_sampler/p_reset[1]','system/core_reset_sync[1]',CAP+'pix_reset[1]',CAP+'sys_reset[1]',
        CAP+'pixels/wr_reset_sync[1]',CAP+'pixels/rd_reset_sync[1]',
        'system/display_fifo/wr_reset_sync[1]','system/display_fifo/rd_reset_sync[1]',OUT+'reset_sync[1]']
    guards=[]
    for net in guard_names:
        support={n for kind,n in g.support(net)if kind=='ff'}
        if len(support)!=1:guards.append({'LogicalRelease':net,'BindingVerified':False});continue
        source=next(iter(support));possibilities=[]
        for physical in (0,1):
            if abstract_value(g,net,{source:physical},{})==frozenset({0}):possibilities.append(physical)
        if len(possibilities)!=1:guards.append({'LogicalRelease':net,'BindingVerified':False});continue
        guards.append({'LogicalRelease':net,'BindingVerified':True,'ReleaseFF':source,
            'InactivePhysicalQ':possibilities[0],'Clock':g.clock(g.ff[source]['Ports']['CK'])['Domain']})
    candidates=sorted({r['DestinationFF']for r in relationships if r['Role']=='async_reset_requires_guard_review'})
    caches={};rows=[]
    for name in candidates:
        domain=g.clock(g.ff[name]['Ports']['CK'])['Domain'];proofs=[]
        for guard in guards:
            if not guard['BindingVerified']or guard['Clock']!=domain or guard['ReleaseFF']==name:continue
            fixed={guard['ReleaseFF']:guard['InactivePhysicalQ']};key=guard['LogicalRelease']
            try:forced=forced_next_q(g,name,fixed,caches.setdefault(key,{}))
            except ValueError:forced=None
            if forced is not None:proofs.append({'LogicalRelease':key,'InactivePhysicalQ':guard['InactivePhysicalQ'],
                'ReleaseFF':guard['ReleaseFF'],'NativeForcedQ':forced})
        rows.append({'FF':name,'Clock':domain,'NativeInactiveGuardProofs':proofs,'NativeNextQForced':bool(proofs),
            'ResetExceptionAccepted':False,'ReleaseChainAndConsumersAccepted':False})
    return {'Verified':False,'ResetScopeVerified':False,'GuardBindings':guards,'ConsumerRows':rows,
        'NativeResetRelationshipCount':sum(r['Role']=='async_reset_requires_guard_review'for r in relationships),
        'UniqueAsyncResetConsumers':len(rows),'NativeInactiveForcedConsumers':sum(r['NativeNextQForced']for r in rows),
        'Limits':'Native SR precedes CE. Forced physical Q is not a logical reset value or a power-up/GRS claim. '
                 'Release-chain safety, coordinated reset and timed interstage/consumer release remain independently required.'}


def derive(build_plan,export_receipt,route_receipt):
    build_plan=Path(build_plan).resolve();export_receipt=Path(export_receipt).resolve();route_receipt=Path(route_receipt).resolve()
    watched={}
    for path in static_helpers():native.add(watched,path)
    imported_runtime(watched)
    initial=dict(watched);plan=build.validate(build_plan)
    exported,inputs=native.bind_receipt(export_receipt);native.merge(watched,inputs)
    routed,inputs=native.bind_receipt(route_receipt);native.merge(watched,inputs)
    require(exported['Mode']=='export' and routed['Mode']in ('report','query') and
        all(exported[k]==routed[k]for k in ('BuildPlanSHA256','SourceADFSHA256','SourceADF')) and
        exported['BuildPlanSHA256']==sha(build_plan),'pixel export/route lineage differs')
    net=native.artifact(export_receipt,exported,TARGET+'_sim.v');dump=native.artifact(route_receipt,routed,'route-dump.txt')
    native.add(watched,net);native.add(watched,dump)
    text=net.read_text(encoding='utf-8-sig');parsed=functional(text)
    models=load_models({c['Primitive']for c in parsed['Cells'].values()},watched)
    source=build_plan.parent/'compiled'/build.TOP;ports=build.top_ports(source.read_text(encoding='utf-8-sig'))
    fdcpath=build_plan.parent/'compiled'/build.FDC;native.add(watched,fdcpath)
    clocks=clock_definitions(fdcpath.read_text());g=PixelGraph(parsed,ports,clocks,models)
    pins=pin_inventory(build_plan.parent,g,plan,watched);sampling=source_sampling(g)
    aliases=rtl_alias_inventory(build_plan.parent,g,watched)
    chains,gray=discover_chains(g);rows,other,clock_counts=crossing_inventory(g,chains)
    guards=local_reset_guards(g,rows)
    placements=clm.placed_luts(text,g)
    parents={raw.parent(n)for row in rows for n in (row['SourceFF'],row['DestinationFF'])}
    parents.update(n.rsplit('/',2)[0]for n in placements)
    with tempfile.TemporaryDirectory(prefix='hdmi-pixel-audit-')as temporary:
        normalized=Path(temporary)/'route.adif';normalization=calibrated.normalize_source_locations(dump,normalized)
        route=native_route(normalized,parents)
    mapper=PixelMapper(g,route,placements);mapped,scopes=exact_scopes(g,rows,mapper)
    g.findings.add('LocalResetGuardReviewIncomplete','all foreign async reset consumers',
        'No reset exception is proposed. Per-native-FF next-Q/cofactor and coordinated release proof required.')
    g.findings.add('ProtocolNativeReviewIncomplete','held/scalar/Gray roles',
        'Candidate role inventory is not a native next-state, hold, Gray one-bit or synchronizer fanout proof.')
    for row in other:
        if row['SourceKind']=='unresolved':g.findings.add('UnresolvedSequentialSupport',row['DestinationFF']+'/'+row['DestinationPin'],row['Source'])
    for path,expected in initial.items():require(sha(path)==expected,'pixel audit helper/runtime changed during derivation: '+str(path))
    result={'Schema':SCHEMA,'Target':TARGET,'BuildPlan':native.ref(build_plan),'ExportReceipt':native.ref(export_receipt),
        'RouteReceipt':native.ref(route_receipt),'SourceADF':native.ref(exported['SourceADF']),
        'NativeNetlist':native.ref(net),'RouteDump':native.ref(dump),'Pins':pins,'ClockDefinitions':list(clocks.values()),
        'ClockTopology':{'FFCountsByClock':clock_counts,'ResolvedNativeNets':g.clock_cache},
        'ActualCells':len(g.cells),'ActualFFs':len(g.ff),'PrimitiveCounts':dict(sorted(Counter(c['Primitive']for c in g.cells.values()).items())),
        'SourceSampling':sampling,'PrimitiveBoundaries':list(g.macro_rows.values()),'Synchronizers':chains,'GrayGroups':gray,
        'LogicalAliasRecovery':aliases,
        'ProtocolInventory':{'CandidateRoles':dict(sorted(Counter(r['Role']for r in rows).items())),'NativeAcceptanceComplete':False},
        'ForeignRelationships':mapped,'NonFFSequentialSupport':other,
        'LocalResetGuards':guards,
        'NativeRouteNormalization':normalization,'DataScopes':scopes,'ResetScopes':[],'Blockers':g.findings.rows,
        'ProposalReady':not g.findings.rows,'ConstraintsApplied':False,'TimingAccepted':False,'HardwareReleaseAllowed':False,
        'HardwareAccessed':False,'BitstreamRequested':False,'InputSHA256':{str(p):h for p,h in sorted(watched.items(),key=lambda x:str(x[0]))},
        'Limits':'Unapplied CPU inventory. Candidate scopes require independent protocol, reset, primitive, query and final native timing acceptance.'}
    return result,watched


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('build-plan','export-receipt','route-receipt','output-dir'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args(argv);out=build.work_path(args.output_dir);out.mkdir(parents=True,exist_ok=True)
    value,_=derive(args.build_plan,args.export_receipt,args.route_receipt);write(out/'proposal.json',value)
    print(json.dumps({'Proposal':str(out/'proposal.json'),'ProposalReady':value['ProposalReady'],
        'ForeignRelationships':len(value['ForeignRelationships']),'DataScopes':len(value['DataScopes']),
        'Blockers':len(value['Blockers']),'ConstraintsApplied':False}))
    return 0


if __name__=='__main__':raise SystemExit(main())
