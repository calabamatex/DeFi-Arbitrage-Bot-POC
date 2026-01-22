#!/usr/bin/env python3
"""
Flash Loan Arbitrage Bot - Main Runner

Runs both the Opportunity Detector and Flash Loan Orchestrator together.
"""

import os
import sys
import time
import logging
import threading
from typing import Optional
from dotenv import load_dotenv
from web3 import Web3

from src.opportunity_detector import OpportunityDetector
from src.flash_loan_orchestrator import FlashLoanOrchestrator
from src.db.database import check_db_connection

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class ArbitrageBot:
    """
    Main arbitrage bot that coordinates detector and orchestrator.
    """

    def __init__(
        self,
        web3: Web3,
        detector: OpportunityDetector,
        orchestrator: FlashLoanOrchestrator,
        direct_execution: bool = True
    ):
        """
        Initialize the bot.

        Args:
            web3: Web3 instance
            detector: Opportunity detector instance
            orchestrator: Flash loan orchestrator instance
            direct_execution: If True, execute immediately. If False, use database queue.
        """
        self.web3 = web3
        self.detector = detector
        self.orchestrator = orchestrator
        self.direct_execution = direct_execution

        self.running = False
        self.stats = {
            'scans': 0,
            'opportunities_found': 0,
            'opportunities_executed': 0,
            'successful_executions': 0,
            'failed_executions': 0,
            'total_profit': 0
        }

        logger.info("ArbitrageBot initialized")
        logger.info(f"Direct execution mode: {direct_execution}")

    def run_detector_loop(self):
        """Run the detector in a loop."""
        logger.info("🔍 Starting Detector Loop")

        try:
            while self.running:
                self.stats['scans'] += 1

                try:
                    # Scan for opportunities
                    opportunities = self.detector.scan_opportunities()

                    if opportunities:
                        self.stats['opportunities_found'] += len(opportunities)
                        logger.info(f"🎯 Found {len(opportunities)} opportunities!")

                        if self.direct_execution:
                            # Execute immediately
                            for opp in opportunities:
                                self.execute_opportunity(opp)
                        # else: opportunities are already logged to database
                        # and orchestrator will pick them up

                except Exception as e:
                    logger.error(f"Detector loop error: {e}")

                # Wait before next scan
                time.sleep(self.detector.check_interval)

        except KeyboardInterrupt:
            logger.info("Detector loop stopped by user")

    def run_orchestrator_loop(self):
        """Run the orchestrator in monitor mode."""
        logger.info("⚡ Starting Orchestrator Loop")

        try:
            self.orchestrator.monitor_opportunities(
                check_interval=5
            )
        except KeyboardInterrupt:
            logger.info("Orchestrator loop stopped by user")

    def execute_opportunity(self, opportunity: dict):
        """
        Execute a single opportunity.

        Args:
            opportunity: Opportunity dict from detector
        """
        self.stats['opportunities_executed'] += 1

        logger.info(f"\n{'='*60}")
        logger.info(f"Executing Opportunity #{self.stats['opportunities_executed']}")
        logger.info(f"{'='*60}")

        result = self.orchestrator.execute_opportunity(opportunity)

        if result['success']:
            self.stats['successful_executions'] += 1
            self.stats['total_profit'] += result['profit']
            logger.info(f"✅ Execution #{self.stats['successful_executions']} successful!")
        else:
            self.stats['failed_executions'] += 1
            logger.error(f"❌ Execution failed: {result.get('error')}")

        self.print_stats()

    def print_stats(self):
        """Print current statistics."""
        logger.info(f"\n{'='*60}")
        logger.info("Bot Statistics")
        logger.info(f"{'='*60}")
        logger.info(f"Total scans: {self.stats['scans']}")
        logger.info(f"Opportunities found: {self.stats['opportunities_found']}")
        logger.info(f"Opportunities executed: {self.stats['opportunities_executed']}")
        logger.info(f"Successful: {self.stats['successful_executions']}")
        logger.info(f"Failed: {self.stats['failed_executions']}")
        logger.info(f"Total profit: {self.stats['total_profit'] / 10**6:.2f} tokens")
        if self.stats['successful_executions'] > 0:
            avg_profit = self.stats['total_profit'] / self.stats['successful_executions'] / 10**6
            logger.info(f"Average profit per trade: {avg_profit:.2f} tokens")
        logger.info(f"{'='*60}\n")

    def run(self):
        """Start the bot."""
        self.running = True

        logger.info("\n" + "="*60)
        logger.info("🚀 Flash Loan Arbitrage Bot Starting")
        logger.info("="*60)

        if self.direct_execution:
            # Run detector only (executes immediately)
            logger.info("Mode: Direct Execution")
            self.run_detector_loop()

        else:
            # Run both detector and orchestrator in parallel
            logger.info("Mode: Database Queue")

            detector_thread = threading.Thread(target=self.run_detector_loop)
            orchestrator_thread = threading.Thread(target=self.run_orchestrator_loop)

            detector_thread.start()
            orchestrator_thread.start()

            try:
                detector_thread.join()
                orchestrator_thread.join()
            except KeyboardInterrupt:
                logger.info("\n⛔ Bot stopped by user")
                self.running = False

    def stop(self):
        """Stop the bot."""
        self.running = False
        self.print_stats()
        logger.info("Bot stopped")


def main():
    """Main entry point."""
    logger.info("="*60)
    logger.info("Flash Loan Arbitrage Bot")
    logger.info("="*60)

    # Load configuration
    rpc_url = os.getenv("POLYGON_RPC_URL", "http://localhost:8545")
    contract_address = os.getenv("FLASH_LOAN_ARBITRAGE_ADDRESS")
    private_key = os.getenv("PRIVATE_KEY")
    v3_adapter = os.getenv("UNISWAP_V3_ADAPTER_ADDRESS")
    v2_adapter = os.getenv("UNISWAP_V2_ADAPTER_ADDRESS")
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    direct_execution = os.getenv("DIRECT_EXECUTION", "true").lower() == "true"

    # Validate configuration
    if not all([contract_address, private_key, v3_adapter, v2_adapter]):
        logger.error("❌ Missing required environment variables")
        logger.error("Required: FLASH_LOAN_ARBITRAGE_ADDRESS, PRIVATE_KEY, UNISWAP_V3_ADAPTER_ADDRESS, UNISWAP_V2_ADAPTER_ADDRESS")
        sys.exit(1)

    # Check database connection
    logger.info("Checking database connection...")
    if not check_db_connection():
        logger.error("❌ Database connection failed")
        sys.exit(1)
    logger.info("✅ Database connected")

    # Initialize Web3
    logger.info(f"Connecting to {rpc_url}...")
    web3 = Web3(Web3.HTTPProvider(rpc_url))

    if not web3.is_connected():
        logger.error("❌ Failed to connect to blockchain")
        sys.exit(1)

    logger.info(f"✅ Connected to blockchain (Chain ID: {web3.eth.chain_id})")

    # Initialize detector
    logger.info("Initializing Opportunity Detector...")
    detector = OpportunityDetector(
        web3=web3,
        min_profit_usd=float(os.getenv("MIN_PROFIT_USD", "1.0")),
        max_gas_price_gwei=int(os.getenv("MAX_GAS_PRICE_GWEI", "100")),
        check_interval=int(os.getenv("CHECK_INTERVAL", "5")),
        min_flash_loan=int(os.getenv("MIN_FLASH_LOAN_USD", "500")) * 10**6,  # Convert USD to USDC units
        max_flash_loan=int(os.getenv("MAX_FLASH_LOAN_USD", "100000")) * 10**6
    )
    logger.info("✅ Detector initialized")

    # Initialize orchestrator
    logger.info("Initializing Flash Loan Orchestrator...")
    orchestrator = FlashLoanOrchestrator(
        web3=web3,
        contract_address=contract_address,
        private_key=private_key,
        v3_adapter_address=v3_adapter,
        v2_adapter_address=v2_adapter,
        dry_run=dry_run
    )
    logger.info("✅ Orchestrator initialized")

    # Initialize bot
    bot = ArbitrageBot(
        web3=web3,
        detector=detector,
        orchestrator=orchestrator,
        direct_execution=direct_execution
    )

    # Run bot
    try:
        bot.run()
    except KeyboardInterrupt:
        logger.info("\n⛔ Shutting down...")
        bot.stop()
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        bot.stop()
        sys.exit(1)


if __name__ == "__main__":
    main()
