"""Real small-frame system: capture CDC, triple source slots, dual lanes and HDMI scan.

Runs a deterministic shared-service DDR stress model at exact 125:148.5 MHz
clock ratios. This functional/ownership test does not predict native DDR FPS.
"""
from pathlib import Path
import argparse, hashlib, json, re, subprocess, time, zlib
import numpy as np
from prepare_candidate import prepare, HERE
from fisheye_integer_reference import integer_map


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_reference(folder, compiled):
    width = height = 64
    coords, black = integer_map(width, height,
        compiled/'board/hdmi-camera-fisheye-profile.vh',
        compiled/'board/hdmi-camera-fisheye-radial-table.vh')
    x, y = coords[:, :, 0].astype(np.int64), coords[:, :, 1].astype(np.int64)
    ix, iy, fx, fy = x//256, y//256, x % 256, y % 256
    crc_raw, crc_corrected = [], []
    pixels = []
    for texture in range(64):
        index = np.arange(width*height, dtype=np.int64).reshape(height, width)
        raw = ((index*13) ^ (index >> 3) ^ (texture*0x4237) ^ 0x5a31).astype('<u2')
        neighbors = []
        for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
            xx, yy = ix+dx, iy+dy
            p = raw[np.clip(yy, 0, height-1), np.clip(xx, 0, width-1)].astype(np.int64)
            p = np.where((xx >= 0) & (xx < width) & (yy >= 0) & (yy < height), p, 0)
            r, g, b = (p >> 11) & 31, (p >> 5) & 63, p & 31
            neighbors.append(np.stack(((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)), axis=-1))
        wx, wy = fx[:, :, None], fy[:, :, None]
        rgb = ((neighbors[0]*(256-wx)+neighbors[1]*wx)*(256-wy) +
               (neighbors[2]*(256-wx)+neighbors[3]*wx)*wy + 32768) >> 16
        rgb = np.where(((x <= -256) | (y <= -256) | (x >= width*256) | (y >= height*256))[:, :, None], 0, rgb)
        out = (((rgb[:, :, 0] >> 3) << 11) | ((rgb[:, :, 1] >> 2) << 5) | (rgb[:, :, 2] >> 3)).astype('<u2')
        pixels.extend(out.ravel().tolist())
        crc_raw.append(zlib.crc32(raw.tobytes()))
        crc_corrected.append(zlib.crc32(out.tobytes()))
    for name, values, digits in (('corrected.hex', pixels, 4), ('raw-crc.hex', crc_raw, 8), ('corrected-crc.hex', crc_corrected, 8)):
        (folder/name).write_text(''.join(f'{v:0{digits}x}\n' for v in values), encoding='ascii')
    return {'coordinate_sha256': hashlib.sha256(coords.tobytes()).hexdigest(), 'numeric_black': int(black.sum()),
            'golden_files': {p.name: digest(p) for p in folder.glob('*.hex')}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--vivado-bin', type=Path, default=Path('D:/Vicado/Vivado/2017.4/bin'))
    parser.add_argument('--tile-width', type=int, choices=(8, 32), default=8)
    parser.add_argument('--cache-index-bits', type=int, choices=(7, 8, 9, 10), default=None,
        help='Override both lanes with a uniform linear cache; default uses the rowpad profile.')
    parser.add_argument('--cache-profile', choices=('rowpad', 'balanced'), default='rowpad')
    parser.add_argument('--ddr-fanout16', action='store_true',
        help='Snapshot the optional CA fanout constraint; functional simulation does not validate physical timing.')
    args = parser.parse_args()
    work = args.work.resolve()
    receipt = prepare(work, args.tile_width, args.cache_index_bits, args.cache_profile, args.ddr_fanout16)
    compiled, sim = work/'compiled', work/'sim'
    sim.mkdir()
    names = ['mul32_pipe.v', 'bilinear_rgb.v', 'ddr_read_arbiter.v', 'ddr_write_arbiter.v',
        'ddr_adaptive_result_writer.v', 'ddr_neighbour_cache_scatter4_rowpipe.v', 'ddr_remap_sample_scatter4_rowpipe.v',
        'hdmi_camera_fisheye_mapper.v', 'hdmi_camera_fisheye_rom.v', 'hdmi_camera_fisheye_core.v',
        'hdmi_camera_fisheye_lane.v', 'hdmi_camera_fisheye_engine.v', 'hdmi_camera_fisheye_bank.v',
        'hdmi1080_capture_cdc.v', 'hdmi1080_input_dma.v', 'hdmi_camera_fisheye_input_link.v',
        'video_async_fifo.v', 'ddr_video_reader.v', 'ddr_video_output_1080_board.v',
        'ddr_read_return_register.v', 'hdmi_camera_fisheye_system_c.v']
    files = {p.name: p for p in compiled.rglob('*.v')}
    sources = [files[name] for name in names] + [HERE/'tests/system_contention.sv']
    report = {'passed': False, 'hardware_tested': False, 'real_engine': True, 'tile_width': args.tile_width,
        'cache_index_bits_override': args.cache_index_bits, 'cache_profile': args.cache_profile,
        'build_id': receipt['build_id'],
        'cache_configuration': receipt.get('cache_configuration', receipt.get('configuration')),
        'width': 64, 'height': 64, 'core_hz': 125000000, 'input_hz': 148500000, 'output_hz': 148500000,
        'scope': 'Real complete datapath, scaled raster, shared-service DDR model; no native 1080p60 throughput or physical timing claim.',
        'source_identity': receipt['source_identity'], 'sources': {str(p): digest(p) for p in sources},
        'reference_source_sha256': digest(HERE/'tools/fisheye_integer_reference.py'),
        'reference': make_reference(sim, compiled), 'commands': []}
    try:
        commands = [['xvlog.bat', '--sv', *map(str, sources)],
                    ['xelab.bat', 'tb_system_contention', '-s', 'system_contention'],
                    ['xsim.bat', 'system_contention', '-runall']]
        for command in commands:
            start = time.monotonic()
            proc = subprocess.run([str(args.vivado_bin/command[0]), *command[1:]], cwd=sim,
                capture_output=True, text=True, errors='replace', timeout=1200)
            output = proc.stdout + proc.stderr
            log = sim/(command[0]+'.log')
            log.write_text(output, encoding='utf-8')
            report['commands'].append({'command': command, 'returncode': proc.returncode,
                'seconds': time.monotonic()-start, 'log_sha256': digest(log)})
            if proc.returncode or re.search(r'(?im)^\s*(fatal|error)(?:\s|:|\[)', output):
                raise RuntimeError(command[0]+': '+output[-6000:])
            print(command[0]+' passed', flush=True)
        if 'PASS SYSTEM CONTENTION' not in output:
            raise RuntimeError('Missing completion marker')
        report['epochs'] = [json.loads(line) for line in (sim/'system-results.jsonl').read_text().splitlines()]
        if len(report['epochs']) != 2:
            raise RuntimeError('Two reset epochs required')
        report['changed_overlays_after_snapshot'] = [row['source'] for row in receipt['overlays']
            if digest(HERE/row['source']) != row['source_sha256']]
        if report['changed_overlays_after_snapshot']:
            raise RuntimeError('Source overlays changed during simulation: '+str(report['changed_overlays_after_snapshot']))
        report['passed'] = True
        print(json.dumps(report['epochs'], indent=2))
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        (work/'system-report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
