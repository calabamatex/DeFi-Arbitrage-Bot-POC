"""
Main Bot Orchestrator - Coordinates all components and runs trading loop.
"""

import asyncio
import signal
import sys
import logging
from decimal import Decimal
from typing import List, Optional, Dict
from datetime import datetime, timedelta

from web3 import Web3

from src.bot.config import load_config, get_erc20_abi
from src.dex.quickswap import QuickSwap
from src.dex.sushiswap import SushiSwap
from src.dex.uniswap_v3 import UniswapV3
from src.bot.arbitrage import (
    execute_arbitrage,
    calculate_arbitrage,
    ArbitrageOpportunity,
    is_profitable,
    log_arbitrage_attempt,
)
from src.config import Config as _PrimaryConfig
from src.utils.transaction_manager import TransactionManager
from src.utils.risk_manager import RiskManager
from src.utils.slippage_protection import SlippageProtection
from src.utils.emergency_shutdown import EmergencyShutdown
from src.bot.opportunity_scorer import OpportunityScorer
from src.bot.telegram_bot import TelegramBot
from src.utils.metrics_collector import MetricsCollector
from src.utils.performance_monitor import PerformanceMonitor

logger = logging.getLogger(__name__)


class ArbitrageBot:
    """Main arbitrage bot coordinator."""

    def __init__(self):
        """Initialize bot (loads config, sets up components)."""
        self.running = False
        self.web3: Optional[Web3] = None
        self.dex_instances: Dict = {}
        self.risk_manager: Optional[RiskManager] = None
        self.transaction_manager: Optional[TransactionManager] = None
        self.slippage_protection: Optional[SlippageProtection] = None
        self.opportunity_scorer: Optional[OpportunityScorer] = None
        self.emergency_shutdown: Optional[EmergencyShutdown] = None
        self.telegram_bot: Optional[TelegramBot] = None
        self.metrics_collector: Optional[MetricsCollector] = None
        self.performance_monitor: Optional[PerformanceMonitor] = None

        # Configuration
        self.config = None
        self.account = None
        self.private_key = None

        # Trading parameters
        self.min_profit_threshold = Decimal("0.01")  # 1% minimum profit
        self.max_trade_amount = Decimal("1.0")  # Max 1 ETH per trade
        self.check_interval = 5  # Check every 5 seconds

        # Statistics
        self.start_time = datetime.now()
        self.opportunities_found = 0
        self.trades_executed = 0
        self.successful_trades = 0
        self.failed_trades = 0
        self.total_profit = Decimal("0")

        # Token pairs to monitor
        self.token_pairs = [
            ("WETH", "USDC"),
            ("WETH", "USDT"),
            ("WETH", "DAI"),
            ("USDC", "USDT"),
            ("USDC", "DAI"),
        ]

        logger.info("ArbitrageBot initialized")

    async def initialize(self):
        """
        Initialize all bot components.

        13-step initialization:
        1. Load configuration
        2. Load environment variables
        3. Initialize Web3
        4. Setup account
        5. Initialize DEX instances
        6. Initialize Telegram bot
        7. Initialize Transaction Manager
        8. Initialize Risk Manager
        9. Initialize Slippage Protection
        10. Initialize Opportunity Scorer
        11. Initialize Emergency Shutdown
        12. Initialize Metrics Collector
        13. Initialize Performance Monitor
        """
        logger.info("Starting bot initialization...")

        try:
            # 1. Load configuration
            logger.info("Step 1/11: Loading configuration...")
            full_config, env_name, env_config, token_list = load_config()
            self.config = env_config  # Store environment-specific config
            self.token_list = token_list

            # 2. Load environment variables
            logger.info("Step 2/11: Loading environment variables...")
            import os
            from dotenv import load_dotenv

            load_dotenv()
            self.private_key = os.getenv("PRIVATE_KEY")
            if not self.private_key:
                raise ValueError("PRIVATE_KEY not found in environment variables")

            # 3. Initialize Web3
            logger.info("Step 3/11: Initializing Web3...")
            rpc_url = os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com")
            self.web3 = Web3(Web3.HTTPProvider(rpc_url))

            if not self.web3.is_connected():
                raise ConnectionError("Failed to connect to Polygon network")

            logger.info(
                f"Connected to Polygon network (chain_id: {self.web3.eth.chain_id})"
            )

            # 4. Setup account
            logger.info("Step 4/11: Setting up account...")
            self.account = self.web3.eth.account.from_key(self.private_key)
            logger.info(f"Using account: {self.account.address}")

            # 5. Initialize DEX instances
            logger.info("Step 5/11: Initializing DEX adapters...")
            self.dex_instances = {
                "quickswap": QuickSwap(
                    router_address=self.config["QUICKSWAP_ROUTER"], name="QuickSwap"
                ),
                "sushiswap": SushiSwap(
                    router_address=self.config["SUSHISWAP_ROUTER"], name="SushiSwap"
                ),
            }

            v3_router = os.getenv("UNISWAP_V3_ROUTER")
            v3_factory = os.getenv("UNISWAP_V3_FACTORY")
            v3_quoter = os.getenv("UNISWAP_V3_QUOTER")

            if v3_router and v3_factory and v3_quoter:
                self.dex_instances["uniswap_v3"] = UniswapV3(
                    router_address=v3_router,
                    factory_address=v3_factory,
                    quoter_address=v3_quoter,
                    name="UniswapV3",
                )
            logger.info(f"Initialized {len(self.dex_instances)} DEX adapters")

            # 6. Initialize Telegram bot
            logger.info("Step 6/11: Initializing Telegram bot...")
            telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
            telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")

            if telegram_token and telegram_chat_id:
                self.telegram_bot = TelegramBot(telegram_token, telegram_chat_id)
                await self.telegram_bot.send_message("🤖 Arbitrage Bot initializing...")
                logger.info("Telegram bot initialized")
            else:
                logger.warning("Telegram credentials not found, notifications disabled")

            # 7. Initialize Transaction Manager
            logger.info("Step 7/11: Initializing Transaction Manager...")
            self.transaction_manager = TransactionManager(
                web3=self.web3,
                account=self.account.address,
                private_key=self.private_key,
            )
            logger.info("Transaction Manager initialized")

            # 8. Initialize Risk Manager
            logger.info("Step 8/11: Initializing Risk Manager...")
            erc20_abi = get_erc20_abi()
            risk_config = {
                "MAX_POSITION_SIZE_USD": 10000,
                "MAX_TOTAL_EXPOSURE_USD": 50000,
                "DAILY_LOSS_LIMIT_USD": 5000,
            }
            self.risk_manager = RiskManager(
                web3=self.web3,
                erc20_abi=erc20_abi,
                config=risk_config,
            )
            logger.info("Risk Manager initialized")

            # 9. Initialize Slippage Protection
            logger.info("Step 9/11: Initializing Slippage Protection...")
            self.slippage_protection = SlippageProtection(
                max_slippage_percent=Decimal("0.005"),  # 0.5%
                max_price_impact_percent=Decimal("0.01"),  # 1%
            )
            logger.info("Slippage Protection initialized")

            # 10. Initialize Opportunity Scorer
            logger.info("Step 10/11: Initializing Opportunity Scorer...")
            self.opportunity_scorer = OpportunityScorer()
            logger.info("Opportunity Scorer initialized")

            # 11. Initialize Emergency Shutdown
            logger.info("Step 11/13: Initializing Emergency Shutdown...")
            admin_code = os.getenv("EMERGENCY_SHUTDOWN_CODE", "EMERGENCY_2024")
            self.emergency_shutdown = EmergencyShutdown(
                telegram_bot=self.telegram_bot, admin_code=admin_code
            )
            logger.info("Emergency Shutdown system initialized")

            # 12. Initialize Metrics Collector
            logger.info("Step 12/13: Initializing Metrics Collector...")
            self.metrics_collector = MetricsCollector(bot_start_time=self.start_time)
            logger.info("Metrics Collector initialized")

            # 13. Initialize Performance Monitor
            logger.info("Step 13/13: Initializing Performance Monitor...")
            self.performance_monitor = PerformanceMonitor()
            logger.info("Performance Monitor initialized")

            logger.info("✅ Bot initialization complete!")

            if self.telegram_bot:
                await self.telegram_bot.send_message(
                    "✅ Arbitrage Bot initialized successfully!\n"
                    f"Account: {self.account.address[:10]}...\n"
                    f"DEXes: {', '.join(self.dex_instances.keys())}\n"
                    f"Min Profit: {self.min_profit_threshold:.2%}"
                )

        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}", exc_info=True)
            if self.telegram_bot:
                await self.telegram_bot.send_alert(
                    "Initialization Error",
                    f"Failed to initialize bot: {e}",
                    severity="CRITICAL",
                )
            raise

    async def monitor_and_execute(self):
        """
        Main trading loop - continuously monitors for opportunities.

        Checks token pairs every 5 seconds for arbitrage opportunities.
        Scores and prioritizes opportunities, then executes the best one.
        """
        logger.info("Starting main trading loop...")

        if self.telegram_bot:
            await self.telegram_bot.send_message(
                "🚀 Trading loop started - monitoring for opportunities..."
            )

        try:
            while self.running:
                try:
                    # Check if emergency shutdown is active
                    if (
                        self.emergency_shutdown
                        and self.emergency_shutdown.is_shutdown_active()
                    ):
                        logger.warning("Emergency shutdown active - pausing trading")
                        await asyncio.sleep(self.check_interval)
                        continue

                    # Monitor all token pairs
                    logger.debug(
                        f"Checking {len(self.token_pairs)} token pairs for opportunities..."
                    )

                    all_opportunities = []

                    for token_a, token_b in self.token_pairs:
                        try:
                            logger.debug(
                                f"Checking {token_a}/{token_b} for arbitrage opportunities..."
                            )

                            result = await calculate_arbitrage(
                                token_a,
                                token_b,
                                self.web3,
                                self.dex_instances,
                                self.token_list,
                            )

                            if result is not None:
                                token_a_address = self.token_list.get(
                                    token_a, {}
                                ).get("address", "")
                                opp_dict = {
                                    "token_a": result.token1,
                                    "token_b": result.token2,
                                    "buy_dex": result.buy_dex,
                                    "sell_dex": result.sell_dex,
                                    "profit_percent": Decimal(
                                        str(result.profit_percent)
                                    ),
                                    "expected_profit": result.expected_profit,
                                    "amount": result.amount,
                                    "buy_price": result.buy_price,
                                    "sell_price": result.sell_price,
                                    "token_a_address": token_a_address,
                                    "gas_estimate": 300000,
                                    "liquidity": Decimal("1.0"),
                                    "confidence": Decimal("0.8"),
                                }
                                all_opportunities.append(opp_dict)
                                logger.info(
                                    f"Found opportunity for {token_a}/{token_b}: "
                                    f"{result.buy_dex} -> {result.sell_dex}, "
                                    f"profit: {result.profit_percent:.2%}"
                                )

                        except Exception as e:
                            logger.error(f"Error checking {token_a}/{token_b}: {e}")

                    # Process opportunities if any found
                    if all_opportunities:
                        self.opportunities_found += len(all_opportunities)
                        logger.info(
                            f"Total opportunities found: {len(all_opportunities)}"
                        )
                        await self._process_opportunities(all_opportunities)
                    else:
                        logger.debug("No opportunities found in this cycle")

                    # Wait before next check
                    await asyncio.sleep(self.check_interval)

                except Exception as e:
                    logger.error(f"Error in trading loop: {e}", exc_info=True)
                    await asyncio.sleep(self.check_interval)

        except asyncio.CancelledError:
            logger.info("Trading loop cancelled")
        except Exception as e:
            logger.error(f"Fatal error in trading loop: {e}", exc_info=True)
            if self.telegram_bot:
                await self.telegram_bot.send_alert(
                    "Trading Loop Error", f"Fatal error: {e}", severity="CRITICAL"
                )

        logger.info("Trading loop stopped")

    async def _process_opportunities(self, opportunities: List[Dict]):
        """
        Score, prioritize, and execute the best opportunity.

        Args:
            opportunities: List of arbitrage opportunities
        """
        if not opportunities:
            return

        try:
            # Score all opportunities
            scored_opportunities = []
            for opp in opportunities:
                score = self.opportunity_scorer.score_opportunity(
                    profit_percent=opp.get("profit_percent", Decimal("0")),
                    liquidity=opp.get("liquidity", Decimal("0")),
                    gas_estimate=opp.get("gas_estimate", 200000),
                    confidence=opp.get("confidence", Decimal("0.5")),
                )
                scored_opportunities.append((score, opp))

            # Sort by score (highest first)
            scored_opportunities.sort(reverse=True, key=lambda x: x[0])

            # Log top opportunities
            logger.info(f"Top 3 opportunities:")
            for i, (score, opp) in enumerate(scored_opportunities[:3], 1):
                logger.info(
                    f"  {i}. Score: {score:.2f}, Profit: {opp.get('profit_percent', 0):.2%}, "
                    f"Route: {opp.get('buy_dex', 'unknown')} -> {opp.get('sell_dex', 'unknown')}"
                )

            # Execute the best opportunity
            best_score, best_opportunity = scored_opportunities[0]

            if best_score >= self.opportunity_scorer.min_acceptable_score:
                logger.info(f"Executing best opportunity (score: {best_score:.2f})...")
                await self._execute_opportunity(best_opportunity)
            else:
                logger.info(
                    f"Best opportunity score {best_score:.2f} below threshold, skipping"
                )

        except Exception as e:
            logger.error(f"Error processing opportunities: {e}", exc_info=True)

    async def _execute_opportunity(self, opportunity: Dict):
        """
        Execute an arbitrage opportunity.

        Args:
            opportunity: Arbitrage opportunity details
        """
        try:
            # Extract opportunity details
            buy_dex = opportunity.get("buy_dex")
            sell_dex = opportunity.get("sell_dex")
            token_a = opportunity.get("token_a")
            token_b = opportunity.get("token_b")
            amount = opportunity.get("amount", Decimal("0"))
            expected_profit = opportunity.get("expected_profit", Decimal("0"))
            profit_percent = opportunity.get("profit_percent", Decimal("0"))

            logger.info(
                f"Attempting to execute: {token_a}/{token_b} via {buy_dex} -> {sell_dex}, "
                f"profit: {expected_profit:.6f} ({profit_percent:.2%})"
            )

            # Check if profit meets minimum threshold
            if profit_percent < self.min_profit_threshold:
                logger.info(
                    f"Profit {profit_percent:.2%} below threshold {self.min_profit_threshold:.2%}, skipping"
                )
                return

            # Validate with risk manager
            if self.risk_manager:
                can_trade, reason = await self.risk_manager.validate_trade(
                    token_address=opportunity.get("token_a_address"),
                    amount=amount,
                    expected_price=opportunity.get("buy_price", Decimal("0")),
                    dex_name=buy_dex,
                )

                if not can_trade:
                    logger.warning(f"Risk manager blocked trade: {reason}")
                    if self.telegram_bot:
                        await self.telegram_bot.send_message(
                            f"⚠️ Trade blocked: {reason}"
                        )
                    return

            # Execute the arbitrage trade
            self.trades_executed += 1

            # Reconstruct ArbitrageOpportunity dataclass from the dict
            opp = ArbitrageOpportunity(
                token1=token_a,
                token2=token_b,
                buy_dex=buy_dex,
                sell_dex=sell_dex,
                expected_profit=expected_profit,
                amount=amount,
                buy_price=opportunity.get("buy_price", Decimal("0")),
                sell_price=opportunity.get("sell_price", Decimal("0")),
                timestamp=datetime.now(),
            )

            # Check profitability after gas costs
            profitable, net_profit = await is_profitable(
                opp, self.web3, self.min_profit_threshold
            )
            if not profitable:
                logger.info(
                    f"Opportunity not profitable after gas (net: {net_profit:.6f}), skipping"
                )
                self.trades_executed -= 1  # Don't count skipped trades
                return

            # Dry-run mode: simulate without executing on-chain
            if _PrimaryConfig.DRY_RUN:
                logger.info(
                    f"[DRY_RUN] Would execute {token_a}/{token_b} "
                    f"via {buy_dex} -> {sell_dex}, "
                    f"expected net profit: {net_profit:.6f}"
                )
                result = {
                    "success": True,
                    "tx_hash": "DRY_RUN_SIMULATED",
                    "error": "",
                    "profit": net_profit,
                }
                await log_arbitrage_attempt(opp, True, "dry-run simulation", net_profit)
            else:
                # Live execution
                success, message, actual_profit = await execute_arbitrage(
                    opp,
                    self.web3,
                    self.dex_instances,
                    self.token_list,
                    self.account.address,
                    self.private_key,
                )
                result = {
                    "success": success,
                    "tx_hash": message if success else "",
                    "error": message if not success else "",
                    "profit": actual_profit,
                }
                await log_arbitrage_attempt(opp, success, message, actual_profit)

            # Process result
            if result.get("success"):
                self.successful_trades += 1
                actual_profit = result.get("profit", Decimal("0"))
                self.total_profit += actual_profit

                logger.info(f"✅ Trade successful! Profit: {actual_profit:.6f}")

                if self.telegram_bot:
                    await self.telegram_bot.send_message(
                        f"✅ Trade Executed!\n"
                        f"Pair: {token_a}/{token_b}\n"
                        f"Route: {buy_dex} → {sell_dex}\n"
                        f"Profit: {actual_profit:.6f} ({profit_percent:.2%})\n"
                        f"TX: {result.get('tx_hash', 'N/A')}"
                    )

                # Record profit with risk manager
                if self.risk_manager:
                    await self.risk_manager.record_trade_result(
                        success=True, profit_loss=actual_profit
                    )

            else:
                self.failed_trades += 1
                error = result.get("error", "Unknown error")

                logger.error(f"❌ Trade failed: {error}")

                if self.telegram_bot:
                    await self.telegram_bot.send_message(
                        f"❌ Trade Failed\n"
                        f"Pair: {token_a}/{token_b}\n"
                        f"Error: {error}"
                    )

                # Record failure with risk manager
                if self.risk_manager:
                    await self.risk_manager.record_trade_result(
                        success=False, profit_loss=Decimal("0")
                    )

        except Exception as e:
            self.failed_trades += 1
            logger.error(f"Error executing opportunity: {e}", exc_info=True)

            if self.telegram_bot:
                await self.telegram_bot.send_alert(
                    "Execution Error", f"Failed to execute trade: {e}", severity="HIGH"
                )

    async def export_metrics_periodically(self):
        """Export metrics every hour."""
        while self.running:
            try:
                # Wait 1 hour
                await asyncio.sleep(3600)

                if not self.running:
                    break

                # Collect and export metrics
                if self.metrics_collector:
                    metrics = self.metrics_collector.collect_metrics(
                        self.risk_manager, self.performance_monitor
                    )

                    # Create data directory if it doesn't exist
                    import os

                    os.makedirs("data", exist_ok=True)

                    # Export to JSON
                    self.metrics_collector.export_metrics_json("data/metrics.json")

                    # Export to Prometheus
                    self.metrics_collector.export_prometheus("data/metrics.prom")

                    logger.info("Metrics exported")

                    # Send summary via Telegram
                    if self.telegram_bot:
                        await self.telegram_bot.send_message(
                            f"📊 *Hourly Metrics*\n\n"
                            f"Uptime: {metrics.uptime_seconds/3600:.1f}h\n"
                            f"Opportunities: {metrics.opportunities_found}\n"
                            f"Trades: {metrics.trades_executed}\n"
                            f"Success Rate: {metrics.success_rate*100:.1f}%\n"
                            f"Net Profit: ${metrics.net_profit_usd:.2f}"
                        )

            except Exception as e:
                logger.error(f"Error exporting metrics: {e}")

    def _log_statistics(self):
        """Log current bot statistics."""
        runtime = datetime.now() - self.start_time
        success_rate = (
            (self.successful_trades / self.trades_executed * 100)
            if self.trades_executed > 0
            else 0
        )

        logger.info(
            f"\n{'='*60}\n"
            f"Bot Statistics\n"
            f"{'='*60}\n"
            f"Runtime: {runtime}\n"
            f"Opportunities Found: {self.opportunities_found}\n"
            f"Trades Executed: {self.trades_executed}\n"
            f"Successful: {self.successful_trades}\n"
            f"Failed: {self.failed_trades}\n"
            f"Success Rate: {success_rate:.1f}%\n"
            f"Total Profit: {self.total_profit:.6f} ETH\n"
            f"{'='*60}"
        )

    async def shutdown(self):
        """Gracefully shutdown the bot."""
        logger.info("Shutting down bot...")
        self.running = False

        # Export final metrics
        if self.metrics_collector:
            try:
                import os

                os.makedirs("data", exist_ok=True)

                metrics = self.metrics_collector.collect_metrics(
                    self.risk_manager, self.performance_monitor
                )
                self.metrics_collector.export_metrics_json("data/metrics.json")
                self.metrics_collector.export_prometheus("data/metrics.prom")
                logger.info("Final metrics exported")
            except Exception as e:
                logger.error(f"Error exporting final metrics: {e}")

        # Log final statistics
        self._log_statistics()

        # Send shutdown notification
        if self.telegram_bot:
            runtime = datetime.now() - self.start_time
            await self.telegram_bot.send_message(
                f"🛑 Bot Shutting Down\n"
                f"Runtime: {runtime}\n"
                f"Trades: {self.trades_executed}\n"
                f"Success Rate: {(self.successful_trades/self.trades_executed*100 if self.trades_executed > 0 else 0):.1f}%\n"
                f"Total Profit: {self.total_profit:.6f} ETH"
            )

        logger.info("Bot shutdown complete")

    async def run(self):
        """Main entry point - initialize and run the bot."""

        # Setup signal handlers for graceful shutdown
        def signal_handler(sig, frame):
            logger.info(f"Received signal {sig}, initiating shutdown...")
            self.running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        try:
            # Initialize all components
            await self.initialize()

            # Start monitoring
            self.running = True

            # Run monitoring loop and metrics export concurrently
            await asyncio.gather(
                self.monitor_and_execute(), self.export_metrics_periodically()
            )

        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        except Exception as e:
            logger.error(f"Fatal error in bot: {e}", exc_info=True)
        finally:
            await self.shutdown()


async def main():
    """Main entry point."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("arbitrage_bot.log"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    logger.info("Starting Arbitrage Bot...")

    # Create and run bot
    bot = ArbitrageBot()
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
