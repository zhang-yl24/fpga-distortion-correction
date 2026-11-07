"""Small saved-report excerpt; no rtr scan or provider execution."""
from pathlib import Path
import collections
import hashlib
import json

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / 'assoc2way256-ordinary-core-failure-paths-a.json'
TEXT = SOURCE.with_suffix('.txt')


def ref(path):
    return dict(Path=str(path.resolve()), SHA256=hashlib.sha256(path.read_bytes()).hexdigest(), Bytes=path.stat().st_size)


def main():
    value = json.loads(SOURCE.read_text())
    classes = collections.defaultdict(list)
    for row in value['WorstPathPerFailingEndpoint']:
        start = row['Startpoint']
        if '/writer/accepted_pixels' in start:
            family = 'writer_ready_to_metadata_LRU'
        elif 'reset_sync' in start:
            family = 'reset_to_valid'
        elif '/tags_' in start and 'gopdrm' in start:
            family = 'tag_RAM_to_selected_way_fault_valid'
        elif 'dqs_read_valid' in start:
            family = 'DDR_return_valid_to_valid'
        elif 'display_fifo' in start:
            family = 'display_FIFO_gray_to_stats'
        elif '/read_bus/state' in start:
            family = 'read_bus_state_to_writer'
        else:
            raise ValueError('unclassified actual worst endpoint: ' + start)
        classes[family].append(row)
    expected = dict(writer_ready_to_metadata_LRU=257, reset_to_valid=183,
                    tag_RAM_to_selected_way_fault_valid=170, DDR_return_valid_to_valid=50,
                    display_FIFO_gray_to_stats=14, read_bus_state_to_writer=13)
    if {k: len(v) for k, v in classes.items()} != expected or sum(expected.values()) != value['UniqueFailingEndpoints']:
        raise ValueError('actual family counts differ')
    result = dict(Schema='tile8-assoc2-actual-core-failure-small-archive-summary-v1', ResearchOnly=True,
                  ActualOrdinaryCorePassed=False, ActualSummary=value['ActualSummary'],
                  NegativePaths=value['NegativePaths'], UniqueFailingEndpoints=value['UniqueFailingEndpoints'],
                  DetailedPathsScanned=value['DetailedPathsScanned'],
                  Families=[dict(Family=k, UniqueEndpoints=len(rows), WorstActualPath=min(rows, key=lambda r: r['SlackNS'])) for k, rows in classes.items()],
                  Report=value['Report'], ReferenceArtifacts=[ref(SOURCE), ref(TEXT)],
                  EDAExecuted=False, HardwareAccessed=False, RTLModified=False,
                  Limits=['Classification from saved detailed review only; original rtr not rescanned here.',
                          'Keeping CHECK chosen-way fault invalidation is required correctness; do not revert to the earlier prototype.',
                          'No single pipeline change is claimed to fix all six families; a new native implementation is required.'])
    destination = HERE.parent / 'assoc2way256-core-failure-small-summary-a.json'
    with destination.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(Summary=ref(destination), EndpointCounts=expected)))


if __name__ == '__main__':
    main()
