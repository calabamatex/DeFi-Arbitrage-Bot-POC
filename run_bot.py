#!/usr/bin/env python3
"""
Flash Loan Arbitrage Bot - Main Runner

Runs the Opportunity Detector and Flash Loan Orchestrator with full
risk management, metrics collection, and monitoring wired in.
"""

import os
import sys
import time
import signal
import logging
import threading
from decimal import Decimal
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv
from web3 import Web3

from src.opportunity_detector import OpportunityDetector
from src.flash_loan_orchestrator import FlashLoanOrchestrator
from src.db.database import check_db_connection
from src.config import Config
from src.utils.risk_manager import RiskManager, TradeResult
from src.utils.metrics_collector import MetricsCollector
from src.utils.gas_optimizer import GasOptimizer
from src.utils.key_manager import load_private_key
from src.utils.logging_config import configure_logging

# Load environment variables (RPC URLs, contract addresses — NOT private keys)
load_dotenv()

# Configure logging (single location -- do not call basicConfig elsewhere)
os.environ.setdefault("BOT_TYPE", "arbitrage")
configure_logging(log_file="bot.log")
logger = logging.getLogger(__name__)

# Minimal ERC20 ABI for balance checks
ERC20_ABI = [
    {
        "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"internalType": "uint8", "name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function"
    }
]


class ArbitrageBot:
    """
    Main arbitrage bot that coordinates detector, orchestrator,
    risk manager, and metrics collector.
    """

    def __init__(
        self,
        web3: Web3,
        detector: OpportunityDetector,
        orchestrator: FlashLoanOrchestrator,
        risk_manager: RiskManager,
        metrics: MetricsCollector,
        gas_optimizer: GasOptimizer,
        direct_execution: bool = True,
        heartbeat_interval: int = 60,
    ):
        self.web3 = web3
        self.detector = detector
        self.orchestrator = orchestrator
        self.risk_manager = risk_manager
        self.metrics = metrics
        self.gas_optimizer = gas_optimizer
        self.direct_execution = direct_execution
        self.heartbeat_interval = heartbeat_interval

        self.running = False
        self.last_heartbeat = time.time()
        self.stats = {
            'scans': 0,
            'opportunities_found': 0,
            'opportunities_executed': 0,
            'successful_executions': 0,
            'failed_executions': 0,
            'total_profit': 0,
            'risk_rejections': 0,
        }

        logger.info("ArbitrageBot initialized with risk management and metrics")
        logger.info(f"Direct execution mode: {direct_execution}")

    def _heartbeat(self):
        """Log periodic heartbeat showing the bot is alive."""
        now = time.time()
        if now - self.last_heartbeat >= self.heartbeat_interval:
            self.last_heartbeat = now
            uptime = now - self.metrics.start_time.timestamp()
            uptime_str = f"{uptime/3600:.1f}h"
            chain_id = self.web3.eth.chain_id
            risk_metrics = self.risk_manager.get_risk_metrics()
            logger.info(
                f"HEARTBEAT chain={chain_id} scans={self.stats['scans']} "
                f"uptime={uptime_str} "
                f"opps={self.stats['opportunities_found']} "
                f"executed={self.stats['opportunities_executed']} "
                f"success={self.stats['successful_executions']} "
                f"daily_pnl=${risk_metrics.daily_pnl:.2f} "
                f"circuit_breaker={'ACTIVE' if risk_metrics.circuit_breaker_active else 'ok'} "
                f"status=OK"
            )
            # Export metrics snapshot
            try:
                self.metrics.collect_metrics(risk_manager=self.risk_manager)
                self.metrics.export_metrics_json('metrics_latest.json')
            except Exception as e:
                logger.warning(f"Metrics export failed: {e}")

    def run_detector_loop(self):
        """Run the detector in a loop."""
        logger.info("Starting Detector Loop")

        try:
            while self.running:
                self.stats['scans'] += 1
                self._heartbeat()

                try:
                    scan_start = time.time()
                    opportunities = self.detector.scan_opportunities()
                    scan_ms = (time.time() - scan_start) * 1000
                    self.metrics.record_detection_time(scan_ms)

                    if opportunities:
                        self.stats['opportunities_found'] += len(opportunities)
                        for opp in opportunities:
                            self.metrics.record_opportunity()

                        logger.info(f"Found {len(opportunities)} opportunities!")

                        if self.direct_execution:
                            for opp in opportunities:
                                self.execute_opportunity(opp)

                except Exception as e:
                    logger.error(f"Detector loop error: {e}")
                    self.metrics.record_error(str(e))

                import random
                jitter = random.uniform(0, self.detector.check_interval * 0.5)
                time.sleep(self.detector.check_interval + jitter)

        except KeyboardInterrupt:
            logger.info("Detector loop stopped by user")

    def run_orchestrator_loop(self):
        """Run the orchestrator in monitor mode."""
        logger.info("Starting Orchestrator Loop")
        try:
            self.orchestrator.monitor_opportunities(check_interval=5)
        except KeyboardInterrupt:
            logger.info("Orchestrator loop stopped by user")

    def execute_opportunity(self, opportunity: dict):
        """Execute a single opportunity with risk checks."""
        # Risk manager gate
        approved, reason = self.risk_manager.validate_trade(
            opportunity,
            self.orchestrator.address,
            opportunity.get('token_in', ''),
        )

        if not approved:
            self.stats['risk_rejections'] += 1
            logger.warning(f"Risk manager rejected trade: {reason}")
            return

        self.stats['opportunities_executed'] += 1
        logger.info(f"Executing Opportunity #{self.stats['opportunities_executed']}")

        exec_start = time.time()
        opp_id = opportunity.get('opportunity_id')
        result = self.orchestrator.execute_opportunity(opportunity, opportunity_id=opp_id)
        exec_ms = (time.time() - exec_start) * 1000
        self.metrics.record_execution_time(exec_ms)

        # Record in risk manager and metrics
        token_decimals = opportunity.get('token_decimals', 6)
        profit_usd = Decimal(str(result.get('profit', 0))) / Decimal(10**token_decimals)

        # Calculate actual gas cost from execution result
        gas_used = result.get('gas_used', 0) or 0
        gas_price = result.get('gas_price', 0) or 0
        gas_cost_wei = gas_used * gas_price
        native_price_usd = Decimal(os.getenv('NATIVE_TOKEN_PRICE_USD', '0.80'))
        gas_cost_usd = (Decimal(str(gas_cost_wei)) / Decimal(10**18)) * native_price_usd

        self.metrics.record_trade(
            success=result['success'],
            profit_usd=profit_usd,
            gas_cost_usd=gas_cost_usd,
        )

        trade_result = TradeResult(
            success=result['success'],
            timestamp=datetime.now(),
            profit_loss=(profit_usd - gas_cost_usd) if result['success'] else -gas_cost_usd,
            token_pair=f"{opportunity.get('token_in', '?')[:8]}/{opportunity.get('token_out', '?')[:8]}",
            buy_dex=opportunity.get('dex_path', ['?'])[0],
            sell_dex=opportunity.get('dex_path', ['?', '?'])[-1],
            amount=Decimal(str(opportunity.get('amount_in', 0))) / Decimal(10**token_decimals),
            gas_cost=gas_cost_usd,
            message=result.get('error') or 'OK',
        )
        self.risk_manager.record_trade_result(trade_result)

        if result['success']:
            self.stats['successful_executions'] += 1
            self.stats['total_profit'] += result.get('profit', 0)
            logger.info(f"Execution #{self.stats['successful_executions']} successful!")
        else:
            self.stats['failed_executions'] += 1
            logger.error(f"Execution failed: {result.get('error')}")

    def run(self):
        """Start the bot."""
        self.running = True

        logger.info("=" * 60)
        logger.info("Flash Loan Arbitrage Bot Starting")
        logger.info("=" * 60)

        if self.direct_execution:
            logger.info("Mode: Direct Execution")
            self.run_detector_loop()
        else:
            logger.info("Mode: Database Queue")
            detector_thread = threading.Thread(target=self.run_detector_loop, daemon=True)
            orchestrator_thread = threading.Thread(target=self.run_orchestrator_loop, daemon=True)

            detector_thread.start()
            orchestrator_thread.start()

            try:
                while self.running:
                    self._heartbeat()
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Bot stopped by user")
                self.running = False

    def stop(self):
        """Stop the bot and export final metrics."""
        self.running = False
        try:
            self.metrics.collect_metrics(risk_manager=self.risk_manager)
            self.metrics.export_metrics_json('metrics_final.json')
        except Exception:
            pass
        logger.info(f"Bot stopped. Scans={self.stats['scans']} "
                     f"Executed={self.stats['opportunities_executed']} "
                     f"Success={self.stats['successful_executions']} "
                     f"RiskRejected={self.stats['risk_rejections']}")


def validate_startup_config():
    """Validate all required configuration before starting."""
    errors = []

    required_vars = [
        'FLASH_LOAN_ARBITRAGE_ADDRESS',
        'UNISWAP_V3_ADAPTER_ADDRESS',
        'UNISWAP_V2_ADAPTER_ADDRESS',
    ]
    for var in required_vars:
        if not os.getenv(var):
            errors.append(f"Missing required env var: {var}")

    # Private key: check that at least one key source is configured
    if not os.getenv('KEYSTORE_FILE') and not os.getenv('PRIVATE_KEY'):
        errors.append(
            "No private key configured. Set KEYSTORE_FILE (recommended) "
            "or PRIVATE_KEY env var. Run: python -m src.utils.key_manager create"
        )

    # Validate Config class
    try:
        Config.validate()
    except ValueError as e:
        errors.append(str(e))

    if errors:
        for err in errors:
            logger.error(f"Config error: {err}")
        logger.error("Fix the above configuration errors and restart.")
        sys.exit(1)


def main():
    """Main entry point. Supports --chain polygon|arbitrum|optimism|base."""
    import argparse

    parser = argparse.ArgumentParser(description='Flash Loan Arbitrage Bot')
    parser.add_argument('--chain', default='polygon',
                        choices=['polygon', 'arbitrum', 'optimism', 'base',
                                 'polygon_amoy', 'arbitrum_sepolia'],
                        help='Target chain (default: polygon)')
    args = parser.parse_args()

    # Map chain to RPC env var name
    rpc_env_map = {
        'polygon': 'POLYGON_RPC_URL',
        'arbitrum': 'ARBITRUM_RPC_URL',
        'optimism': 'OPTIMISM_RPC_URL',
        'base': 'BASE_RPC_URL',
        'polygon_amoy': 'POLYGON_AMOY_RPC_URL',
        'arbitrum_sepolia': 'ARBITRUM_SEPOLIA_RPC_URL',
    }

    logger.info("=" * 60)
    logger.info(f"Flash Loan Arbitrage Bot ({args.chain})")
    logger.info("=" * 60)

    # Validate configuration
    validate_startup_config()

    # Load config -- use chain-specific RPC URL
    rpc_env = rpc_env_map[args.chain]
    rpc_url = os.getenv(rpc_env, os.getenv("POLYGON_RPC_URL", "http://localhost:8545"))
    contract_address = os.getenv("FLASH_LOAN_ARBITRAGE_ADDRESS")
    private_key = load_private_key()
    v3_adapter = os.getenv("UNISWAP_V3_ADAPTER_ADDRESS")
    v2_adapter = os.getenv("UNISWAP_V2_ADAPTER_ADDRESS")
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    direct_execution = os.getenv("DIRECT_EXECUTION", "true").lower() == "true"

    # Check database
    logger.info("Checking database connection...")
    if not check_db_connection():
        logger.error("Database connection failed")
        sys.exit(1)
    logger.info("Database connected")

    # Initialize Web3 with HTTP timeout to prevent infinite hangs
    http_timeout = int(os.getenv("WEB3_HTTP_TIMEOUT", "30"))
    logger.info(f"Connecting to {rpc_url} (timeout={http_timeout}s)...")
    web3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': http_timeout}))
    if not web3.is_connected():
        logger.error("Failed to connect to blockchain")
        sys.exit(1)
    chain_id = web3.eth.chain_id
    logger.info(f"Connected to blockchain (Chain ID: {chain_id})")

    # Canary check: verify we can fetch a block
    try:
        latest = web3.eth.get_block('latest')
        logger.info(f"Latest block: {latest['number']}")
    except Exception as e:
        logger.error(f"RPC canary check failed: {e}")
        sys.exit(1)

    # Initialize components
    detector = OpportunityDetector(
        web3=web3,
        min_profit_usd=float(os.getenv("MIN_PROFIT_USD", "1.0")),
        max_gas_price_gwei=int(os.getenv("MAX_GAS_PRICE_GWEI", "100")),
        check_interval=int(os.getenv("CHECK_INTERVAL", "5")),
        min_flash_loan=int(os.getenv("MIN_FLASH_LOAN_USD", "500")) * 10**6,
        max_flash_loan=int(os.getenv("MAX_FLASH_LOAN_USD", "100000")) * 10**6,
    )

    orchestrator = FlashLoanOrchestrator(
        web3=web3,
        contract_address=contract_address,
        private_key=private_key,
        v3_adapter_address=v3_adapter,
        v2_adapter_address=v2_adapter,
        dry_run=dry_run,
    )

    risk_config = {
        'MAX_POSITION_SIZE_USD': float(os.getenv('MAX_POSITION_SIZE_USD', '10000')),
        'MAX_TOTAL_EXPOSURE_USD': float(os.getenv('MAX_TOTAL_EXPOSURE_USD', '50000')),
        'DAILY_LOSS_LIMIT_USD': float(os.getenv('DAILY_LOSS_LIMIT_USD', '1000')),
        'MAX_CONSECUTIVE_LOSSES': int(os.getenv('MAX_CONSECUTIVE_LOSSES', '5')),
        'CIRCUIT_BREAKER_COOLDOWN_MIN': int(os.getenv('CIRCUIT_BREAKER_COOLDOWN_MIN', '60')),
    }
    risk_manager = RiskManager(web3=web3, erc20_abi=ERC20_ABI, config=risk_config)

    metrics = MetricsCollector(bot_start_time=datetime.now())
    gas_optimizer = GasOptimizer(web3=web3)

    logger.info("All components initialized: detector, orchestrator, risk_manager, metrics, gas_optimizer")

    # Initialize bot
    bot = ArbitrageBot(
        web3=web3,
        detector=detector,
        orchestrator=orchestrator,
        risk_manager=risk_manager,
        metrics=metrics,
        gas_optimizer=gas_optimizer,
        direct_execution=direct_execution,
    )

    # Start health/metrics HTTP server
    from src.api.health import start_health_server
    start_health_server(bot)

    # Handle SIGTERM for graceful shutdown (Docker, systemd, etc.)
    def handle_sigterm(signum, frame):
        logger.info("Received SIGTERM, shutting down gracefully...")
        bot.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_sigterm)

    # Run
    try:
        bot.run()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        bot.stop()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        bot.stop()
        sys.exit(1)


if __name__ == "__main__":
    main()
