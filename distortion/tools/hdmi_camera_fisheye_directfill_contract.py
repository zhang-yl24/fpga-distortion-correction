"""Finite source contract and saved unit binding for the direct-fill cache.

This reads files and derives narrow source facts only. It neither runs an EDA
tool nor confers native timing, RAM mapping, CDC or hardware acceptance.
"""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
SOURCE = ROOT / 'rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe_directfill.v'
BASELINE = ROOT / 'rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe_fill8r3.v'
BENCH = ROOT / 'tests/tb_directfill_rowpipe_cache.sv'
RUNNER = ROOT / 'tools/run_directfill_rowpipe_cache_sim.py'
UNIT_RECEIPT = ROOT / 'work/hdmi-camera-fisheye-tile8df9-20261103-a/cache-unit-a/simulation.json'
SOURCE_SHA256 = 'd4730a733bc8f84886d268fcc90bb702db035a41867c812d6119694fbbf35b1e'
BASELINE_SHA256 = 'ccddbc0293698184a3695744d7fca88350969ccc5f69cb1762b39eac84a0d294'
BENCH_SHA256 = '1095a80958e59950fe2ff49a8ff10401e4a17ddb5a32e1c817515cf05c20f5f4'
RUNNER_SHA256 = 'e86fa646130c74b6eb98b2bfb888042251d6698d1e950a9935a47e2b7c9911a6'
UNIT_RECEIPT_SHA256 = '3340fb27a7d6953e10e98cf07dba0cb8ed85181beaaf049eb392d8fc72870b27'
SCHEMA = 'hdmi-camera-fisheye-directfill-finite-source-contract-v1'

# These normalized source sections were independently compared against the
# pinned fill8r3 file. Their hashes describe unchanged source, not a native
# functional-equivalence or arbitrary-Verilog theorem.
PRESERVED_SECTIONS = (
    ('PublicFIFOAndPortInterface', 'moduleddr_neighbour_cache_scatter16_rowpipe#(', 'endmodule',
     '65bfa248de1805c02053071c6baaf138cd8a65b553b84639613b2d2fb08eb304'),
    ('FrameAdmissionAndFastQueries', 'wire[3:0]decoded_bounds,line_hit;', 'wire[ADDRESS_BITS-1:0]even_upper=',
     '6e243baaad43cd181d5c41c04fa3e327874b7f364ea4fe97988d6f845eae7623'),
    ('NeighbourReadSelection', 'wire[ADDRESS_BITS-1:0]even_upper=',
     'wire[ADDRESS_BITS-1:0]odd_lower=pixel_number[2][0]?pixel_address[2]:pixel_address[3];',
     'c8432ecd85d3897ef9894e07e9b5321bd931c89d45b48ff39fb09ed0406ce233'),
    ('VisibleHitAccounting', 'wire[2:0]fast_hit_increment=', 'integeri;',
     '8b07171691e63a3f3949dd929e434b1b33ab2123d60206d39708b68e29f5edf0'),
    ('FastSequentialAndWatchdog', 'if(decode_query)begin', 'case(state)',
     '1cd43a580c3bff57aac2bffa9cf0906d7ad5ee645a3c262986543cf622a57bf7'),
    ('FrameLookupAndARStates', 'case(state)', 'AR:if(accept_address)state<=FILL;',
     '95d8da4f403b94177f6f8e81d16583a2b3a1477e9fcd58974a6fb3e4f9ebcae3'),
    ('SlowResultAndFaultQuarantine', 'LOAD:state<=PICK;', 'if(!failed&&rvalid)begin',
     '61ad8101ce17153b2d104a4a59ce49488afef5af92f2e40bc1032a8d7b9bf97d'),
    ('TimeoutStickyTail', 'if(!failed&&&watchdog', 'endmodule',
     '7b34c25252c369245f19fa688c3212ad1b7e714c17a7c8fb1cd3e20d4faf83df'),
)
UNIT_INPUTS = {
    SOURCE: SOURCE_SHA256, BENCH: BENCH_SHA256, RUNNER: RUNNER_SHA256,
    ROOT / 'tools/run_fill8_rowpipe_cache_sim.py':
        '7511b32ca0d03b04ffa7126a98dce01d31c701a67f654a553985fb3af0a43885',
    ROOT / 'tools/simulation_tools.py':
        'cb6f08cf764cce9c088ede89c65ce8f7da0cee447d95015b5685fde18de50a6e',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compact(text):
    require(type(text) is str, 'source must be a complete string')
    return re.sub(r'\s+', '', re.sub(r'//[^\n]*|/\*[\s\S]*?\*/', '', text))


def section(code, start, end):
    require(code.count(start) == 1, 'source section start is not unique: ' + start)
    left = code.index(start)
    right = code.find(end, left)
    require(right >= left, 'source section end missing: ' + end)
    return code[left:right + len(end)]


def once(code, clause, role):
    require(code.count(clause) == 1, 'direct-fill source invariant differs: ' + role)


def preserved(code):
    facts = {}
    for name, start, end, expected in PRESERVED_SECTIONS:
        value = section(code, start, end)
        digest = hashlib.sha256(value.encode('utf-8')).hexdigest()
        require(digest == expected, 'pinned baseline source section changed: ' + name)
        facts[name] = {'NormalizedSHA256': digest, 'SamePinnedSourceSection': True}
    return facts


def review_source(text):
    """Check the full pinned UTF-8 source and finite critical source clauses."""
    code = compact(text)
    once(code, 'wirewrite_commit=rst_n&&!failed&&fill_write_valid;', 'registered write CE')
    once(code, 'wirewrite_commit_last=write_commit&&fill_write_beat==7;', 'last owned commit')
    once(code, 'always@(posedgeclk)fill_write_data<=rdata;', 'unconditional payload register')
    require(re.findall(r'\bfill_write_data<=([^;]+);', code) == ['rdata'],
            'payload register acquired another assignment/reset/CE')
    require('fill_buffer' not in code and 'SCATTER' not in code and 'scatter_group' not in code,
            'post-receive burst scatter storage/state reintroduced')
    once(code, 'wire[INDEX_BITS-1:0]write_commit_line=fill_write_line;', 'owned write line')
    once(code, 'wire[2:0]write_commit_beat=fill_write_beat;', 'owned write beat')
    once(code, "wire[WORD_ADDRESS_BITS-1:0]write_address_a={write_commit_line,write_commit_beat,1'b0};",
         'first owned word address')
    once(code, "wire[WORD_ADDRESS_BITS-1:0]write_address_b={write_commit_line,write_commit_beat,1'b1};",
         'second owned word address')
    once(code, 'wire[255:0]fill_sixteen=fill_write_data;', 'registered RAM payload')
    once(code, "wire[31:0]hit_count=committed_hits+{29'd0,pending_hits};", 'same-edge visible hit-count bypass')
    for array, port, payload in (('even_pixels', 'even_a', 'fill_even_a'),
                                 ('even_pixels', 'even_b', 'fill_even_b'),
                                 ('odd_pixels', 'odd_a', 'fill_odd_a'),
                                 ('odd_pixels', 'odd_b', 'fill_odd_b')):
        once(code, 'if(write_commit)' + array + '[' + port + ']<=' + payload + ';',
             'owned RAM port ' + port)
    once(code, 'WAIT_COMMIT:beginif(write_commit_last)beginvalid_lines[write_commit_line]<=1;'
         'tags[write_commit_line]<=fill_write_block;state<=LOAD;endend',
         'actual final RAM edge before line publication')
    once(code, 'if(!failed&&rvalid)beginif(!receiving)beginfailed<=1;fault<=8\'h04;state<=FAULT;'
         'valid_lines[selected_line]<=0;endelseif(rid!=0||rlast!=(fill_beat==7))beginfailed<=1;'
         'fault<=8\'h03;state<=FAULT;valid_lines[selected_line]<=0;endelsebeginfill_write_valid<=1;'
         'fill_write_beat<=fill_beat;fill_write_line<=selected_line;fill_write_block<=selected_block;'
         "if(fill_beat==7)state<=WAIT_COMMIT;elsefill_beat<=fill_beat+1'b1;endend",
         'guarded receive and same-edge complete stage metadata')
    once(code, 'if(!rst_n)beginstate<=IDLE;frame_loaded<=0;address_pending<=0;base<=0;valid_lines<=0;',
         'common reset of ownership and validity')
    once(code, 'fill_beat<=0;fill_write_valid<=0;fill_write_beat<=0;fill_write_line<=0;'
         'fill_write_block<=0;watchdog<=0;failed<=0;fault<=0;', 'reset of new owned stage')
    once(code, 'endelsebeginfill_write_valid<=0;if(decode_query)begin', 'default one-edge stage ownership')
    require(re.findall(r'fill_write_valid<=([^;]+);', code) == ['0', '0', '1'],
            'write validity is not reset/default-zero/accepted-return-only')
    for field, value in (('fill_write_beat', 'fill_beat'), ('fill_write_line', 'selected_line'),
                         ('fill_write_block', 'selected_block')):
        require(re.findall(field + r'<=([^;]+);', code) == ['0', value],
                'owned stage field assignment set changed: ' + field)
    writes = re.findall(r'(valid_lines(?:\[[^\]]+\])?)<=([^;]+);', code)
    require(writes == [('valid_lines', '0'), ('valid_lines', '0'),
                      ('valid_lines[selected_line]', '0'), ('valid_lines[write_commit_line]', '1'),
                      ('valid_lines[selected_line]', '0'), ('valid_lines[selected_line]', '0'),
                      ('valid_lines[selected_line]', '0')], 'line validity assignment inventory changed')
    require(re.findall(r'\b(tags\[[^\]]+\])<=([^;]+);', code) ==
            [('tags[write_commit_line]', 'fill_write_block')], 'tag publication inventory changed')
    # The raw-return invalidation block is textually after the entire state case
    # in the SAME clocked block, so its final nonblocking assignment wins over
    # an otherwise simultaneous final-commit publication on the selected line.
    publish = code.index('WAIT_COMMIT:beginif(write_commit_last)')
    state_end = code.index('endcase', publish)
    fault_tail = code.index('if(!failed&&rvalid)begin', state_end)
    require(publish < state_end < fault_tail < code.index('if(!failed&&&watchdog', fault_tail),
            'fault invalidation no longer follows commit publication in the same block')
    unchanged = preserved(code)
    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
    require(digest == SOURCE_SHA256, 'complete pinned direct-fill source SHA256 differs')
    return {'Schema': SCHEMA, 'Passed': True, 'SourceSHA256': digest,
            'BaselineSHA256': BASELINE_SHA256, 'RegisteredRAMWriteEnable': True,
            'UnconditionalPayloadRegisterWithoutResetOrCE': True,
            'LineBeatBlockValidCapturedOnSameAcceptedReturnEdge': True,
            'OnlyActualFinalRAMCommitPublishesTagAndValid': True,
            'RawProtocolFaultInvalidationHasFinalAssignmentPriority': True,
            'PreservedBaselineSections': unchanged, 'PostReceiveScatterCycles': 0,
            'RAMMappingAccepted': False, 'NativeEquivalent': False, 'CDCAccepted': False,
            'STAInherited': False, 'HardwareReleaseAllowed': False,
            'PDSAccessed': False, 'HardwareAccessed': False}


def review(source_path=SOURCE):
    """Read exact source, old baseline and the already-completed unit evidence."""
    watched = {}

    def bind(path, expected=None):
        path = Path(path).resolve()
        require(path.is_file(), 'missing direct-fill contract input: ' + str(path))
        digest = sha(path)
        require(expected is None or digest == expected, 'direct-fill contract input SHA drift: ' + str(path))
        require(str(path) not in watched or watched[str(path)] == digest, 'conflicting watched SHA')
        watched[str(path)] = digest
        return path

    source_path = bind(source_path, SOURCE_SHA256)
    facts = review_source(source_path.read_bytes().decode('utf-8'))
    baseline = bind(BASELINE, BASELINE_SHA256)
    require(preserved(compact(baseline.read_bytes().decode('utf-8'))) == facts['PreservedBaselineSections'],
            'live pinned baseline sections do not match')
    receipt_path = bind(UNIT_RECEIPT, UNIT_RECEIPT_SHA256)
    value = json.loads(receipt_path.read_text(encoding='utf-8'))
    require(value.get('Schema') == 'tile8-directfill-independent-cache-simulation-v1' and
            value.get('Passed') is True and value.get('InputDrift') == [] and
            value.get('PDSAccessed') is False and value.get('HardwareAccessed') is False and
            value.get('FullFrameSimulated') is False and value.get('SingleRegisteredBeatPerWrite') is True and
            value.get('PostReceiveScatterCycles') == 0 and not value.get('Error'),
            'clean completed direct-fill cache unit receipt required')
    expected_inputs = {str(path.resolve()): digest for path, digest in UNIT_INPUTS.items()}
    require(value.get('SourceSHA256') == expected_inputs, 'actual unit source/test/runner closure differs')
    for path, digest in UNIT_INPUTS.items():
        bind(path, digest)
    for name, digest in value['ArtifactsSHA256'].items():
        relative = Path(name)
        require(not relative.is_absolute() and '..' not in relative.parts,
                'unit artifact escaped its actual work directory')
        bind(receipt_path.parent / relative, digest)
    cases = value.get('Cases')
    require(isinstance(cases, dict) and set(cases) == {'639-i3', '1920-i7', '1920-i8', '1920-i9'},
            'all actual direct-fill geometry/index cases required')
    for name, case in cases.items():
        require(case['passed'] is True and case['commits_per_fill'] == 8 and case['fault_cases'] == 6 and
                case['reset_before_last_commit'] == 1 and case['warm_stream_outputs'] == 64 and
                case['warm_span_cycles'] == 63 and case['warm_first_valid_latency'] == 4 and
                case['ram_pixels_checked'] == case['complete_fills'] * 128 and
                case['IndependentTrace']['ActualMatchesIndependentPixelOracle'] is True and
                case['IndependentTrace']['ResetCanceledQueries'] == 1,
                'saved direct-fill case lacks required checks: ' + name)
        require(all(case[key] > 0 for key in ('same_cycle_first_beats', 'delayed_first_beats',
                    'continuous_commit_pairs', 'ar_stalls', 'r_gaps', 'output_stalls', 'input_stalls',
                    'queue_full', 'frame_pending', 'fast_queries', 'slow_queries', 'frame_drains')),
                'vacuous saved direct-fill case: ' + name)
    bind(SELF)
    facts['SelectedSource'] = {'Path': str(source_path), 'SHA256': SOURCE_SHA256}
    facts['CompletedUnitReceipt'] = {'Path': str(receipt_path), 'SHA256': UNIT_RECEIPT_SHA256}
    facts['SavedUnitCases'] = {name: {'Outputs': case['normal_outputs'],
                                  'RAMLinePixelsChecked': case['ram_pixels_checked'],
                                  'StreamCRC32': case['IndependentTrace']['CRC32']}
                             for name, case in cases.items()}
    facts['ChecksUseOnlyPinnedSourceAndSavedUnitEvidence'] = True
    return facts, watched
