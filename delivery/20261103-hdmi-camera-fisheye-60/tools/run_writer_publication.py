"""Check speculative writer payloads against accepted-input publications."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--vivado-bin', type=Path, required=True)
    args = parser.parse_args()
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=False)
    sources = [PACKAGE/'rtl/ddr_adaptive_result_writer.v',
               PACKAGE/'tests/tb_writer_publication.sv', REPO/'distortion/rtl/video_crc32.vh']
    hashes = {}
    for source in sources:
        data = source.read_bytes()
        (work/source.name).write_bytes(data)
        hashes[source.relative_to(REPO).as_posix()] = hashlib.sha256(data).hexdigest()
    commands = []
    steps = [('xvlog', ['--sv', 'ddr_adaptive_result_writer.v', 'tb_writer_publication.sv']),
             ('xelab', ['tb_writer_publication', '-mt', '2', '-s', 'publication']),
             ('xsim', ['publication', '-runall'])]
    for tool, arguments in steps:
        command = [str(args.vivado_bin.resolve()/(tool+'.bat')), *arguments]
        result = subprocess.run(command, cwd=work, capture_output=True, text=True, timeout=120)
        output = result.stdout+result.stderr
        (work/(tool+'.log')).write_text(output, encoding='utf-8')
        passed = result.returncode == 0 and 'Fatal:' not in output and 'ERROR:' not in output
        if tool == 'xsim':
            passed &= 'PASS writer publication checks=8' in output
        commands.append({'command':command, 'returncode':result.returncode, 'passed':passed})
        if not passed:
            raise RuntimeError('Failed '+tool+'; inspect '+str(work/(tool+'.log')))
    metrics = [line for line in output.splitlines() if line.startswith('METRIC')]
    report = {'schema':'fisheye60-writer-publication-v1', 'passed':True, 'scenarios':8,
              'source_sha256':hashes, 'commands':commands, 'metrics':metrics,
              'checks':['Accepted input independently predicts command word, lane and RGB565 payload.',
                        'Every burst word is compared after every edge; unissued speculative data cannot change memory.',
                        'Bad tag, abort, reset and bank switch collide with an earlier pending command.',
                        'Both banks full, inactive input and failed/reset cycles change private payload without publication.'],
              'scope':'Digital unit evidence; native timing and board validation are separate.'}
    (work/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
