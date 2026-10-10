"""Prepare an isolated OV5640 cadence trial; no active sources or hardware changes."""
from pathlib import Path
import hashlib
import json
import re

root = Path(__file__).resolve().parents[1]
path = root / 'board/ov5640_commands.vh'
text = path.read_text()
commands = [(int(i), int(word, 16)) for i, word in re.findall(r"9'd(\d+): camera_command=32'h([0-9a-fA-F]{8});", text)]
assert len(commands) == 264 and [i for i, _ in commands] == list(range(264))
registers = {word >> 16: (word >> 8) & 255 for _, word in commands}
assert all(registers[a] == v for a, v in {0x3034: 0x18, 0x3035: 0x41, 0x3036: 0x60, 0x3037: 0x13, 0x3108: 1}.items())
xclk = 24000000
hts = registers[0x380c] * 256 + registers[0x380d]
vts = registers[0x380e] * 256 + registers[0x380f]
assert (hts, vts) == (1936, 1088)
vco = xclk * registers[0x3036] // (registers[0x3037] & 15)
assert vco <= 800000000

def sysclk(regs):
    # OV5640 DVP application guide pp. 56-57, get_sysclk().
    divisor = regs[0x3035] >> 4 or 16
    root_divisor = ((regs[0x3037] >> 4) & 1) + 1
    bit_divisor_2x = (regs[0x3034] & 15) // 2
    sclk_divisor = (1, 2, 4, 8)[regs[0x3108] & 3]
    return vco // divisor // root_divisor * 2 // bit_divisor_2x // sclk_divisor

current_clock = sysclk(registers)
trial = dict(registers)
trial[0x3035] = 0x21
trial_clock = sysclk(trial)
assert current_clock == 24000000 and trial_clock == 48000000
# Preserve the application-guide integer truncation order (units: 10 kHz).
step50 = (trial_clock // 10000) * 100 // hts
step60 = step50 * 100 // 120
changes = {0x3035: 0x21, 0x3a08: step50 >> 8, 0x3a09: step50 & 255,
           0x3a0a: step60 >> 8, 0x3a0b: step60 & 255,
           0x3a0e: (vts - 4) // step50, 0x3a0d: (vts - 4) // step60}
changed_indices = []
for index, word in commands:
    address = word >> 16
    if address not in changes:
        continue
    new_word = (word & 0xffff00ff) | changes[address] << 8
    old_line = f"9'd{index}: camera_command=32'h{word:08x};"
    new_line = f"9'd{index}: camera_command=32'h{new_word:08x};"
    assert old_line in text
    text = text.replace(old_line, new_line)
    changed_indices.append({'index': index, 'address': f'{address:04X}',
                            'old': f'{registers[address]:02X}', 'candidate': f'{changes[address]:02X}'})
new_path = root / 'board/ov5640_cadence_trial_commands.vh'
new_path.write_text('// Isolated cadence trial, not physically validated.\n' + text)
init_path = root / 'rtl/ov5640_init.v'
init = init_path.read_text().replace('module ov5640_init #(', 'module ov5640_cadence_trial_init #(')
init = init.replace(str(path).replace('\\', '/'), str(new_path).replace('\\', '/'))
assert 'ov5640_cadence_trial_commands.vh' in init
(root / 'rtl/experimental/ov5640_cadence_trial_init.v').write_text(init)
observed = json.loads((root / 'results/lab-20261007/overlap-zero-check.json').read_text())
predicted_current = current_clock / hts / vts
measured_current = observed['scheduling']['approx_sensor_frame_rate_at_125mhz']
assert abs(predicted_current - measured_current) / measured_current < .01
result = {
    'status': 'isolated_preparation_only', 'hardware_accessed': False, 'board_build_started': False,
    'xclk_hz_from_existing_module_schematic': xclk, 'pll_vco_hz_unchanged': vco,
    'width': 640, 'height': 480, 'hts_unchanged': hts, 'vts_unchanged': vts,
    'current_predicted_fps': predicted_current, 'current_measured_sensor_fps': measured_current,
    'candidate_predicted_fps': trial_clock / hts / vts,
    'current_sysclk_hz': current_clock, 'candidate_sysclk_hz': trial_clock,
    'register_changes': changed_indices,
    'existing_source_sha256': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (path, init_path)},
    'manual': '../vendor/board/盘古100Pro+开发板（MES2L676-100HP）配套资料/4_IC_datasheet/OV5640/OV5640_AF_Imaging_Module_Application_Guide_(DVP_Interface).pdf',
    'manual_pages': [56, 57, 59, 60],
    'limits': 'Prediction only. A future board target must use the isolated init module, read back controls, verify actual PCLK against constraints, all 307200 pixels/480 lines, cadence under exposure changes, DDR/video errors and temperature. Does not claim 22.79 fps achieved. Active board/init/table sources are unchanged. HTS/VTS, crop, ISP geometry and calibration coefficients are preserved, but image quality and calibration validity still require physical checks.',
}
(root / 'results/lab-20261007/camera-cadence-candidate.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'prepared_only': True, 'current_predicted_fps': predicted_current,
                  'current_measured_fps': measured_current, 'candidate_predicted_fps': result['candidate_predicted_fps']}, indent=2))
