"""Trace checked-I2C connectivity in a flat native functional netlist.

This audits cell connections, not names merely appearing in text. Export/ADF
provenance remains a separate required audit; no timing or hardware acceptance.
"""
from pathlib import Path
from collections import defaultdict
from itertools import product
import argparse
import hashlib
import json
import re

LIBRARY = Path('D:/pango/PDS_2023.2/arch/vendor/pango/verilog/bsim')
IDENT = r'(?:\\[^\s,{}()]+|[A-Za-z_]\w*)'
ATOM = re.compile(IDENT + r'(?:\s+\[\d+\]|\[\d+\])?|\d+\x27[bhd][0-9a-fxz_]+', re.I)
CELL = re.compile(r'\s*(V_\w+)\s*(?:#\s*\((.*?)\)\s*)?(' + IDENT + r')\s*\((.*?)\)\s*;', re.S)
PAIR = re.compile(r'\.(\w+)\s*\(([^()]*)\)', re.S)
FFS = ('V_FFASYN', 'V_FFSYN')
SEMANTICS_SHA256 = {
    'V_BUF': '774fb1a08820223eef6c66217e510d3a5eb328edebffb488a25467fe3e623836',
    'V_INV': 'b1242601ab1cc80fbc152a149eaf3d73b140e541392d8af727260cadc7b378ef',
    'V_IBUF': '18814ef6d6f140b763c88871640498cacfaa420f4e5038b4fc751beedf69d4f4',
    'V_OBUFT': 'cfc024e819351fe3dd04cabd22f2860c5eac6d528f413c78ab56b1b0f2dd8017',
    'V_FFASYN': 'e2fcf0de9085fd056c4daa14b2f73bd9235cdb52c90e68a2b58114024e048b24',
    'V_FFSYN': 'ae4094a9a478a8ae9e5c67a0fcf982ff1e61a6e1e66588d849dd815d713c1f8c',
    'V_LUT6CARRY': 'aa7ca57e8ce35845b0d61b02358d4a546facc52be65ec1ca5e68fe37a8bdcf98',
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clean(text):
    return re.sub(r'/\*.*?\*/|//[^\n]*|\(\*.*?\*\)', '', text, flags=re.S)


def canonical(token):
    token = token.strip()
    if token.startswith('\\'):
        parts = token[1:].split()
        return '\\' + (parts[0] if len(parts) == 1 else parts[0] + '::' + ''.join(parts[1:]))
    return re.sub(r'\s+', '', token)


def atoms(expression):
    matches = list(ATOM.finditer(expression))
    remain = ATOM.sub('', expression)
    require(not re.sub(r'[\s{},]', '', remain), 'unsupported connection expression: ' + expression)
    return [canonical(m[0]) for m in matches]


def scalar(expression):
    values = atoms(expression)
    require(len(values) == 1 and not any(c in expression for c in '{},'), 'scalar connection required')
    return values[0]


def constant(net):
    if re.fullmatch(r"1'[bh]0", net, re.I): return 0
    if re.fullmatch(r"1'[bh]1", net, re.I): return 1
    return None


def pairs(text):
    matches = list(PAIR.finditer(text or ''))
    require(not re.sub(r'[\s,]', '', PAIR.sub('', text or '')), 'unsupported named port or parameter')
    require(len({m[1] for m in matches}) == len(matches), 'duplicate named port or parameter')
    return {m[1]: m[2].strip() for m in matches}


def interface(text, name):
    text = clean(text)
    match = re.search(r'\bmodule\s+' + re.escape(name) + r'\s*(?:#\s*\(.*?\)\s*)?\((.*?)\)\s*;', text, re.S)
    require(match is not None, 'primitive interface missing: ' + name)
    result, direction = {}, None
    for item in match[1].split(','):
        declaration = re.fullmatch(r'\s*(?:(input|output|inout)\s+)?(?:wire\s+|reg\s+)?'
            r'(?:\[[^\]]+\]\s*)?(\w+)\s*', item)
        require(declaration is not None, 'unsupported primitive declaration: ' + name)
        direction = declaration[1] or direction
        require(direction is not None and declaration[2] not in result, 'ambiguous primitive port')
        result[declaration[2]] = direction
    return result


def parse(text, library):
    require('2023.2-SP3<build 154097>' in text[:300], 'native netlist version differs')
    text = clean(text)
    header = re.match(r'\s*module\s+board1080_top\s*\([^;]*\);', text)
    require(header is not None and len(re.findall(r'\bmodule\b', text)) == 1, 'flat board1080_top required')
    text = text[header.end():]
    require(text.rstrip().endswith('endmodule'), 'netlist is incomplete')
    text = text[:text.rfind('endmodule')]
    cells, ports, offset = {}, {}, 0
    statement = re.compile(r'\s*(input|output|inout|wire)\s+([^;]+);')
    whitespace = re.compile(r'\s*')
    while offset < len(text):
        offset = whitespace.match(text, offset).end()
        if offset == len(text): break
        declaration = statement.match(text, offset)
        if declaration:
            if declaration[1] != 'wire':
                names = re.sub(r'^\s*\[[^\]]+\]\s*', '', declaration[2])
                for name in names.split(','):
                    name = canonical(name)
                    require(name not in ports, 'duplicate top port')
                    ports[name] = declaration[1]
            offset = declaration.end(); continue
        match = CELL.match(text, offset)
        require(match is not None, 'unsupported native statement near offset ' + str(offset))
        name = canonical(match[3])
        require(name not in cells, 'duplicate cell name')
        cells[name] = dict(Type=match[1], Parameters=pairs(match[2]), Ports=pairs(match[4]))
        offset = match.end()
    drivers, libraries, directions = defaultdict(list), {}, {}
    for typ in {c['Type'] for c in cells.values()}:
        path = library / (typ + '.v')
        digest = sha(path)
        if typ in SEMANTICS_SHA256:
            require(digest == SEMANTICS_SHA256[typ], 'interpreted primitive semantics changed: ' + typ)
        libraries[str(path.resolve())] = digest
        directions[typ] = interface(path.read_text(encoding='utf-8-sig'), typ)
    for name, cell in cells.items():
        directions_here = directions[cell['Type']]
        require(set(cell['Ports']) <= set(directions_here), 'unknown primitive port: ' + name)
        for port, connection in cell['Ports'].items():
            if directions_here[port] in ('output', 'inout'):
                for net in atoms(connection): drivers[net].append((name, port))
    return cells, ports, drivers, libraries


def analyze(path, library=LIBRARY):
    path, library = Path(path).resolve(), Path(library).resolve()
    digest = sha(path)
    cells, ports, drivers, libraries = parse(path.read_text(encoding='utf-8-sig'), library)
    traced = set()

    def one(net):
        require(len(drivers.get(net, [])) == 1, 'missing or multiple drivers: ' + net)
        name, port = drivers[net][0]
        traced.add(name)
        return name, port, cells[name]

    def trace(net):
        seen, steps = set(), []
        while constant(net) is None:
            require(net not in seen, 'buffer cycle')
            seen.add(net)
            if ports.get(net) == 'input':
                require(not drivers.get(net), 'input port has an internal driver')
                break
            name, port, cell = one(net)
            if cell['Type'] != 'V_BUF': break
            require(port == 'Z' and set(cell['Ports']) == {'Z','I'}, 'buffer interface differs')
            steps.append(name); net = scalar(cell['Ports']['I'])
        return net, steps

    def ff(name):
        cell = cells[name]
        require(cell['Type'] in FFS and '/driver/' in name, 'checked driver FF required')
        require(set(cell['Ports']) == {'Q','D','CK','CE','SR'}, 'FF interface differs')
        require(constant(trace(scalar(cell['Ports']['CE']))[0]) == 1, 'sampling FF must be always enabled')
        require(one(scalar(cell['Ports']['Q']))[:2] == (name,'Q'), 'FF Q driver differs')
        return name, cell

    buffers = [(n,scalar(c['Ports']['I']),scalar(c['Ports']['Z'])) for n,c in cells.items()
               if c['Type'] == 'V_BUF']

    def next_ff(net):
        reachable = {net}
        while True:
            added = {output for name,input_net,output in buffers if input_net in reachable}
            if added <= reachable: break
            reachable |= added
        matches = [n for n,c in cells.items() if c['Type'] in FFS and scalar(c['Ports']['D']) in reachable]
        require(len(matches) == 1, 'one FF must receive the synchronizer stage')
        name, cell = ff(matches[0])
        require(trace(scalar(cell['Ports']['D']))[0] == net, 'synchronizer buffer graph differs')
        return name, cell

    def expression(net, stack=()):
        require(len(stack) < 64 and net not in stack, 'combinational cycle or excessive cone depth')
        value = constant(net)
        if value is not None: return ('constant',value)
        name, port, cell = one(net)
        typ, cp, params = cell['Type'], cell['Ports'], cell['Parameters']
        child = lambda pin: expression(scalar(cp[pin]), stack+(net,))
        if typ in FFS and port == 'Q': return ('variable',net)
        if typ == 'V_BUF' and port == 'Z': return child('I')
        if typ == 'V_INV' and port == 'Z': return ('invert',child('I'))
        require(typ == 'V_LUT6CARRY' and port in ('Z','Z5'), 'unsupported logic in output cone: '+name)
        require(set(cp) == {'COUT','Z','Z5','CIN','I0','I1','I2','I3','I4','I5'}, 'LUT ports differ')
        match = re.fullmatch(r"64'h([0-9a-fA-F_]+)",params.get('INIT',''))
        require(match is not None and len(match[1].replace('_','')) == 16, 'exact 64-bit LUT INIT required')
        init = int(match[1].replace('_',''),16)
        require(params.get('I5_TO_LUT','"FALSE"') in ('"TRUE"','"FALSE"'), 'LUT input selector differs')
        inputs = [child('I'+str(i)) for i in range(5)]
        if port == 'Z': inputs.append(child('I5' if params.get('I5_TO_LUT','"FALSE"')=='"TRUE"' else 'CIN'))
        return ('lut',init,inputs)

    def variables(expr):
        if expr[0] == 'variable': return {expr[1]}
        if expr[0] == 'constant': return set()
        if expr[0] == 'invert': return variables(expr[1])
        return set().union(*(variables(e) for e in expr[2]))

    def evaluate(expr, values):
        if expr[0] == 'constant': return expr[1]
        if expr[0] == 'variable': return values[expr[1]]
        if expr[0] == 'invert': return 1-evaluate(expr[1],values)
        index = sum(evaluate(e,values)<<i for i,e in enumerate(expr[2]))
        return (expr[1]>>index)&1

    def truth(expr):
        names = sorted(variables(expr))
        require(len(names) <= 8, 'output cone exceeds exhaustive truth-table bound')
        return [dict(Inputs=dict(zip(names,values)),Output=evaluate(expr,dict(zip(names,values))))
                for values in product((0,1),repeat=len(names))]

    result = {}
    for bus in ('scl','sda'):
        pad = 'hd_' + bus
        require(ports.get(pad) == 'inout', 'checked pad must be inout: ' + pad)
        out_name, out_port, out = one(pad)
        require(out['Type'] == 'V_OBUFT' and out_port == 'O' and set(out['Ports']) == {'O','I','T'},
                'single tri-state output buffer required: ' + pad)
        data_truth = truth(expression(scalar(out['Ports']['I'])))
        require(all(row['Output'] == 0 for row in data_truth), 'open-drain output data is not constant zero')
        ibufs = [(n,c) for n,c in cells.items() if c['Type']=='V_IBUF' and scalar(c['Ports']['I'])==pad]
        require(len(ibufs)==1, 'one physical input buffer required per pad')
        in_name, ibuf = ibufs[0]
        meta_name, meta = next_ff(scalar(ibuf['Ports']['O']))
        sampled_name, sampled = next_ff(scalar(meta['Ports']['Q']))
        first, read_buffers = trace(scalar(meta['Ports']['D']))
        in_name, in_port, ibuf = one(first)
        require(ibuf['Type'] == 'V_IBUF' and in_port == 'O' and set(ibuf['Ports']) == {'O','I'} and
                scalar(ibuf['Ports']['I']) == pad, 'pad does not drive first synchronizer input')
        second, sync_buffers = trace(scalar(sampled['Ports']['D']))
        require(second == scalar(meta['Ports']['Q']), 'second synchronizer bypasses first register')
        sampling_clock = trace(scalar(meta['Ports']['CK']))[0]
        require(constant(sampling_clock) is None and
                sampling_clock == trace(scalar(sampled['Ports']['CK']))[0],
                'synchronizer clocks differ')
        require(trace(scalar(meta['Ports']['SR']))[0] == trace(scalar(sampled['Ports']['SR']))[0],
                'synchronizer reset nets differ')
        require(constant(trace(scalar(meta['Ports']['SR']))[0]) is None,
                'synchronizer reset tied to a constant')
        for sample in (meta,sampled):
            require(sample['Parameters'].get('SET_RESET')=='"SET"' and
                    sample['Parameters'].get('LRS_EN')=='"TRUE"' and
                    constant(sample['Parameters'].get('INIT',''))==1, 'synchronizer reset configuration differs')
        lows = [n for n,c in cells.items() if c['Type'] in FFS and
                re.search(r'(?:^|/)driver/'+bus+r'_low(?:_vname)?(?:/|$)',n)]
        require(len(lows)==1, 'one native low control register required')
        low_name, low = ff(lows[0])
        low_q = scalar(low['Ports']['Q'])
        require(low['Parameters'].get('SET_RESET')=='"RESET"' and
                low['Parameters'].get('LRS_EN')=='"TRUE"' and
                constant(low['Parameters'].get('INIT',''))==0, 'low-control reset configuration differs')
        control_truth = truth(expression(scalar(out['Ports']['T'])))
        require(all(low_q in row['Inputs'] and row['Output']==1-row['Inputs'][low_q] for row in control_truth),
                'tri-state disable is not exactly inverse low FF Q')
        require(trace(scalar(low['Ports']['CK']))[0] == sampling_clock,
                'control and sampling clock nets differ')
        result[pad] = dict(InputBuffer=in_name, MetaFF=meta_name, SampledFF=sampled_name,
            SamplingClockNet=sampling_clock, MetaFFParameters=meta['Parameters'],
            SampledFFParameters=sampled['Parameters'],
            PadToMetaBuffers=read_buffers, MetaToSampledBuffers=sync_buffers,
            OutputBuffer=out_name, OutputDataConstant=0, OutputDataTruthTable=data_truth,
            TristateControlFF=low_name, TristateControlTruthTable=control_truth,
            NativeQToDisableTruthTable=[1,0],
            NativeControlFFParameters=low['Parameters'],
            NativeControlRegisterPolarityRelativeToRTLVerified=False)
    evidence = {str(path):digest, **libraries, str(Path(__file__).resolve()):sha(__file__)}
    require(all(sha(p) == h for p,h in evidence.items()), 'netlist or primitive definitions changed during audit')
    return dict(Schema='checked-io-flat-netlist-connectivity-v1', DiagnosticOnly=True,
        NativeConnectivityVerified=True, ParsedCells=len(cells), Buses=result,
        TracedCells={n:cells[n] for n in sorted(traced)}, EvidenceSHA256=evidence,
        ExportADFProvenanceVerified=False, PhysicalImplementationAccepted=False,
        ExternalPullupsVerified=False, TimingAccepted=False, HardwareReleaseAllowed=False,
        Limitations=['Export execution and exact current ADF provenance must be verified separately.',
            'Native low-register Q polarity relative to RTL is recorded, not inferred from its name.',
            'Structural connectivity does not prove external voltage, pullups, timing or hardware behavior.'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--netlist', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    require(not args.output.exists(), 'output must be new')
    result = analyze(args.netlist)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False); stream.write('\n')
    print(json.dumps({k: result[k] for k in ('NativeConnectivityVerified','ExportADFProvenanceVerified',
                                           'PhysicalImplementationAccepted','HardwareReleaseAllowed')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
