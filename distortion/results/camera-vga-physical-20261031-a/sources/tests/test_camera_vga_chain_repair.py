from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import run_camera_vga_chain_repair as chain


def change(pins):
    return {'Net': '_N188', 'Branch': 'M2:CLMA_357_546', 'Pins': pins}


def test_four_pin_continuous_chain_is_one_native_item():
    pins = 'ZDNE[0]:SRB_300_402>IDNE[0]:SRB_306_408>ZDNE[2]:SRB_306_570>IDNE[2]:SRB_312_576;'
    with chain.chain_mode():
        commands = chain.repair.route_commands([change(pins)])
    assert commands[2] == 'manual_route -net {_N188} -branch {M2:CLMA_357_546} -pins {' + pins + '}'


@pytest.mark.parametrize('pins', [
    'ZDNE[0]:SRB_300_402>IDNE[0]:SRB_306_408;ZDNE[2]:SRB_306_570>IDNE[2]:SRB_312_576;',
    'ZDNE[0]:SRB_300_402>IDNE[0]:SRB_306_408;;',
    'ZDNE[0]:SRB_300_402;',
    'ZDNE[0]:SRB_300_402>IDNE[0]:SRB_306_408; exec calc',
    'ZDNE[0]:SRB_300_402>[exec calc];',
])
def test_multiple_items_and_invalid_pin_chains_are_rejected(pins):
    with chain.chain_mode(), pytest.raises(ValueError, match='detour pin/site chain'):
        chain.repair.route_commands([change(pins)])


def test_wrapper_restores_frozen_module_runtime_bindings():
    pins, prepare = chain.repair.PINS, chain.repair.prepare_request
    with pytest.raises(RuntimeError):
        with chain.chain_mode():
            assert chain.repair.PINS == chain.PINS
            assert chain.repair.prepare_request is chain.prepare_request
            raise RuntimeError('test interrupted scope')
    assert chain.repair.PINS == pins
    assert chain.repair.prepare_request is prepare


def test_preflight_binds_wrapper_hash(monkeypatch):
    source = chain.repair.core.ORIGINAL
    monkeypatch.setattr(chain, 'ORIGINAL_PREPARE_REQUEST', lambda _: ({}, source, {}, []))
    _, _, watched, _ = chain.prepare_request('unused')
    assert watched[chain.SELF] == chain.repair.core.sha(chain.SELF)
