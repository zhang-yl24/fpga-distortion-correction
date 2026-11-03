"""Bound vendor-model bit/port selection for current fisheye arithmetic/RAMs.

The caller supplies its actual native graph. Unused bits are derived from
primitive modes and output consumers, never from an instance prefix or an old
count. Unknown bits on selected functional inputs remain blocking issues.
"""
from pathlib import Path
import hashlib
import itertools
import re

SELF=Path(__file__).resolve()
MODEL_SHA={'V_APM_E2':'b2403492e98454365e6cfaed681cbef2902cbe8a378cb693a0c3cfbbee35e48c',
 'V_DRM18K_E1':'c7c271c7c372ccd9f7e3701db5a79a94e106ac28b7b735c60f3a8f43d78429da',
 'V_DRM36K_E1':'224ad428a209ba704b58c24a505b9290648a95e4ae585494b80296bc9e0f1c96'}
APM_WIDTH={'X':30,'Y':18,'XB':25,'CXI':30,'CXBI':25,'Z':48,'CPI':48,
 'P':48,'CPO':48,'COUT':1,'CXO':30,'CXBO':25,'MODEIN':5,'MODEY':3,'MODEZ':4}


def require(value,message):
    if not value:raise ValueError(message)


def bits(value,width):
    """Return MSB-first native scalar tokens without dropping X or constants."""
    value=re.sub(r'\s+','',str(value)).replace('\\','')
    if not value:return []
    if value.startswith('{'):
        require(value.endswith('}')and'{'not in value[1:]and'}'not in value[:-1],
            'unreviewed nested native concatenation')
        result=[]
        for part in value[1:-1].split(','):
            literal=re.match(r"(\d+)'",part);span=re.fullmatch(r'(.+)\[(\d+):(\d+)\]',part)
            part_width=int(literal[1])if literal else abs(int(span[2])-int(span[3]))+1 if span else 1
            result+=bits(part,part_width)
        require(len(result)==width,'native concatenation width differs');return result
    m=re.fullmatch(r"(\d+)'(?:s)?([bhd])([0-9a-fxz_]+)",value,re.I)
    if m:
        n,base,data=int(m[1]),m[2].lower(),m[3].replace('_','').lower()
        require(n==width or width==1,'native literal width differs')
        if base=='b':binary=data
        elif base=='h':binary=''.join((c*4 if c in'xz'else f'{int(c,16):04b}')for c in data)
        else:require(not any(c in'xz'for c in data),'unknown decimal constant');binary=f'{int(data):b}'
        binary=binary[-n:].rjust(n,'0')
        return ["1'b"+c for c in binary]
    m=re.fullmatch(r'(.+)\[(\d+):(\d+)\]',value)
    if m:
        hi,lo=int(m[2]),int(m[3]);step=-1 if hi>=lo else 1
        result=[m[1]+f'[{i}]'for i in range(hi,lo+step,step)]
        require(len(result)==width,'native range width differs');return result
    if width==1:return[value]
    # A full named bus is legal only when its declared model width supplies
    # the bit indices; this never turns an unknown constant into a primary.
    require(re.fullmatch(r'[A-Za-z_$][\w$./\[\]-]*',value),'unparsed native bus')
    return [value+f'[{i}]'for i in range(width-1,-1,-1)]


def possible(expr):
    kind=expr[0]
    if kind=='constant':return{int(expr[1])}
    if kind=='variable':return{0,1}
    if kind=='not':return{1-v for v in possible(expr[1])}
    if kind=='mux':return set.union(set(),*(possible(expr[1+v])for v in possible(expr[3])))
    if kind=='lut':
        return{(expr[1]>>sum(v<<i for i,v in enumerate(row)))&1
            for row in itertools.product(*(possible(x)for x in expr[2]))}
    raise ValueError('unknown constant-proof expression')


def constant(g,value):
    token=str(value).replace('\\','').strip()
    if token in("1'b0","1'b1"):return int(token[-1])
    require('x'not in token.lower()or not re.fullmatch(r"\d+'[bh].*",token,re.I),'X is not a constant control')
    values=possible(g.expression(value));require(len(values)==1,'nonconstant selected control');return next(iter(values))


def number(g,value,width):
    result=0
    for token in bits(value,width):result=(result<<1)|constant(g,token)
    return result


def widths(cell):
    if cell['Primitive']=='V_APM_E2':return APM_WIDTH
    big=cell['Primitive']=='V_DRM36K_E1'
    return {**{p:(16 if big else 14)for p in('ADDRA','ADDRB')},
        **{p:(36 if big else 18)for p in('DIA','DIB','DOA','DOB')},
        'BWEA':8 if big else 4,'BWEB':4 if big else 2,'CSA':3,'CSB':3,'ECC_RDADDR':9,'ECC_PARITY':8}


def output_users(g,cells):
    """Direct actual users; later filter cascade users by selected input bits."""
    result={}
    for name,c in cells.items():
        w=widths(c)
        for pin,direction in g.models[c['Primitive']]['Ports'].items():
            if direction!='OUTPUT'or not c['Ports'].get(pin):continue
            used=set();tokens=bits(c['Ports'][pin],w.get(pin,1))
            for index,net in enumerate(reversed(tokens)):
                if any((n,p)!=(name,pin)and g.models[g.cells[n]['Primitive']]['Ports'].get(p)=='INPUT'
                    for n,p in g.scalar_refs.get(net,[])):used.add(index)
            result[name,pin]=used
    return result


def apm_selection(g,c,used):
    p=c['Parameters'];ports=c['Ports'];selected={};why={}
    def use(pin,indexes=None):selected.setdefault(pin,set()).update(range(APM_WIDTH.get(pin,1))if indexes is None else indexes)
    def v(key):return int(p[key])
    require(v('USE_MULT')==1 and v('USE_PREADD')==0 and v('X_SEL')==0 and v('USE_SIMD')==0,
        'unreviewed arithmetic preadder/input/SIMD mode')
    require(all(v(k)==0 for k in('MODEIN_REG','MODEY_REG','MODEZ_REG','XB_REG','PREADD_REG')),
        'unreviewed registered arithmetic control or preadder mode')
    mi=number(g,ports['MODEIN'],5);my=number(g,ports['MODEY'],3);mz=number(g,ports['MODEZ'],4)
    require(mi==2 and my in(0,1)and mz in(0,2,3,6),'unreviewed arithmetic dynamic/constant operand selection')
    def mult():use('X',range(25));use('Y')
    def alu():
        if my&3==1:mult()
        elif my&3==3:use('X');use('Y')
        elif my&3==2:require(v('P_REG')==1,'unreviewed ALU feedback without output register')
        if mz&7==2:use('Z')
        elif mz&7 in(3,4,5,6,7):use('CPI')
        elif mz&7==1:require(v('P_REG')==1,'unreviewed ALU feedback')
        if v('CIN_SEL'):use('CIN')
    if used.get('P')or used.get('CPO'):
        if v('USE_POSTADD'):alu()
        else:mult()
    if used.get('COUT'):alu()
    if used.get('CXO'):use('X',used['CXO'])
    if used.get('CXBO'):
        if v('XB_SEL')&2:use('X',used['CXBO'])
        else:use('CXBI'if v('XB_SEL')&1 else'XB')
    for pin in('MODEIN','MODEY','MODEZ'):use(pin)
    regs={k:v(k)for k in('X_REG','Y_REG','MULT_REG','P_REG','CXO_REG','CPO_REG','XB_REG','PREADD_REG','MODEIN_REG','MODEY_REG','MODEZ_REG')}
    active_clock=any(regs.values())
    if active_clock:
        use('CLK')
        for pin in ports:
            if pin.startswith(('CE','RST')):use(pin)
    else:why['CLK']='All eleven native register-selection parameters are zero; selected outputs are combinational.'
    why['X[29:25]']='Multiplier uses25 low X bits; upper X bits are relevant only to actually consumed CXO bits or MODEY=3, which is rejected here.'
    if mz&7!=2:why['Z']='MODEZ selects zero/feedback/CPI, not Z; static MODEZ_REG=0.'
    return selected,why,{'RegisterParameters':regs,'ActiveClockRequired':active_clock,'MODEIN':mi,'MODEY':my,'MODEZ':mz}


def ram_selection(g,c,used):
    p=c['Parameters'];ports=c['Ports'];mode=p['RAM_MODE'].strip('"');wa,wb=int(p['DATA_WIDTH_A']),int(p['DATA_WIDTH_B'])
    require(mode in('TRUE_DUAL_PORT','SIMPLE_DUAL_PORT','SINGLE_PORT','ROM')and wa in(1,2,4,8,9,16,18,32,36,64,72)
        and wb in(1,2,4,8,9,16,18,32,36,64,72),'unknown native RAM mode/width')
    require(p.get('RAM_CASCADE','"NONE"')=='"NONE"'and p.get('ECC_READ_EN','"FALSE"')=='"FALSE"'
        and p.get('ECC_WRITE_EN','"FALSE"')=='"FALSE"','RAM cascade/ECC mode requires separate proof')
    require(all(int(p.get(k,'0'))==0 for k in('DOA_REG_CLKINV','DOB_REG_CLKINV')),
        'inverted RAM output register clock requires separate edge proof')
    require(all(p.get(k,'"NORMAL_WRITE"').strip('"')in('NORMAL_WRITE','TRANSPARENT_WRITE','READ_BEFORE_WRITE')
        for k in('WRITE_MODE_A','WRITE_MODE_B')),'unknown RAM read-during-write mode')
    sizes=widths(c);selected={};why={};facts={}
    def use(pin,indexes=None):
        if pin in ports:selected.setdefault(pin,set()).update(range(sizes.get(pin,1))if indexes is None else indexes)
    def data_positions(width):
        if width<16:return list(range(width))
        if width in(16,32,64):return[i for byte in range(width//8)for i in range(byte*9,byte*9+8)]
        return list(range(width))
    def data_a(width):
        positions=data_positions(width);part=sizes['DIA'];use('DIA',[i for i in positions if i<part])
        if max(positions)>=part:use('DIB',[i-part for i in positions if i>=part])
    for side,width in(('A',wa),('B',wb)):
        try:ce=constant(g,ports['CE'+side])
        except ValueError:ce=None
        disabled=ce==0 and int(p['DO'+side+'_REG'])==0
        read_only=(side=='B'and mode=='SIMPLE_DUAL_PORT')or mode=='ROM'
        try:we=constant(g,ports['WE'+side])
        except ValueError:we=None
        writes=not disabled and not read_only and we!=0
        read_output=bool(used.get('DO'+side))or(side=='B'and mode=='SIMPLE_DUAL_PORT'and wb>sizes['DOB']and bool(used.get('DOA')))
        reads=not disabled and (we!=1 or read_only)and read_output and not(side=='A'and mode=='SIMPLE_DUAL_PORT')
        facts[side]={'CEConstant':ce,'WEConstant':we,'DisabledByCEWithNoOutputReg':disabled,
            'ReadOnlyByMode':read_only,'CanWrite':writes,'UsedReadOutput':read_output,'CanReadUsedOutput':reads}
        if not writes and not reads:
            why[side+' port']='No enabled write and no enabled actual output read under current mode/CE/output registration.';continue
        use('CLK'+side);use('CE'+side);use('WE'+side);use('RST'+side);use('ORCE'+side);use('ADDR'+side+'_HOLD');use('CS'+side)
        low=0 if width==1 else 1 if width==2 else 2 if width==4 else 3 if width<=9 else 4 if width<=18 else 5 if width<=36 else 6
        use('ADDR'+side,range(low,15 if c['Primitive']=='V_DRM36K_E1'else 14));why['ADDR'+side+' low bits']=f'Native memory width{width} addresses use only upper bits starting at{low}.'
        if writes:
            if side=='A':data_a(width)
            else:use('DIB',data_positions(width))
            if width>=16:use('BWE'+side,range(width//(9 if width in(18,36,72)else 8)))
            else:why['BWE'+side]='Native mem_write width<=9 ignores byte_en.'
        else:why['DI'+side]='No write is possible on this port; data and byte enables are not functional inputs.'
    if mode=='SIMPLE_DUAL_PORT':why['BWEB']='Native SDP B port only reads; BWEB and DIB-as-B-write-data never used.'
    return selected,why,{'RAMMode':mode,'DataWidths':[wa,wb],'PortFacts':facts}


def review_macros(g):
    cells={n:c for n,c in g.cells.items()if c['Primitive']in MODEL_SHA};rows=[];issues=[]
    used=output_users(g,cells);selections={}
    for _ in range(len(cells)+1):
        current={}
        for name,c in cells.items():
            try:current[name]=(apm_selection if c['Primitive']=='V_APM_E2'else ram_selection)(g,c,
                {pin:positions for(n,pin),positions in used.items()if n==name})
            except(ValueError,KeyError)as e:current[name]=({}, {}, {'Error':str(e)})
        next_used={}
        for(name,pin),positions in used.items():
            c=cells[name];tokens=list(reversed(bits(c['Ports'][pin],widths(c).get(pin,1))));kept=set()
            for index in positions:
                net=tokens[index]
                for dest,dp in g.scalar_refs.get(net,[]):
                    if(dest,dp)==(name,pin)or g.models[g.cells[dest]['Primitive']]['Ports'].get(dp)!='INPUT':continue
                    if dest not in cells or 'Error'in current[dest][2]:kept.add(index);break
                    active=current[dest][0].get(dp,set());dt=list(reversed(bits(cells[dest]['Ports'][dp],widths(cells[dest]).get(dp,1))))
                    if any(i in active and token==net for i,token in enumerate(dt)):kept.add(index);break
            next_used[name,pin]=kept
        selections=current
        if next_used==used:break
        used=next_used
    else:raise ValueError('native macro active-bit fixed point did not converge')
    for name,c in sorted(cells.items()):
        kind=c['Primitive'];selected,why,facts=selections[name];rowissues=[]
        reference=g.models[kind]['Reference'];path=Path(reference['Path'])
        if reference.get('SHA256')!=MODEL_SHA[kind]or hashlib.sha256(path.read_bytes()).hexdigest()!=MODEL_SHA[kind]:
            rowissues.append({'Code':'VendorModelSHAChanged','Model':reference})
        if 'Error'in facts:rowissues.append({'Code':'MacroModeNotReviewed','Detail':facts['Error']})
        active=[];ignored=[]
        for pin,value in c['Ports'].items():
            if g.models[kind]['Ports'].get(pin)!='INPUT':continue
            tokens=list(reversed(bits(value,widths(c).get(pin,1))));indexes=selected.get(pin,set())
            chosen=[tokens[i]for i in sorted(indexes)if i<len(tokens)]
            unknown=[i for i,t in enumerate(tokens)if re.fullmatch(r"1'b[xz]",t)]
            for index in unknown:
                target=active if index in indexes else ignored
                if target is active:rowissues.append({'Code':'SelectedMacroInputUnknown','Pin':pin,'Bit':index})
                else:ignored.append({'Pin':pin,'Bit':index,'Value':tokens[index],
                    'Reason':'Excluded by exact current primitive-mode and actual output-consumer fixed point.'})
            if chosen:active.append({'Pin':pin,'Bits':sorted(indexes),'MSBFirstTokens':list(reversed(chosen)),
                'SelectedValue':chosen[0]if len(chosen)==1 else'{'+','.join(reversed(chosen))+'}'})
        rows.append({'Cell':name,'Primitive':kind,'VendorModel':reference,'ModeFacts':facts,
            'ActiveInputs':active,'ActuallyConsumedOutputBits':{p:sorted(v)for(n,p),v in used.items()if n==name},
            'IgnoredUnknownBits':ignored,'ModeReasons':why,'Passed':not rowissues,'Violations':rowissues,
            'TimingAccepted':False,'SameDomainInputProofStillRequired':True})
        issues += [{'Cell':name,**issue}for issue in rowissues]
    return rows,issues
