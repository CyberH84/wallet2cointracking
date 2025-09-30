"""
DeFi Protocol Configuration
Contains addresse        ]
    },
    'flare': {
        'router_addresses': [
            '0x6352a56caadc4f1e25cd6c21570aae1b9d1bc644',  # OpenOcean Router on Flare
        ],
        'methods': {
            'swap': '0x12aa3caf',
            'swap_eth': '0x7ff36ab5',
        }od signatures for various DeFi protocols
"""

# Aave V3 Protocol Addresses and Methods
AAVE_V3_CONFIG = {
    'arbitrum': {
        'pool_addresses': [
            '0x794a61358D6845594F94dc1DB02A252b5b4814aD',  # Aave V3 Pool
            '0x69FA688f1Dc47d4B5d8029D5a35FB7a548310654',  # Pool Data Provider
            '0x6Ae43d3271ff6888e7Fc43Fd7321a503ff738951',  # Aave V3 Pool V2
            '0x929EC64c34a17401F460460D4B9390518E5B473e',  # Aave V3 Pool Configurator
        ],
        'methods': {
            'supply': '0x617ba037',  # supply(address asset, uint256 amount, address onBehalfOf, uint16 referralCode)
            'withdraw': '0x693ec85e',  # withdraw(address asset, uint256 amount, address to)
            'borrow': '0xa415bcad',  # borrow(address asset, uint256 amount, uint256 interestRateMode, uint16 referralCode, address onBehalfOf)
            'repay': '0x573ade81',  # repay(address asset, uint256 amount, uint256 rateMode, address onBehalfOf)
            'liquidation_call': '0x80e670ae',  # liquidationCall(address collateralAsset, address debtAsset, address user, uint256 debtToCover, bool receiveAToken)
            'flashloan': '0xab9c4b5d',  # flashLoan
            'setUserUseReserveAsCollateral': '0x693ec85e',  # setUserUseReserveAsCollateral
        }
    },
    'flare': {
        'pool_addresses': [
            '0x2E4C9Ab8518A443a2EbB4371C24a8246B30b3446',  # Aave V3 Pool on Flare
        ],
        'methods': {
            'supply': '0x617ba037',
            'withdraw': '0x693ec85e',
            'borrow': '0xa415bcad',
            'repay': '0x573ade81',
        }
    }
}

# OpenOcean Protocol Addresses
OPENOCEAN_CONFIG = {
    'arbitrum': {
        'router_addresses': [
            '0x6352a56caadc4f1e25cd6c21570aae1b9d1bc644',  # OpenOcean Router
            '0x6E2B76966cbD9cF4cC2Fa0D76d24d5241E0ABC2F',  # OpenOcean Exchange
        ],
        'methods': {
            'swap': '0x12aa3caf',  # swapExactTokensForTokens
            'swap_eth': '0x7ff36ab5',  # swapExactETHForTokens
            'swap_tokens_for_eth': '0x18cbafe5',  # swapExactTokensForETH
            'swap_eth_for_tokens': '0x7ff36ab5',  # swapExactETHForTokens
        }
    },
    'flare': {
        'router_addresses': [
            '0x0000000000000000000000000000000000000000',  # Placeholder
        ],
        'methods': {
            'swap': '0x12aa3caf',
            'swap_eth': '0x7ff36ab5',
        }
    }
}

# Uniswap V3 Protocol (SparkDEX V3 is based on Uniswap V3)
UNISWAP_V3_CONFIG = {
    'arbitrum': {
        'router_addresses': [
            '0xE592427A0AEce92De3Edee1F18E0157C05861564',  # Uniswap V3 Router
            '0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45',  # Uniswap V3 Router 2
            '0x1F98431c8aD98523631AE4a59f267346ea31F984',  # Uniswap V3 Factory
        ],
        'methods': {
            'exact_input_single': '0x414bf389',  # exactInputSingle
            'exact_input': '0xc04b8d59',  # exactInput
            'exact_output_single': '0xdb3e2198',  # exactOutputSingle
            'exact_output': '0xf28c0498',  # exactOutput
            'mint': '0x88316456',  # mint
            'burn': '0xa34123a7',  # burn
            'collect': '0xfc6f7865',  # collect
            'swap': '0x128acb08',  # swap
        }
    },
    'flare': {
        'router_addresses': [
            '0x0000000000000000000000000000000000000000',  # Placeholder
        ],
        'methods': {
            'exact_input_single': '0x414bf389',
            'exact_input': '0xc04b8d59',
            'mint': '0x88316456',
            'burn': '0xa34123a7',
            'collect': '0xfc6f7865',
        }
    }
}

# SushiSwap Protocol
SUSHISWAP_CONFIG = {
    'arbitrum': {
        'router_addresses': [
            '0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506',  # SushiSwap Router
            '0xE592427A0AEce92De3Edee1F18E0157C05861564',  # SushiSwap Router V2
        ],
        'methods': {
            'swap_exact_tokens_for_tokens': '0x38ed1739',  # swapExactTokensForTokens
            'swap_exact_eth_for_tokens': '0x7ff36ab5',  # swapExactETHForTokens
            'swap_exact_tokens_for_eth': '0x18cbafe5',  # swapExactTokensForETH
            'add_liquidity': '0xe8e33700',  # addLiquidity
            'remove_liquidity': '0xbaa2abde',  # removeLiquidity
        }
    },
    'flare': {
        'router_addresses': [
            '0x0000000000000000000000000000000000000000',  # Placeholder
        ],
        'methods': {
            'swap_exact_tokens_for_tokens': '0x38ed1739',
            'add_liquidity': '0xe8e33700',
            'remove_liquidity': '0xbaa2abde',
        }
    }
}

# SparkDEX V3 Protocol (Uniswap V3 fork)
SPARKDEX_V3_CONFIG = {
    'arbitrum': {
        'router_address': '0x0Fc73040b26E9bC8514fA028D998E73A0E8584C8',  # SparkDEX V3 Router
        'factory_address': '0x0227628f3F023bb0B980b67D528571c95c6DaC1c',  # SparkDEX V3 Factory
        'methods': {
            'exact_input_single': '0x414bf389',  # exactInputSingle
            'exact_input': '0xc04b8d59',  # exactInput
            'mint': '0x88316456',  # mint
            'burn': '0xa34123a7',  # burn
            'collect': '0xfc6f7865',  # collect
        }
    },
    'flare': {
        'router_address': '0x96E5ac8b2Eab7A4C33e0b5AA2E7E87F32117048a',  # SparkDEX V3 Router on Flare
        'factory_address': '0x48C8613755D0b1aEd67B1Fd8fFD82BB821562E51',  # SparkDEX V3 Factory on Flare
        'methods': {
            'exact_input_single': '0x414bf389',
            'exact_input': '0xc04b8d59',
            'mint': '0x88316456',
            'burn': '0xa34123a7',
            'collect': '0xfc6f7865',
        }
    }
}

# Kinetic Market Protocol
KINETIC_MARKET_CONFIG = {
    'arbitrum': {
        'lending_pool': '0x2f123cF3F37CE3328CC9B5b8415f9EC5109b45e7',  # Kinetic Market Lending Pool
        'methods': {
            'deposit': '0x47e7ef24',  # deposit
            'withdraw': '0x693ec85e',  # withdraw
            'borrow': '0xa415bcad',  # borrow
            'repay': '0x573ade81',  # repay
        }
    },
    'flare': {
        'lending_pool': '0x70e36f6BF80a52b3B46b3aF8e106CC0ed743E8e4',  # Kinetic Market on Flare
        'methods': {
            'deposit': '0x47e7ef24',
            'withdraw': '0x693ec85e',
            'borrow': '0xa415bcad',
            'repay': '0x573ade81',
        }
    }
}

# Flare Network Native Staking
FLARE_STAKING_CONFIG = {
    'wflr_contract': '0x1D80c49BbBCd1C0911346656B529DF9E5c2F783d',  # WFLR contract
    'ftso_manager': '0x1000000000000000000000000000000000000003',  # FTSO Manager
    'methods': {
        'delegate': '0x5c19a95c',  # delegate
        'undelegate': '0x5c19a95c',  # undelegate
        'claim_rewards': '0x3d18b912',  # claimRewards
        'wrap': '0xd0e30db0',  # deposit (wrap)
        'unwrap': '0x2e1a7d4d',  # withdraw (unwrap)
    }
}

# Flare Network DeFi Protocols
FLARE_DEFI_PROTOCOLS = {
    'aave_v3': {
        'name': 'Aave V3',
        'addresses': [
            '0x2E4C9Ab8518A443a2EbB4371C24a8246B30b3446',  # Aave V3 Pool on Flare
        ],
        'methods': {
            'supply': '0x617ba037',
            'withdraw': '0x693ec85e',
            'borrow': '0xa415bcad',
            'repay': '0x573ade81',
            'flashloan': '0xab9c4b5d',
        }
    },
    'openocean': {
        'name': 'OpenOcean',
        'addresses': [
            '0x6352a56caadc4f1e25cd6c21570aae1b9d1bc644',  # OpenOcean Router on Flare
        ],
        'methods': {
            'swap': '0x12aa3caf',
            'swap_eth': '0x7ff36ab5',
            'swap_tokens_for_eth': '0x18cbafe5',
            'swap_eth_for_tokens': '0x7ff36ab5',
        }
    },
    'sparkdex_v3': {
        'name': 'SparkDEX V3',
        'addresses': [
            '0x96E5ac8b2Eab7A4C33e0b5AA2E7E87F32117048a',  # SparkDEX V3 Router on Flare
            '0x48C8613755D0b1aEd67B1Fd8fFD82BB821562E51',  # SparkDEX V3 Factory on Flare
        ],
        'methods': {
            'exact_input_single': '0x414bf389',
            'exact_input': '0xc04b8d59',
            'exact_output_single': '0xdb3e2198',
            'exact_output': '0xf28c0498',
            'mint': '0x88316456',
            'burn': '0xa34123a7',
            'collect': '0xfc6f7865',
            'swap': '0x128acb08',
        }
    },
    'kinetic_market': {
        'name': 'Kinetic Market',
        'addresses': [
            '0x70e36f6BF80a52b3B46b3aF8e106CC0ed743E8e4',  # Kinetic Market on Flare
        ],
        'methods': {
            'deposit': '0x47e7ef24',
            'withdraw': '0x693ec85e',
            'borrow': '0xa415bcad',
            'repay': '0x573ade81',
        }
    },
    'flare_network': {
        'name': 'Flare Network',
        'addresses': [
            '0x1D80c49BbBCd1C0911346656B529DF9E5c2F783d',  # WFLR contract
            '0x1000000000000000000000000000000000000003',  # FTSO Manager
        ],
        'methods': {
            'delegate': '0x5c19a95c',
            'undelegate': '0x5c19a95c',
            'claim_rewards': '0x3d18b912',
            'wrap': '0xd0e30db0',
            'unwrap': '0x2e1a7d4d',
        }
    },
    'flare_swap': {
        'name': 'FlareSwap',
        'addresses': [
            '0x1234567890123456789012345678901234567890',  # FlareSwap Router (placeholder)
            '0xabcdef1234567890abcdef1234567890abcdef12',  # FlareSwap Factory (placeholder)
        ],
        'methods': {
            'swap_exact_tokens_for_tokens': '0x38ed1739',
            'swap_exact_eth_for_tokens': '0x7ff36ab5',
            'add_liquidity': '0xe8e33700',
            'remove_liquidity': '0xbaa2abde',
        }
    },
    'flare_lending': {
        'name': 'Flare Lending',
        'addresses': [
            '0x9876543210987654321098765432109876543210',  # Flare Lending Pool (placeholder)
        ],
        'methods': {
            'supply': '0x617ba037',
            'withdraw': '0x693ec85e',
            'borrow': '0xa415bcad',
            'repay': '0x573ade81',
        }
    },
    'flare_dex': {
        'name': 'Flare DEX',
        'addresses': [
            '0x1111111111111111111111111111111111111111',  # Flare DEX Router (placeholder)
        ],
        'methods': {
            'swap': '0x12aa3caf',
            'trade': '0x128acb08',
        }
    }
}

# Additional Arbitrum DeFi Protocols
ARBITRUM_DEFI_PROTOCOLS = {
    'aave_v3': {
        'name': 'Aave V3',
        'addresses': [
            '0x794a61358D6845594F94dc1DB02A252b5b4814aD',  # Aave V3 Pool
            '0x69FA688f1Dc47d4B5d8029D5a35FB7a548310654',  # Pool Data Provider
            '0x6Ae43d3271ff6888e7Fc43Fd7321a503ff738951',  # Aave V3 Pool V2
            '0x929EC64c34a17401F460460D4B9390518E5B473e',  # Aave V3 Pool Configurator
        ],
        'methods': {
            'supply': '0x617ba037',
            'withdraw': '0x693ec85e',
            'borrow': '0xa415bcad',
            'repay': '0x573ade81',
            'liquidation_call': '0x80e670ae',
            'flashloan': '0xab9c4b5d',
        }
    },
    'openocean': {
        'name': 'OpenOcean',
        'addresses': [
            '0x6352a56caadc4f1e25cd6c21570aae1b9d1bc644',  # OpenOcean Router
            '0x6E2B76966cbD9cF4cC2Fa0D76d24d5241E0ABC2F',  # OpenOcean Exchange
        ],
        'methods': {
            'swap': '0x12aa3caf',
            'swap_eth': '0x7ff36ab5',
            'swap_tokens_for_eth': '0x18cbafe5',
            'swap_eth_for_tokens': '0x7ff36ab5',
        }
    },
    'sparkdex_v3': {
        'name': 'SparkDEX V3',
        'addresses': [
            '0x0Fc73040b26E9bC8514fA028D998E73A0E8584C8',  # SparkDEX V3 Router
            '0x0227628f3F023bb0B980b67D528571c95c6DaC1c',  # SparkDEX V3 Factory
        ],
        'methods': {
            'exact_input_single': '0x414bf389',
            'exact_input': '0xc04b8d59',
            'exact_output_single': '0xdb3e2198',
            'exact_output': '0xf28c0498',
            'mint': '0x88316456',
            'burn': '0xa34123a7',
            'collect': '0xfc6f7865',
            'swap': '0x128acb08',
        }
    },
    'kinetic_market': {
        'name': 'Kinetic Market',
        'addresses': [
            '0x2f123cF3F37CE3328CC9B5b8415f9EC5109b45e7',  # Kinetic Market Lending Pool
        ],
        'methods': {
            'deposit': '0x47e7ef24',
            'withdraw': '0x693ec85e',
            'borrow': '0xa415bcad',
            'repay': '0x573ade81',
        }
    },
    'curve': {
        'name': 'Curve Finance',
        'addresses': [
            '0x7D2768dE32b0b80b7a3454c06BdAc94A69DDc4A9',  # Curve Pool
            '0x8301AE4FC9C624DAD84C6F23A2F5C3B8F0A4B7C',  # Curve Router
        ],
        'methods': {
            'exchange': '0x3df02124',
            'add_liquidity': '0x4515cef3',
            'remove_liquidity': '0x1a4d01d2',
        }
    },
    'balancer': {
        'name': 'Balancer',
        'addresses': [
            '0xBA12222222228d8Ba445958a75a0704d566BF2C8',  # Balancer Vault
        ],
        'methods': {
            'swap': '0x52bbbe29',
            'join_pool': '0xb95db5bb',
            'exit_pool': '0x8bdb3913',
        }
    },
    'compound': {
        'name': 'Compound',
        'addresses': [
            '0x3d9819210A31b4961b30EF54bE2aeD79B9c9Cd3B',  # Compound Comptroller
        ],
        'methods': {
            'mint': '0xa0712d68',
            'redeem': '0xdb006a75',
            'borrow': '0xc5ebeaec',
            'repay_borrow': '0x0e752702',
        }
    }
}

# Additional token/protocol patterns (sample rules). These are used by the
# analyzer to detect protocol interactions heuristically via token symbol/name
# when explicit protocol addresses or method signatures are absent.
#
# Curve LP tokens typically have symbols like: '3CRV', '3pool', 'CRV', 'curve', 'LP',
# or names including 'Curve' or 'LP Token'. Example symbols/names (add real ones):
CURVE_LP_PATTERNS = {
    'symbols': [
        '3CRV', '3CRV-f', 'CRV', 'CRVLP', 'CURVE', 'CRV:', 'sCRV', 'yvBOOST', 'gusd3CRV'
    ],
    'names': ['curve', 'lp token', 'liquidity pool', 'curve.fi', 'curve lp']
}

# Angle protocol tokens may include 'agEUR', 'ANGLE', or names containing 'Angle'
ANGLE_PATTERNS = {
    'symbols': ['AGEUR', 'agEUR', 'ANGLE', 'ANGLE:agEUR'],
    'names': ['angle', 'angle protocol', 'agEUR', 'angle stable']
}

# Liquity protocol tokens: LUSD, LQTY, or names containing 'Liquity'
LIQUITY_PATTERNS = {
    'symbols': ['LUSD', 'LQTY', 'LQTY:'],
    'names': ['liquity', 'lusd', 'lqty', 'liquity protocol']
}


# Common ERC20 Methods
ERC20_METHODS = {
    'transfer': '0xa9059cbb',
    'approve': '0x095ea7b3',
    'transfer_from': '0x23b872dd',
}

# DeFi Protocol Categories
DEFI_CATEGORIES = {
    'lending': {
        'name': 'Lending',
        'protocols': ['aave_v3', 'kinetic_market'],
        'actions': ['supply', 'withdraw', 'borrow', 'repay']
    },
    'dex': {
        'name': 'DEX Trading',
        'protocols': ['openocean', 'sparkdex_v3'],
        'actions': ['swap', 'trade', 'exact_input_single', 'exact_input']
    },
    'liquidity': {
        'name': 'DEX Liquidity Mining',
        'protocols': ['sparkdex_v3'],
        'actions': ['mint', 'burn', 'collect']
    },
    'staking': {
        'name': 'Stacking (passiv)',
        'protocols': ['flare_staking'],
        'actions': ['delegate', 'undelegate', 'claim_rewards', 'wrap', 'unwrap']
    }
}

# Transaction Type Mapping
TRANSACTION_TYPES = {
    'supply': 'Deposit',
    'withdraw': 'Withdrawal',
    'borrow': 'Borrowing',
    'repay': 'Borrowing',
    'swap': 'Trade',
    'trade': 'Trade',
    'exact_input_single': 'Trade',
    'exact_input': 'Trade',
    'exact_output_single': 'Trade',
    'exact_output': 'Trade',
    'swap_exact_tokens_for_tokens': 'Trade',
    'swap_exact_eth_for_tokens': 'Trade',
    'swap_exact_tokens_for_eth': 'Trade',
    'add_liquidity': 'Deposit',
    'remove_liquidity': 'Withdrawal',
    'mint': 'Deposit',
    'burn': 'Withdrawal',
    'collect': 'Withdrawal',
    'delegate': 'Staking',
    'undelegate': 'Staking',
    'claim_rewards': 'Staking',
    'wrap': 'Deposit',
    'unwrap': 'Withdrawal',
    'exchange': 'Trade',
    'join_pool': 'Deposit',
    'exit_pool': 'Withdrawal',
    'redeem': 'Withdrawal',
    'repay_borrow': 'Borrowing',
    'interaction': 'Trade'
}

# Exchange Names
EXCHANGE_NAMES = {
    'aave_v3': 'Aave V3',
    'openocean': 'OpenOcean',
    'uniswap_v3': 'Uniswap V3',
    'sushiswap': 'SushiSwap',
    'sparkdex_v3': 'SparkDEX V3',
    'kinetic_market': 'Kinetic Market',
    'flare_network': 'Flare Network',
    'flare_staking': 'Flare Staking',
    'flare_swap': 'FlareSwap',
    'flare_lending': 'Flare Lending',
    'flare_dex': 'Flare DEX',
    'curve': 'Curve Finance',
    'balancer': 'Balancer',
    'compound': 'Compound'
}
