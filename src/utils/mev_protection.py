"""MEV Protection - Private tx submission via Flashbots and chain-native relays.

Routes signed transactions through private mempools to prevent sandwich attacks.
Ethereum mainnet (1): Flashbots Protect RPC. Polygon (137): standard RPC.
Arbitrum (42161): centralized sequencer, no public mempool.
Base (8453) / Optimism (10): sequencer-based, minimal MEV risk.
"""

import json
import os
import time
import logging
from typing import Dict, List, Optional

import aiohttp
from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3

from src.utils.errors import RPCError, TransactionError

logger = logging.getLogger(__name__)

# Configuration (env vars)
MEV_PROTECTION_ENABLED: bool = os.getenv("MEV_PROTECTION_ENABLED", "true").lower() == "true"
FLASHBOTS_RPC_URL: str = os.getenv("FLASHBOTS_RPC_URL", "https://rpc.flashbots.net")
FLASHBOTS_AUTH_KEY: Optional[str] = os.getenv("FLASHBOTS_AUTH_KEY")
PRIVATE_TX_MAX_WAIT: int = int(os.getenv("PRIVATE_TX_MAX_WAIT", "25"))

_FLASHBOTS_CHAIN_IDS = {1}  # Ethereum mainnet
_SEQUENCER_CHAIN_IDS = {42161, 10, 8453}  # Arbitrum, Optimism, Base


class FlashbotsProvider:
    """Route transactions through Flashbots Protect or chain-native private relays.

    Automatically selects the relay strategy based on ``chain_id``.
    Mirrors the async interface of TransactionManager so callers can
    swap in MEV-protected sending without restructuring their code.
    """

    def __init__(
        self,
        web3: Web3,
        private_key: str,
        flashbots_rpc_url: str = FLASHBOTS_RPC_URL,
        auth_key: Optional[str] = FLASHBOTS_AUTH_KEY,
        max_wait_blocks: int = PRIVATE_TX_MAX_WAIT,
    ) -> None:
        self.web3 = web3
        self._private_key = private_key
        self._flashbots_rpc_url = flashbots_rpc_url
        self._max_wait_blocks = max_wait_blocks
        self._chain_id: int = web3.eth.chain_id
        self._session: Optional[aiohttp.ClientSession] = None

        # Auth signer for Flashbots bundle payloads. Falls back to the bot's
        # own key when no dedicated auth key is configured.
        auth_source = auth_key if auth_key else private_key
        self._auth_account: Account = Account.from_key(auth_source)

        logger.info(
            "FlashbotsProvider init: chain_id=%d rpc=%s max_wait=%d",
            self._chain_id, self._flashbots_rpc_url, self._max_wait_blocks,
        )

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10),
            )
        return self._session

    async def close(self) -> None:
        """Close the underlying HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    # -- Public API --------------------------------------------------------

    async def send_private_transaction(self, signed_tx_raw: str) -> str:
        """Submit a signed transaction via a private relay.

        Args:
            signed_tx_raw: Hex-encoded signed transaction.

        Returns:
            Transaction hash (hex, 0x-prefixed).
        """
        raw = _ensure_hex_prefix(signed_tx_raw)

        if not MEV_PROTECTION_ENABLED:
            logger.debug("MEV protection disabled, using standard send")
            return self._fallback_send(raw)

        if self._chain_id in _FLASHBOTS_CHAIN_IDS:
            return await self._send_via_flashbots_protect(raw)

        # Sequencer L2s or Polygon: standard RPC is sufficient.
        if self._chain_id in _SEQUENCER_CHAIN_IDS:
            logger.debug("Chain %d sequencer-based, standard send is MEV-safe", self._chain_id)
        else:
            logger.debug("No private relay for chain %d, using standard send", self._chain_id)
        return self._fallback_send(raw)

    async def send_bundle(self, signed_txs: List[str], target_block: int) -> Dict:
        """Submit a Flashbots bundle targeting ``target_block``.

        Ethereum mainnet only. Other chains fall back to sequential private sends.
        Returns dict with ``bundleHash`` on success, or ``fallback``+``txHashes``.
        """
        txs = [_ensure_hex_prefix(tx) for tx in signed_txs]

        if self._chain_id not in _FLASHBOTS_CHAIN_IDS:
            logger.warning("Bundles unsupported on chain %d, sequential fallback", self._chain_id)
            hashes = [await self.send_private_transaction(tx) for tx in txs]
            return {"fallback": True, "txHashes": hashes}

        payload = {
            "jsonrpc": "2.0", "id": 1, "method": "eth_sendBundle",
            "params": [{
                "txs": txs,
                "blockNumber": hex(target_block),
                "minTimestamp": 0,
                "maxTimestamp": int(time.time()) + 120,
            }],
        }
        headers = self._flashbots_headers(payload)
        session = await self._get_session()

        try:
            async with session.post(
                self._flashbots_rpc_url, json=payload, headers=headers,
            ) as resp:
                resp.raise_for_status()
                result = await resp.json()

            if "error" in result:
                raise RPCError(f"Flashbots bundle rejected: {result['error']}")
            bundle_hash = result.get("result", {}).get("bundleHash", "")
            logger.info("Bundle submitted: hash=%s block=%d", bundle_hash, target_block)
            return {"bundleHash": bundle_hash, "targetBlock": target_block}

        except aiohttp.ClientError as exc:
            logger.error("Flashbots bundle relay failed: %s, falling back", exc)
            hashes = [self._fallback_send(tx) for tx in txs]
            return {"fallback": True, "txHashes": hashes}

    # -- Internal ----------------------------------------------------------

    async def _send_via_flashbots_protect(self, raw_tx: str) -> str:
        """Send a single tx through the Flashbots Protect RPC endpoint."""
        payload = {
            "jsonrpc": "2.0", "id": 1,
            "method": "eth_sendRawTransaction", "params": [raw_tx],
        }
        session = await self._get_session()

        try:
            async with session.post(self._flashbots_rpc_url, json=payload) as resp:
                resp.raise_for_status()
                result = await resp.json()

            if "error" in result:
                raise RPCError(f"Flashbots Protect rejected tx: {result['error']}")
            tx_hash = result.get("result", "")
            logger.info("Private tx via Flashbots Protect: %s", tx_hash)
            return tx_hash

        except aiohttp.ClientError as exc:
            logger.warning("Flashbots Protect failed: %s, falling back", exc)
            return self._fallback_send(raw_tx)

    def _fallback_send(self, raw_tx: str) -> str:
        """Send via the node's standard eth_sendRawTransaction."""
        try:
            tx_hash = self.web3.eth.send_raw_transaction(raw_tx)
            tx_hex = tx_hash.hex()
            logger.info("Tx sent via standard RPC: %s", tx_hex)
            return tx_hex
        except Exception as exc:
            logger.error("Standard RPC send failed: %s", exc)
            raise TransactionError(f"Failed to send transaction: {exc}") from exc

    def _flashbots_headers(self, payload: Dict) -> Dict[str, str]:
        """Build X-Flashbots-Signature header for bundle authentication."""
        body = json.dumps(payload, separators=(",", ":"))
        message = encode_defunct(text=Web3.keccak(text=body).hex())
        signed = Account.sign_message(message, self._auth_account.key)
        sig = f"{self._auth_account.address}:{signed.signature.hex()}"
        return {"Content-Type": "application/json", "X-Flashbots-Signature": sig}


def _ensure_hex_prefix(value: str) -> str:
    """Normalise a hex string to include a 0x prefix."""
    return value if value.startswith("0x") else f"0x{value}"
