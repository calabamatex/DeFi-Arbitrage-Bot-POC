#!/usr/bin/env python3
"""
Dry-Run Mainnet Validator

Runs the OpportunityDetector in read-only mode against a live RPC or mainnet
fork (Anvil/Hardhat) to validate opportunity detection and profitability
calculations. No transactions are submitted.

Usage:
    python scripts/dry_run_mainnet.py --chain polygon
    python scripts/dry_run_mainnet.py --chain polygon --duration 60 --verbose
    python scripts/dry_run_mainnet.py --rpc-url http://127.0.0.1:8545
"""
import argparse
import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv

load_dotenv()
from web3 import Web3

from src.config import Config
from src.opportunity_detector import OpportunityDetector

logger = logging.getLogger("dry_run")

G = lambda m: f"\033[92m{m}\033[0m"
R = lambda m: f"\033[91m{m}\033[0m"
Y = lambda m: f"\033[93m{m}\033[0m"


def main():
    p = argparse.ArgumentParser(description="Dry-run arbitrage bot (read-only)")
    p.add_argument("--chain", default="polygon", choices=list(Config.CHAINS.keys()))
    p.add_argument("--duration", type=int, default=300, help="Seconds (default 300)")
    p.add_argument("--rpc-url", default=None, help="Override RPC (e.g. Anvil fork)")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    rpc = args.rpc_url or (
        Config.CHAINS[args.chain].rpc_url
        if args.chain in Config.CHAINS
        else sys.exit(R(f"Unknown chain: {args.chain}"))
    )

    http_timeout = int(os.getenv("WEB3_HTTP_TIMEOUT", "30"))
    print(f"\n  Connecting to {rpc[:60]}...")
    w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": http_timeout}))
    if not w3.is_connected():
        print(R("  Connection failed"))
        sys.exit(1)

    chain_id = w3.eth.chain_id
    block = w3.eth.block_number
    gas_gwei = float(Web3.from_wei(w3.eth.gas_price, "gwei"))
    print(G(f"  Connected: chain_id={chain_id}, block={block}, gas={gas_gwei:.2f} gwei"))

    detector = OpportunityDetector(
        web3=w3,
        min_profit_usd=float(os.getenv("MIN_PROFIT_USD", "1.0")),
        max_gas_price_gwei=int(os.getenv("MAX_GAS_PRICE_GWEI", "100")),
        check_interval=int(os.getenv("CHECK_INTERVAL", "10")),
        min_flash_loan=int(os.getenv("MIN_FLASH_LOAN_USD", "500")) * 10**6,
        max_flash_loan=int(os.getenv("MAX_FLASH_LOAN_USD", "100000")) * 10**6,
    )

    total_opps = 0
    profitable_opps = 0
    cycles = 0
    start = time.monotonic()
    scan_interval = 10

    print(f"\n  Scanning for {args.duration}s (interval: {scan_interval}s)...\n")

    try:
        while (time.monotonic() - start) < args.duration:
            cycles += 1
            elapsed = time.monotonic() - start
            logger.info("Cycle %d (%.0fs elapsed)", cycles, elapsed)

            scan_start = time.time()
            opportunities = detector.scan_opportunities()
            scan_ms = (time.time() - scan_start) * 1000

            if opportunities:
                total_opps += len(opportunities)
                for opp in opportunities:
                    net = opp.get("net_profit", 0)
                    pair = f"{opp.get('token_in', '?')[:10]}/{opp.get('token_out', '?')[:10]}"
                    direction = opp.get("direction", "?")
                    tag = G("PROFIT") if net > 0 else Y("MARGINAL")
                    if net > 0:
                        profitable_opps += 1
                    if args.verbose:
                        print(
                            f"  [{tag}] {pair} direction={direction} "
                            f"net_profit={net} scan={scan_ms:.0f}ms"
                        )
            else:
                if args.verbose:
                    print(f"  Cycle {cycles}: no opportunities (scan={scan_ms:.0f}ms)")

            remaining = args.duration - (time.monotonic() - start)
            if remaining > 0:
                time.sleep(min(scan_interval, remaining))

    except KeyboardInterrupt:
        print(Y("\n  Interrupted."))

    elapsed = time.monotonic() - start
    end_block = w3.eth.block_number

    print(f"\n{'='*64}")
    print(f"  DRY-RUN VALIDATION REPORT")
    print(f"{'='*64}")
    print(f"  Chain:          {args.chain} (ID:{chain_id})")
    print(f"  RPC:            {rpc[:60]}")
    print(f"  Blocks:         {block} -> {end_block}")
    print(f"  Duration:       {elapsed:.1f}s ({cycles} cycles)")
    print(f"  Opportunities:  {total_opps}")
    print(f"  Profitable:     {profitable_opps}")
    print(f"{'='*64}\n")


if __name__ == "__main__":
    main()
