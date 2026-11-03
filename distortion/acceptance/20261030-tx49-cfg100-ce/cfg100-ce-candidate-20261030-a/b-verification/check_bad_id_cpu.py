"""Two-state Boolean check only; no RTL, EDA, network, or device access.

bank_diff and crc_diff exhaust the equality outcomes used by the predicate.
The independent contract uses an integer clockwise distance, not a sign bit.
"""
from pathlib import Path
import hashlib
import itertools
import json
import random
import time

HERE = Path(__file__).resolve().parent
SEED = 0xCE20261030


def original(width, gid, last, valid, bank_diff, crc_diff):
    difference = (gid - last) & ((1 << width) - 1)
    is_newer = difference != 0 and not bool(difference & (1 << (width - 1)))
    return gid == 0 or (valid and gid != last and not is_newer) or (
        valid and gid == last and (bank_diff or crc_diff))


def simplified(width, gid, last, valid, bank_diff, crc_diff):
    difference = (gid - last) & ((1 << width) - 1)
    return gid == 0 or (valid and (bool(difference & (1 << (width - 1))) or (
        gid == last and (bank_diff or crc_diff))))


def integer_contract(width, gid, last, valid, bank_diff, crc_diff):
    if gid == 0:
        return True
    if not valid:
        return False
    if gid == last:
        return bool(bank_diff or crc_diff)
    modulus = pow(2, width)
    forward = gid - last if gid > last else modulus - last + gid
    return not (0 < forward < modulus // 2)


def check(width, gid, last, valid, bank_diff, crc_diff):
    values = tuple(bool(f(width, gid, last, valid, bank_diff, crc_diff))
                   for f in (original, simplified, integer_contract))
    if not (values[0] == values[1] == values[2]):
        raise AssertionError(dict(width=width, gid=gid, last=last, valid=valid,
                                  bank_diff=bank_diff, crc_diff=crc_diff,
                                  outputs=values))
    return values[0]


def main():
    start = time.perf_counter()
    flags = list(itertools.product((False, True), repeat=3))
    exhaustive = {}
    for width in range(2, 8):
        cases = bad = 0
        for gid in range(1 << width):
            for last in range(1 << width):
                for valid, bd, cd in flags:
                    bad += check(width, gid, last, valid, bd, cd)
                    cases += 1
        exhaustive[str(width)] = dict(cases=cases, bad=bad, allowed=cases-bad)
    anchors = (0, 1, 2, 0x7fffffff, 0x80000000, 0x80000001,
               0xfffffffe, 0xffffffff)
    anchor_cases = 0
    for gid, last in itertools.product(anchors, repeat=2):
        for valid, bd, cd in flags:
            check(32, gid, last, valid, bd, cd)
            anchor_cases += 1
    # Deliberate boundary cases include forward/backward wrap and exact half-range.
    examples = [
        ('zero_reserved_even_invalid',0,0,False,False,False,True),
        ('zero_reserved_after_max',0,0xffffffff,True,False,False,True),
        ('initial_nonzero_with_mismatches',1,0xffffffff,False,True,True,False),
        ('forward_one',2,1,True,False,False,False),
        ('backward_one',1,2,True,False,False,True),
        ('largest_forward_gap',0x80000000,1,True,False,False,False),
        ('exact_half_range',0x80000001,1,True,False,False,True),
        ('past_half_range',0x80000002,1,True,False,False,True),
        ('forward_wrap_max_to_one',1,0xffffffff,True,False,False,False),
        ('backward_wrap_one_to_max',0xffffffff,1,True,False,False,True),
        ('same_id_match',1,1,True,False,False,False),
        ('same_id_bank_mismatch',1,1,True,True,False,True),
        ('same_id_crc_mismatch',1,1,True,False,True,True),
        ('same_id_both_mismatch',1,1,True,True,True,True),
        ('new_id_ignores_old_bank_crc',2,1,True,True,True,False),
        ('invalid_last_ignores_backward',1,2,False,True,True,False),
        ('invalid_last_ignores_half_range',0x80000001,1,False,True,True,False),
        ('half_range_from_zero',0x80000000,0,True,False,False,True),
    ]
    vectors = []
    for name, gid, last, valid, bd, cd, expected in examples:
        got = check(32, gid, last, valid, bd, cd)
        assert got == expected, name
        vectors.append(dict(name=name, gid=f'0x{gid:08x}', last=f'0x{last:08x}',
                            last_valid=valid, bank_diff=bd, crc_diff=cd,
                            bad_id=got, outcome='reject' if got else 'allow'))
    rng = random.Random(SEED)
    random_cases = 100000
    targeted_random_cases = 20000
    for _ in range(random_cases):
        check(32, rng.getrandbits(32), rng.getrandbits(32),
              *flags[rng.randrange(len(flags))])
    offsets = (0, 1, 2, 0x7fffffff, 0x80000000, 0x80000001, 0xfffffffe, 0xffffffff)
    for _ in range(targeted_random_cases):
        last = rng.getrandbits(32)
        gid = (last + rng.choice(offsets)) % 0x100000000
        check(32, gid, last, *flags[rng.randrange(len(flags))])
    elapsed = time.perf_counter() - start
    assert elapsed < 30, f'CPU-check wall time exceeded limit: {elapsed}'
    result = dict(status='PASS', mismatch_count=0, seed=f'0x{SEED:x}',
                  small_width_exhaustive=exhaustive,
                  small_width_cases=sum(v['cases'] for v in exhaustive.values()),
                  anchors_32bit=anchor_cases, explicit_vectors=len(vectors),
                  uniform_random_32bit=random_cases,
                  targeted_random_32bit=targeted_random_cases,
                  total_cases=sum(v['cases'] for v in exhaustive.values())+
                  anchor_cases+len(vectors)+random_cases+targeted_random_cases,
                  elapsed_wall_seconds=elapsed,
                  script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  scope='Two-state numeric predicate only; not X/Z equivalence, MTBF, RTL simulation, timing validation, or a formal proof.')
    (HERE / 'bad_id_cpu_results.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    (HERE / 'bad_id_boundary_vectors.json').write_text(json.dumps(vectors, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
    for v in vectors:
        print(f"{v['name']}: gid={v['gid']} last={v['last']} valid={int(v['last_valid'])} bank_diff={int(v['bank_diff'])} crc_diff={int(v['crc_diff'])} -> {v['outcome']}")


if __name__ == '__main__':
    main()
