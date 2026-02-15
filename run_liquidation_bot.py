#!/usr/bin/env python3
"""
Flash Loan Liquidation Bot

Monitors Aave V3 borrower positions for health factor < 1.0
and executes profitable liquidations via FlashLoanLiquidator contract.

Separate from the arbitrage bot — can run independently.
"""

import os
import sys
import time
import signal
import logging
from dotenv import load_dotenv
from web3 import Web3

from src.liquidation_detector import LiquidationDetector
from src.liquidation_orchestrator import LiquidationOrchestrator
from src.utils.key_manager import load_private_key
from src.utils.logging_config import configure_logging

load_dotenv()

os.environ.setdefault("BOT_TYPE", "liquidation")
configure_logging(log_file="liquidation_bot.log")
logger = logging.getLogger(__name__)


class LiquidationBot:
    """
    Main liquidation bot that coordinates detector and orchestrator.
    """

    def __init__(
        self,
        web3: Web3,
        detector: LiquidationDetector,
        orchestrator: LiquidationOrchestrator,
        scan_interval: int = 30,
        lookback_blocks: int = 50000,
    ):
        self.web3 = web3
        self.detector = detector
        self.orchestrator = orchestrator
        self.scan_interval = scan_interval
        self.lookback_blocks = lookback_blocks

        self.running = False
        self.known_borrowers: set = set()
        self.stats = {
            'scans': 0,
            'liquidations_found': 0,
            'liquidations_executed': 0,
            'successful': 0,
            'failed': 0,
        }

    def discover_borrowers(self):
        """Discover new borrowers from recent blocks."""
        try:
            current_block = self.web3.eth.block_number
            from_block = max(0, current_block - self.lookback_blocks)
            new_borrowers = self.detector.discover_active_borrowers(from_block, current_block)
            before = len(self.known_borrowers)
            self.known_borrowers.update(new_borrowers)
            added = len(self.known_borrowers) - before
            if added > 0:
                logger.info(f"Discovered {added} new borrowers (total: {len(self.known_borrowers)})")
        except Exception as e:
            logger.error(f"Borrower discovery failed: {e}")

    def run(self):
        """Main loop: discover borrowers, scan for liquidations, execute."""
        self.running = True
        logger.info("=" * 60)
        logger.info("Flash Loan Liquidation Bot Starting")
        logger.info("=" * 60)

        # Get common debt and collateral assets
        debt_assets = [
            addr for addr in [
                os.getenv('USDC_ADDRESS'),
                os.getenv('USDT_ADDRESS'),
                os.getenv('DAI_ADDRESS'),
            ] if addr
        ]
        collateral_assets = [
            addr for addr in [
                os.getenv('WETH_ADDRESS'),
                os.getenv('WMATIC_ADDRESS'),
                os.getenv('WBTC_ADDRESS'),
            ] if addr
        ]

        if not debt_assets or not collateral_assets:
            logger.error(
                "Missing token addresses. Set USDC_ADDRESS, USDT_ADDRESS, DAI_ADDRESS, "
                "WETH_ADDRESS, WMATIC_ADDRESS, WBTC_ADDRESS env vars."
            )
            sys.exit(1)

        logger.info(f"Monitoring {len(debt_assets)} debt assets and {len(collateral_assets)} collateral assets")

        # Initial borrower discovery
        logger.info("Discovering active borrowers...")
        self.discover_borrowers()

        try:
            while self.running:
                self.stats['scans'] += 1

                # Refresh borrowers periodically (every 10 scans)
                if self.stats['scans'] % 10 == 0:
                    self.discover_borrowers()

                try:
                    if not self.known_borrowers:
                        logger.debug("No known borrowers, skipping scan")
                        time.sleep(self.scan_interval)
                        continue

                    # Scan for liquidatable positions
                    opportunities = self.detector.scan_for_liquidations(
                        users=list(self.known_borrowers),
                        debt_assets=debt_assets,
                        collateral_assets=collateral_assets,
                    )

                    if opportunities:
                        self.stats['liquidations_found'] += len(opportunities)
                        logger.info(f"Found {len(opportunities)} liquidation opportunities!")

                        # Sort by profit descending
                        opportunities.sort(key=lambda x: x.get('net_profit_usd', 0), reverse=True)

                        # Execute the most profitable ones
                        results = self.orchestrator.execute_batch(opportunities[:5])
                        for result in results:
                            self.stats['liquidations_executed'] += 1
                            if result['success']:
                                self.stats['successful'] += 1
                            else:
                                self.stats['failed'] += 1

                except Exception as e:
                    logger.error(f"Scan error: {e}")

                # Log stats periodically
                if self.stats['scans'] % 5 == 0:
                    logger.info(
                        f"Stats: scans={self.stats['scans']} "
                        f"found={self.stats['liquidations_found']} "
                        f"executed={self.stats['liquidations_executed']} "
                        f"success={self.stats['successful']} "
                        f"borrowers={len(self.known_borrowers)}"
                    )

                time.sleep(self.scan_interval)

        except KeyboardInterrupt:
            logger.info("Liquidation bot stopped by user")

        self.running = False
        logger.info(f"Final stats: {self.stats}")

    def stop(self):
        self.running = False


def main():
    logger.info("=" * 60)
    logger.info("Flash Loan Liquidation Bot")
    logger.info("=" * 60)

    # Required env vars
    rpc_url = os.getenv("POLYGON_RPC_URL", "http://localhost:8545")
    pool_provider = os.getenv("AAVE_POOL_PROVIDER")
    data_provider = os.getenv("AAVE_DATA_PROVIDER")
    liquidator_address = os.getenv("FLASH_LOAN_LIQUIDATOR_ADDRESS")
    v3_adapter = os.getenv("UNISWAP_V3_ADAPTER_ADDRESS")
    v2_adapter = os.getenv("UNISWAP_V2_ADAPTER_ADDRESS")

    missing = []
    for name, val in [
        ("AAVE_POOL_PROVIDER", pool_provider),
        ("AAVE_DATA_PROVIDER", data_provider),
        ("FLASH_LOAN_LIQUIDATOR_ADDRESS", liquidator_address),
        ("UNISWAP_V3_ADAPTER_ADDRESS", v3_adapter),
        ("UNISWAP_V2_ADAPTER_ADDRESS", v2_adapter),
    ]:
        if not val:
            missing.append(name)

    if missing:
        logger.error(f"Missing env vars: {', '.join(missing)}")
        sys.exit(1)

    private_key = load_private_key()
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    min_profit_usd = float(os.getenv("LIQUIDATION_MIN_PROFIT_USD", "50"))
    scan_interval = int(os.getenv("LIQUIDATION_SCAN_INTERVAL", "30"))

    # Connect to chain
    http_timeout = int(os.getenv("WEB3_HTTP_TIMEOUT", "30"))
    web3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': http_timeout}))
    if not web3.is_connected():
        logger.error("Failed to connect to blockchain")
        sys.exit(1)
    logger.info(f"Connected to blockchain (Chain ID: {web3.eth.chain_id})")

    # Resolve Pool address from provider
    provider_abi = [
        {
            "inputs": [],
            "name": "getPool",
            "outputs": [{"type": "address", "name": ""}],
            "stateMutability": "view",
            "type": "function",
        }
    ]
    provider_contract = web3.eth.contract(
        address=web3.to_checksum_address(pool_provider),
        abi=provider_abi,
    )
    pool_address = provider_contract.functions.getPool().call()
    logger.info(f"Aave Pool: {pool_address}")

    # Initialize components
    detector = LiquidationDetector(
        web3=web3,
        pool_address=pool_address,
        data_provider_address=data_provider,
        min_profit_usd=min_profit_usd,
    )

    orchestrator = LiquidationOrchestrator(
        web3=web3,
        liquidator_address=liquidator_address,
        private_key=private_key,
        v3_adapter_address=v3_adapter,
        v2_adapter_address=v2_adapter,
        dry_run=dry_run,
        curve_adapter_address=os.getenv("CURVE_ADAPTER_ADDRESS"),
    )

    bot = LiquidationBot(
        web3=web3,
        detector=detector,
        orchestrator=orchestrator,
        scan_interval=scan_interval,
    )

    def handle_sigterm(signum, frame):
        logger.info("Received SIGTERM, shutting down...")
        bot.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_sigterm)

    try:
        bot.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
