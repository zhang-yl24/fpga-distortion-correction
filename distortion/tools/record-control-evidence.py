from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[1]
manual=next((root.parent/'vendor/board').rglob('教程1_硬件实验指导手册*100Pro+*.pdf'))
text=(root/'build/board-hardware-manual.txt').read_text(encoding='utf-8')
import re
assert re.search(r'KEY0\s+C22',text) and '低电平有效' in text
out={'source':str(manual),'source_sha256':hashlib.sha256(manual.read_bytes()).hexdigest(),
    'section':'2.1.3.4.1 按键','key':'KEY0','fpga_pin':'C22','active_level':'low',
    'matching_vendor_constraint':'platform/video_base/HDMI_IN_DDR3_HDMI_OUT_top.fdc rst_in=C22',
    'photo_model':'MES2L676-BASE-V1.4','physical_key_behavior_verified_this_turn':False}
(root/'results/rotation-key-evidence-20261006.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
thermal_path=root/'results/temperature-monitor-plan-20261006.json'
thermal=json.loads(thermal_path.read_text(encoding='utf-8'))
thermal.update({'protocol_simulation_passed':True,'adc_register_figure_visually_verified':True,
    'extraction':'temperature code12=0x40 word[15:4]','implementation':'rtl/logos2_temperature_monitor.v and rtl/adc_temperature_reader.v; corrected_rotate build underway',
    'limits':'Board build and actual analog temperature await verification. Protocol simulation does not verify physical ADC accuracy or alarm behavior.'})
thermal_path.write_text(json.dumps(thermal,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('KEY0/C22/active-low confirmed from vendor hardware guide; ADC protocol and visual register evidence recorded.')
