"""Build delivery status from source-bound evidence, retaining every open gate."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project',type=Path,required=True)
    p.add_argument('--revision',required=True)
    a=p.parse_args();project=a.project.resolve();rev=a.revision
    plan=json.loads((project/'candidate-plan.json').read_text())
    hashes={}
    def read(name):
        path=HERE/name
        if not path.is_file():return None
        data=path.read_bytes();hashes[name]=hashlib.sha256(data).hexdigest()
        return json.loads(data)
    for overlay in plan['overlays']:
        path=HERE/overlay['source']
        assert hashlib.sha256(path.read_bytes()).hexdigest()==overlay['source_sha256'],path
    full=[]
    for latency in (12,40):
        folder=f'evidence/final-{rev}-lat{latency}'
        r=read(folder+'/engine-report.json');binding=read(folder+'/physical-source-binding.json')
        passed=bool(r and r['passed'] and binding and binding['passed'] and
                    binding['physical_source_identity']==plan['source_identity'] and
                    binding['tested_source_identity']==r['source_identity'])
        full.append(dict(status='PASS' if passed else 'PENDING',evidence=folder,
                         latency_cycles=latency,shared_service_pressure=True,
                         **({k:r[k] for k in ('cycles','pixels','mismatched_pixels','crc','reads','writes',
                            'ms_at_125mhz','engine_fps_at_125mhz','output_sha256','within_60fps_engine_budget')} if r else {})))
    system_folder=f'evidence/system-final-{rev}-rowpad640-fanout16'
    system=read(system_folder+'/system-report.json')
    binding=read(system_folder+f'/physical-{rev}-source-binding.json')
    system_status=dict(status='PENDING',evidence=system_folder)
    if system and binding:
        assert binding['physical_source_identity']==plan['source_identity']
        assert binding['system_source_identity']==system['source_identity']
        assert binding['same_overlay_sources'] and not binding['source_differences']
        assert binding['closure_files']==binding['closure_normalized_matches']==len(plan['source_files'])
        assert all(x['normalized_match'] for x in binding['closure'])
        assert not system['changed_overlays_after_snapshot']
        system_status.update(status='PASS' if system['passed'] else 'FAIL',width=system['width'],height=system['height'],
            real_engine=system['real_engine'],epochs=len(system['epochs']),
            totals={key:sum(e[key] for e in system['epochs']) for key in
                    ('unique_displayed','raw_displayed','corrected_displayed','display_pixels','repeat_displayed','underflows','mismatches')})
    timing=read(f'evidence/physical-{rev}/timing.json')
    physical=dict(status='PENDING',same_or_related_clock_failures=[],external_io='PENDING',
                  held_bundle_cdc_and_reset_acceptance='PENDING')
    if timing:
        assert timing['source_identity']==plan['source_identity']
        failures=[]
        for check,rows in timing['summaries'].items():
            for row in rows:
                count=int(row.get('Failing Endpoints',row.get('Failing End Point','0')) or 0)
                if count and row['domain_status'] in ('same_clock','related_clock_domains_timed','core_to_divided_phy_timed'):
                    failures.append(dict(check=check,**row))
        physical.update(status='FAIL' if failures else 'INTERNAL_CHECKS_PASS_ACCEPTANCE_PENDING',
                        same_or_related_clock_failures=failures,
                        external_io=timing['external_io_status'],
                        report=f'evidence/physical-{rev}/timing.json')
    gray=read(f'evidence/cdc-user-audit/physical-{rev}-gray-constraints.json')
    nonfifo=read(f'evidence/cdc-user-audit/physical-{rev}-nonfifo-mapping.json')
    fifo=read(f'evidence/cdc-fifo-{rev}/fifo-{rev}-mapped-audit.json')
    structure=dict(nonfifo=nonfifo.get('status') if nonfifo else 'PENDING',
        fifo='PASS' if fifo and fifo['source_identity']==plan['source_identity'] and fifo['mapped']['gray_pairs_passed'] and fifo['mapped']['reset_owners_passed'] else 'PENDING',
        gray_bounds=gray.get('status') if gray else 'PENDING',
        scope='Structural mapping and exact Gray bounds; other CDC/MTBF/reset acceptance remains open.')
    ddr=read(f'evidence/physical-{rev}/ddr-constraints.json')
    ca=read(f'evidence/physical-{rev}/ddr-ca-fanout.json')
    status=dict(schema='fisheye60-validation-v1',updated_utc=datetime.now(timezone.utc).isoformat(),
        delivery_kind='SOURCE_INTEGRATION_CANDIDATE',revision=rev,
        source_identity=plan['source_identity'],source_file_count=len(plan['source_files']),
        build_id=plan['build_id'],profile_id=plan['profile_id'],baseline_commit=plan['baseline_commit'],
        baseline_bitstream_sha256=plan['baseline_bitstream'],hardware_tested=False,
        target=dict(width=1920,height=1080,new_corrected_fps=60,quality='C fisheye calibration, bilinear, RGB565, gamma off, zero rotation'),
        full_frame_simulation=full,system_simulation=system_status,physical_timing=physical,
        synchronizers_and_gray=structure,
        ddr_constraint_audit=ddr.get('status') if ddr else 'PENDING',
        ca_local_equivalence=ca.get('status') if ca else 'PENDING',
        candidate_bitstream=dict(status='NOT_GENERATED',board_ready=False),
        remaining_acceptance=['Physical timing closure','Held-bundle CDC, reset release and MTBF review',
            'External HDMI IO timing','Board programming and new-frame rate measurement','60-second and 600-second board runs'],
        evidence_sha256=hashes,
        limitations=['Model processing rate is distinct from scan refresh and measured new displayed frame rate.',
                     'Original board-tested C bitstream is retained separately and belongs to the 4.28 FPS baseline.'])
    (HERE/'VALIDATION_STATUS.json').write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(source_identity=plan['source_identity'],full=[x['status'] for x in full],
                         system=system_status['status'],physical=physical['status'],cdc=structure),indent=2))


if __name__=='__main__':main()
