"""Reject corrupt synthetic structural graphs; never a native physical proof."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import audit_camera720_monitor as monitor

P = monitor.PREFIX


def ff(q, d, clk='clk_27m', sr="1'b0"):
    return {'Primitive': 'V_FFASYN', 'Parameters': {'INIT': "1'b0", 'SET_RESET': '"RESET"'},
            'Ports': {'Q': q, 'D': d, 'CK': clk, 'CE': "1'b1", 'SR': sr}}


def fixture():
    cells, sites = {}, {}
    def add(name, cell, site):
        cells[name] = cell
        sites[name] = {'Site': site, 'Attributes': ''}
    add(P+'r_reset[1]/FF0/FF', ff(P+'r_reset[1]', "1'b1"), 'RESET')
    for family, width in (('edge', 32), ('vs', 16), ('href', 16)):
        for bit in range(width):
            source, first, second = (P+family+suffix+f'[{bit}]' for suffix in ('_gray', '_meta', '_sync'))
            add(source+'/FF0/FF', ff(source, "1'b0", 'cam_pclk'), f'S{family}{bit}')
            add(first+'/FF0/FF', ff(first, source), f'D{family}{bit}')
            add(second+'/FF0/FF', ff(second, first), f'D{family}{bit}')
    return {'Cells': cells, 'FFPlacement': sites, 'ModuleDeclarations': ''}


def lut(inputs, expression, output):
    init = 0
    for index in range(64):
        if expression([(index >> bit) & 1 for bit in range(6)]):
            init |= 1 << index
    return {'Primitive': 'V_LUT6CARRY', 'Parameters': {'INIT': f"64'h{init:016X}", 'I5_TO_LUT': '"TRUE"', 'I5_TO_CARRY': '"TRUE"'},
            'Ports': {**{'I'+str(i): n for i, n in enumerate(inputs)}, 'Z': output, 'Z5': '', 'COUT': '', 'CIN': "1'b0"}}


class MonitorStructureTests(unittest.TestCase):
    def test_interstage_release_gate_can_use_native_cin_selector(self):
        value = fixture()
        gate = lut(['release']+["1'b0"]*4+["1'b1"], lambda a: a[0] & a[5], 'gated')
        gate['Parameters']['I5_TO_LUT'] = '"FALSE"'
        gate['Ports']['CIN'] = 'first'
        value['Cells']['native_gate'] = gate
        result = monitor.Graph(value).lut_gate('native_gate', 'Z', 'first', 'release')
        self.assertTrue(result['NativeLUTSelectorsChecked'])
        self.assertEqual(result['FirstStageInputPins'], ['CIN'])
        value['Cells']['native_gate']['Parameters']['I5_TO_LUT'] = '"TRUE"'
        with self.assertRaisesRegex(ValueError, 'unrelated Boolean support'):
            monitor.Graph(value).lut_gate('native_gate', 'Z', 'first', 'release')

    def test_native_cin_and_carry_selectors_are_not_treated_as_plain_lut6(self):
        cell = lut(["1'b0"]*6, lambda a: a[5], 'z')
        cell['Ports']['CIN'] = "1'b1"
        cell['Parameters']['I5_TO_LUT'] = '"FALSE"'
        self.assertEqual(monitor.lut_value(cell, 'Z', {}), 1)
        cell['Parameters']['I5_TO_LUT'] = '"TRUE"'
        self.assertEqual(monitor.lut_value(cell, 'Z', {}), 0)
        cell['Parameters']['I5_TO_CARRY'] = '"FALSE"'
        self.assertEqual(monitor.lut_value(cell, 'COUT', {}), 1)
        cell['Parameters']['I5_TO_CARRY'] = '"TRUE"'
        self.assertEqual(monitor.lut_value(cell, 'COUT', {}), 0)

    def test_held_bus_traversal_reaches_consumer_through_carry_then_cin_selected_lut(self):
        value = fixture()
        source = P+'held_snapshot[0]/FF0/FF'
        sq = P+'held_snapshot[0]'
        dest = P+'frame_age[0]/FF0/FF'
        value['Cells'][source] = ff(sq, "1'b0", 'cam_pclk')
        value['Cells'][dest] = ff(P+'frame_age[0]', 'compared')
        c = lut([sq]+["1'b0"]*5, lambda a: a[0] if not a[5] else 0, '')
        c['Ports'].update(COUT='carry', CIN="1'b1")
        value['Cells']['compare'] = c
        c = lut(["1'b0"]*6, lambda a: a[5], 'compared')
        c['Ports']['CIN'] = 'carry'
        c['Parameters']['I5_TO_LUT'] = '"FALSE"'
        value['Cells']['carry_tail'] = c
        g = monitor.Graph(value)
        report = monitor.held_first_sinks(g, {'Rows': [{'Bit': 0, 'Source': source, 'Ports': value['Cells'][source]['Ports']}]})
        self.assertEqual(report['FirstSequentialPathPairs'], 1)
        self.assertEqual(report['Rows'][0]['Consumers'][0]['Cell'], dest)

    def test_shared_lut_constant_and_duplicate_inputs_are_cofactored(self):
        value = fixture()
        source = P+'edge_gray[0]'
        irrelevant = P+'vs_meta[0]'
        value['Cells']['shared'] = lut([source, irrelevant, "1'b0", "1'b0", "1'b0", "1'b0"],
                                      lambda a: a[0] | (a[1] & a[2]), 'shared_q')
        g = monitor.base.Graph(value)
        self.assertEqual(monitor.cone_ff(g, 'shared_q'), {g.by_q(source)})
        value['Cells']['shared'] = lut([source, irrelevant, irrelevant, "1'b0", "1'b0", "1'b0"],
                                      lambda a: a[0] | (a[1] ^ a[2]), 'shared_q')
        g = monitor.base.Graph(value)
        self.assertEqual(monitor.cone_ff(g, 'shared_q'), {g.by_q(source)})

    def test_encoded_fault_must_stay_low_and_invert_at_first_stage(self):
        value = fixture()
        source = P+'source_fault_reg[0]/FF0/FF'
        source_release = P+'p_reset[1]/FF0/FF'
        destination_release = P+'r_reset[1]/FF0/FF'
        first = P+'failed_sync[0]/FF0/FF'
        source_q, sr_q, dr_q = (P+n for n in ('source_fault_reg[0]', 'p_reset[1]', 'r_reset[1]'))
        value['Cells'][source] = ff(source_q, 'source_d', 'cam_pclk')
        value['Cells'][source]['Parameters'] = {'INIT': "1'b1", 'SET_RESET': '"SET"'}
        value['Cells'][source_release] = ff(sr_q, "1'b1", 'cam_pclk')
        value['Cells'][first] = ff(P+'failed_sync[0]', 'first_d')
        value['Cells']['source_logic'] = lut([source_q, sr_q, 'unreviewed_primary', "1'b0", "1'b0", "1'b0"],
                                           lambda a: (1-a[1]) | (a[0] & a[2]), 'source_d')
        value['Cells']['first_logic'] = lut([source_q, dr_q, "1'b0", "1'b0", "1'b0", "1'b0"],
                                          lambda a: (1-a[0]) & a[1], 'first_d')
        g = monitor.base.Graph(value)
        result = monitor.encoded_sticky_fault(g, source, first, source_release, destination_release)
        self.assertTrue(result['StickyLowWhileSourceReleased'])
        value['Cells'][source]['Ports']['D'] = "1'b1"
        with self.assertRaisesRegex(ValueError, 'may deassert'):
            monitor.encoded_sticky_fault(monitor.base.Graph(value), source, first, source_release, destination_release)

    def test_all_64_gray_chains_are_checked_without_legacy_count(self):
        rows = monitor.monitor_gray(monitor.Graph(fixture()))
        self.assertEqual(len(rows), 64)
        self.assertEqual({row['Width'] for row in rows}, {16, 32})

    def test_missing_gray_bit_fails_closed(self):
        value = fixture()
        del value['Cells'][P+'edge_meta[31]/FF0/FF']
        with self.assertRaisesRegex(ValueError, 'resolve exactly once'):
            monitor.monitor_gray(monitor.base.Graph(value))

    def test_wrong_gray_register_origin_rejected(self):
        value = fixture()
        value['Cells'][P+'edge_meta[0]/FF0/FF']['Ports']['D'] = P+'edge_gray[1]'
        with self.assertRaisesRegex(ValueError, 'identity differs'):
            monitor.monitor_gray(monitor.base.Graph(value))

    def test_gray_first_stage_must_not_drive_functional_logic(self):
        value = fixture()
        value['Cells']['escape'] = ff('escape_q', P+'edge_meta[0]')
        value['FFPlacement']['escape'] = {'Site': 'OTHER', 'Attributes': ''}
        with self.assertRaisesRegex(ValueError, 'functional fanout escapes'):
            monitor.monitor_gray(monitor.base.Graph(value))

    def test_second_stage_clock_change_rejected(self):
        value = fixture()
        value['Cells'][P+'edge_sync[0]/FF0/FF']['Ports']['CK'] = 'cam_pclk'
        with self.assertRaisesRegex(ValueError, 'different stage clock'):
            monitor.monitor_gray(monitor.base.Graph(value))

    def test_stage_clear_difference_rejected(self):
        value = fixture()
        value['Cells'][P+'edge_sync[0]/FF0/FF']['Ports']['SR'] = 'another_reset'
        with self.assertRaisesRegex(ValueError, 'different stage clear'):
            monitor.monitor_gray(monitor.base.Graph(value))

    def test_unknown_first_stage_combinational_cell_rejected(self):
        value = fixture()
        value['Cells']['unknown'] = {'Primitive': 'V_INV', 'Parameters': {}, 'Ports': {'Z': 'unknown_net', 'I': 'unknown_primary'}}
        value['Cells'][P+'edge_meta[0]/FF0/FF']['Ports']['D'] = 'unknown_net'
        with self.assertRaisesRegex(ValueError, 'primary input'):
            monitor.monitor_gray(monitor.base.Graph(value))

    def test_held_inventory_accepts_only_observed_bits_and_stays_unapproved(self):
        value = fixture()
        for bit in range(73, 105):
            name = P+f'held_snapshot[{bit}]/FF0/FF'
            value['Cells'][name] = ff(P+f'held_snapshot[{bit}]', "1'b0", 'cam_pclk')
            value['FFPlacement'][name] = {'Site': str(bit), 'Attributes': ''}
        report = monitor.held_snapshot_inventory(monitor.base.Graph(value))
        self.assertEqual(report['SurvivingBits'], list(range(73, 105)))
        self.assertEqual(report['AbsentLogicalBits'], list(range(73)))
        self.assertFalse(report['NativeHandshakeConeProofComplete'])
        self.assertFalse(report['HeldBusPhysicalBoundComplete'])
        self.assertFalse(report['AbsentBitsClassifiedAsOptimizedDiagnostics'])
        del value['Cells'][P+'held_snapshot[104]/FF0/FF']
        with self.assertRaisesRegex(ValueError, 'missing native bits'):
            monitor.held_snapshot_inventory(monitor.base.Graph(value))


if __name__ == '__main__':
    unittest.main()
