#!/usr/bin/env python3
"""
Dry-Run Mainnet Fork Validator

Runs the bot in read-only mode against a mainnet fork (Anvil/Hardhat) or live
RPC to validate opportunity detection and profit calculations. No transactions
are submitted.

Usage:
    python scripts/dry_run_mainnet.py --chain polygon
    python scripts/dry_run_mainnet.py --chain polygon --duration 60 --verbose
    python scripts/dry_run_mainnet.py --rpc-url http://127.0.0.1:8545
"""
import argparse, asyncio, logging, os, sys, time
from decimal import Decimal
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv; load_dotenv()
from web3 import Web3

from src.config import Config
from src.bot.arbitrage import (
    ArbitrageOpportunity, calculate_arbitrage,
    calculate_gas_cost, is_profitable, GAS_LIMIT,
)
from src.dex.quickswap import QuickSwap
from src.dex.sushiswap import SushiSwap
logger = logging.getLogger("dry_run")
FLASH_LOAN_FEE_BPS = Decimal("9")  # Aave V3: 0.09%
TOKEN_PAIRS = [("WETH","USDC"),("WETH","USDT"),("WETH","DAI"),("USDC","USDT"),("USDC","DAI")]

CHAIN_TOKENS: Dict[str, Dict] = {
    "polygon": {
        "WETH": {"address": "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619", "decimals": 18},
        "USDC": {"address": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174", "decimals": 6},
        "USDT": {"address": "0xc2132D05D31c914a87C6611C10748AEb04B58e8F", "decimals": 6},
        "DAI":  {"address": "0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063", "decimals": 18},
    },
    "arbitrum": {
        "WETH": {"address": "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1", "decimals": 18},
        "USDC": {"address": "0xaf88d065e77c8cC2239327C5EDb3A432268e5831", "decimals": 6},
        "USDT": {"address": "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9", "decimals": 6},
        "DAI":  {"address": "0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1", "decimals": 18},
    },
}
CHAIN_ROUTERS: Dict[str, Dict[str, str]] = {
    "polygon":  {"quickswap": "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff",
                 "sushiswap": "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506"},
    "arbitrum": {"sushiswap": "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506"},
}

G = lambda m: f"\033[92m{m}\033[0m"
R = lambda m: f"\033[91m{m}\033[0m"
Y = lambda m: f"\033[93m{m}\033[0m"


def validate_connectivity(w3: Web3, chain_cfg) -> Dict:
    """Check RPC connection, chain ID, block number, gas price."""
    if not w3.is_connected():
        raise ConnectionError("RPC endpoint is not reachable")
    info = {"chain_id": w3.eth.chain_id, "block": w3.eth.block_number,
            "gas_gwei": float(Web3.from_wei(w3.eth.gas_price, "gwei"))}
    if chain_cfg and info["chain_id"] != chain_cfg.chain_id:
        logger.warning("Chain ID mismatch: expected %d, got %d (fork?)",
                       chain_cfg.chain_id, info["chain_id"])
    return info


def build_dexes(chain: str) -> Dict:
    routers = CHAIN_ROUTERS.get(chain, {})
    dexes: Dict = {}
    for name, addr in routers.items():
        cls = {"quickswap": QuickSwap, "sushiswap": SushiSwap}.get(name)
        if cls:
            dexes[name] = cls(router_address=addr, name=name.capitalize())
    return dexes


async def scan_once(w3, dexes, tokens) -> List[ArbitrageOpportunity]:
    opps = []
    for ta, tb in TOKEN_PAIRS:
        if ta not in tokens or tb not in tokens:
            continue
        try:
            opp = await calculate_arbitrage(ta, tb, w3, dexes, tokens)
            if opp:
                opps.append(opp)
        except Exception as e:
            logger.debug("Scan %s/%s error: %s", ta, tb, e)
    return opps


async def simulate(opp: ArbitrageOpportunity, w3: Web3) -> Dict:
    gas_cost = await calculate_gas_cost(w3, GAS_LIMIT * 2)
    trade_usd = opp.amount * opp.buy_price
    flash_fee = trade_usd * FLASH_LOAN_FEE_BPS / Decimal("10000")
    gross = opp.expected_profit * opp.amount
    net = gross - gas_cost - flash_fee
    is_prof, _ = await is_profitable(opp, w3)
    return {"pair": f"{opp.token1}/{opp.token2}", "buy_dex": opp.buy_dex,
            "sell_dex": opp.sell_dex, "buy_price": opp.buy_price,
            "sell_price": opp.sell_price, "gross_pct": opp.profit_percent,
            "gas_usd": gas_cost, "fee_usd": flash_fee, "net_usd": net,
            "execute": is_prof and net > 0}


def print_report(rpt: Dict) -> None:
    print(f"\n{'='*64}\n  DRY-RUN MAINNET VALIDATION REPORT\n{'='*64}")
    for k in ("chain","rpc","blocks","duration","opportunities","profitable"):
        print(f"  {k.capitalize()+':':<16} {rpt[k]}")
    print(f"{'='*64}")
    results = rpt["results"]
    if results:
        hdr = f"  {'Pair':<12}{'Route':<26}{'Gross%':>8}{'Gas$':>8}{'Fee$':>8}{'Net$':>10}{'Exec?':>7}"
        print(f"\n{hdr}\n  {'-'*79}")
        for r in results:
            route = f"{r['buy_dex']} -> {r['sell_dex']}"
            net_s = G(f"{r['net_usd']:>10.4f}") if r["net_usd"] > 0 else R(f"{r['net_usd']:>10.4f}")
            ex_s = G("YES") if r["execute"] else R("NO")
            print(f"  {r['pair']:<12}{route:<26}{r['gross_pct']:>7.3f}%"
                  f"{r['gas_usd']:>8.4f}{r['fee_usd']:>8.4f}{net_s}{ex_s:>7}")
    else:
        print(Y("\n  No opportunities detected. Markets may be efficient or RPC stale."))
    print(f"\n{'='*64}\n")


async def run(chain: str, rpc_url: str, duration: int, verbose: bool) -> int:
    chain_cfg = Config.CHAINS.get(chain)
    tokens = CHAIN_TOKENS.get(chain, {})
    dexes = build_dexes(chain)
    if not dexes:
        print(R(f"No DEX routers for chain: {chain}")); return 1
    if not tokens:
        print(R(f"No tokens for chain: {chain}")); return 1

    w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 15}))
    print(f"\n  Connecting to {rpc_url[:60]}...")
    try:
        info = validate_connectivity(w3, chain_cfg)
    except ConnectionError as e:
        print(R(f"  Connection failed: {e}")); return 1
    print(G(f"  Connected: chain_id={info['chain_id']}, block={info['block']}, "
            f"gas={info['gas_gwei']:.2f} gwei"))

    for d in dexes.values():
        d.initialize_contract(w3)
    print(f"  DEXes: {', '.join(dexes.keys())}")

    rpt = {"chain": f"{chain} (ID:{info['chain_id']})", "rpc": rpc_url[:60],
           "blocks": str(info["block"]), "duration": "", "opportunities": 0,
           "profitable": 0, "results": []}

    scan_interval, cycles, start = 10, 0, time.monotonic()
    print(f"\n  Scanning for {duration}s (interval: {scan_interval}s)...\n")
    try:
        while (time.monotonic() - start) < duration:
            cycles += 1
            logger.info("Cycle %d (%.0fs elapsed)", cycles, time.monotonic() - start)
            for opp in await scan_once(w3, dexes, tokens):
                rpt["opportunities"] += 1
                res = await simulate(opp, w3)
                rpt["results"].append(res)
                if res["execute"]:
                    rpt["profitable"] += 1
                if verbose:
                    tag = G("PROFIT") if res["execute"] else Y("NOEXEC")
                    print(f"  [{tag}] {res['pair']} {res['buy_dex']}->{res['sell_dex']} "
                          f"gross={res['gross_pct']:.3f}% net=${res['net_usd']:.4f}")
            remaining = duration - (time.monotonic() - start)
            if remaining > 0:
                await asyncio.sleep(min(scan_interval, remaining))
    except KeyboardInterrupt:
        print(Y("\n  Interrupted."))

    elapsed = time.monotonic() - start
    rpt["duration"] = f"{elapsed:.1f}s ({cycles} cycles)"
    rpt["blocks"] += f" -> {w3.eth.block_number}"
    print_report(rpt)
    return 0


def main():
    p = argparse.ArgumentParser(description="Dry-run arbitrage bot (read-only)")
    p.add_argument("--chain", default="polygon", choices=list(Config.CHAINS.keys()))
    p.add_argument("--duration", type=int, default=300, help="Seconds (default 300)")
    p.add_argument("--rpc-url", default=None, help="Override RPC (e.g. Anvil fork)")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                        handlers=[logging.StreamHandler(sys.stdout)])
    rpc = args.rpc_url or (Config.CHAINS[args.chain].rpc_url if args.chain in Config.CHAINS
                           else sys.exit(R(f"Unknown chain: {args.chain}")))
    sys.exit(asyncio.run(run(args.chain, rpc, args.duration, args.verbose)))


if __name__ == "__main__":
    main()
