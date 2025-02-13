#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
          Copyright Blaze 2021.
 Distributed under the Boost Software License, Version 1.0.
    (See accompanying file LICENSE_1_0.txt or copy at
          https://www.boost.org/LICENSE_1_0.txt)
"""

from typing import Literal, Optional, List, Any, Tuple, Union, Dict
from decimal import Decimal

from web3.types import BlockIdentifier
import web3.exceptions
from web3 import Web3

from .data import BRIDGE_CONFIG, SYN_DATA, MAX_UINT8, SYN_DECIMALS
from .helpers import handle_decimals
from .cache import timed_cache

_TokenInfo = Tuple[int, str, int, int, int, int, int, int, bool, bool]


# TODO(blaze): better type hints.
def call_abi(data, key: str, func_name: str, *args, **kwargs) -> Any:
    call_args = kwargs.pop('call_args', {})
    return getattr(data[key].functions, func_name)(*args,
                                                   **kwargs).call(**call_args)


@timed_cache(60)
def get_all_tokens_in_pool(chain: str,
                           max_index: Optional[int] = None,
                           func: str = 'pool_contract') -> List[str]:
    """
    Get all tokens by calling `getToken` by iterating from 0 till a
    contract error or `max_index` and implicitly sorted by index.

    Args:
        chain (str): the EVM chain
        max_index (Optional[int], optional): max index to iterate to. 
            Defaults to None.

    Returns:
        List[str]: list of token addresses
    """

    assert (chain in SYN_DATA)

    data = SYN_DATA[chain]
    res: List[str] = []

    for i in range(max_index or MAX_UINT8):
        try:
            res.append(call_abi(data, func, 'getToken', i))
        except (web3.exceptions.ContractLogicError,
                web3.exceptions.BadFunctionCallOutput):
            # Out of range.
            break

    return res


@timed_cache(60, maxsize=50)
def get_virtual_price(
        chain: str,
        block: Union[int, str] = 'latest',
        func: str = 'pool_contract') -> Dict[str, Dict[str, Decimal]]:
    ret = call_abi(SYN_DATA[chain],
                   func,
                   'getVirtualPrice',
                   call_args={'block_identifier': block})

    # 18 Decimals.
    return {chain: {func: handle_decimals(ret, 18)}}


def get_balance_of(w3: Web3,
                   token: str,
                   target: str,
                   decimals: int = None,
                   block: BlockIdentifier = 'latest') -> Union[Decimal, int]:
    ABI = """[{"inputs":[{"internalType":"address","name":"account","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"}]"""
    contract = w3.eth.contract(w3.toChecksumAddress(token), abi=ABI)

    ret = contract.functions.balanceOf(target).call(block_identifier=block)

    if decimals is not None:
        return handle_decimals(ret, decimals)

    return ret


def get_synapse_emissions(chain: str,
                          block: BlockIdentifier = 'latest',
                          multiplier: int = None) -> Decimal:
    contract = SYN_DATA[chain]['minichef_contract']
    ret = contract.functions.synapsePerSecond().call(block_identifier=block)
    ret = handle_decimals(ret, SYN_DECIMALS)

    if multiplier is None:
        return ret
    elif not isinstance(multiplier, Decimal):
        _multiplier = Decimal(multiplier)
    else:
        _multiplier = multiplier

    return ret * _multiplier


def get_bridge_token_info(chain: str,
                          token: str) -> Union[Literal[False], _TokenInfo]:
    from syn.utils.explorer.data import CHAINS

    chain_id = {v: k for k, v in CHAINS.items()}[chain]
    token = Web3.toChecksumAddress(token)

    ret = BRIDGE_CONFIG.functions.getToken(token, chain_id).call()
    # Does not exist - function's default ret.
    if ret == (0, '0x0000000000000000000000000000000000000000', 0, 0, 0, 0, 0,
               0, False, False):
        return False

    return ret
