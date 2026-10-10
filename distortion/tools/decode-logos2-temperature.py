"""Decode a supplied 12-bit conversion code. Does not contact hardware."""
import argparse
import json

def decode_code12(code):
    if not 0 <= code <= 4095:
        raise ValueError('Expected the extracted 12-bit ADC code, not a 16-bit status word or JTAG status bit')
    # Logos2 ADC User Guide V1.3, chapter 2 temperature monitor, printed p.8.
    return (code * 1219 - 2731500) / 10000

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--code12', required=True, type=lambda s: int(s, 0))
    args = parser.parse_args()
    print(json.dumps({'provided_adc_code12': args.code12, 'computed_temperature_celsius': decode_code12(args.code12),
                      'hardware_accessed': False,
                      'limits': 'Only converts a supplied code. A real measurement requires ADC configuration, completed temperature conversion and a fresh DRDY-confirmed status read. Does not infer temperature from over_temp.'}, indent=2))
