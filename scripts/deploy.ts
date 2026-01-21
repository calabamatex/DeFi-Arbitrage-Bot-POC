import { ethers } from "hardhat";
import * as dotenv from "dotenv";

dotenv.config();

/**
 * Deploy FlashLoanArbitrage contract
 *
 * This script deploys the main arbitrage contract with appropriate
 * configuration for the target network.
 */
async function main() {
  const [deployer] = await ethers.getSigners();

  console.log("====================================");
  console.log("FlashLoanArbitrage Deployment Script");
  console.log("====================================\n");

  console.log("Deploying contracts with account:", deployer.address);
  console.log("Account balance:", ethers.formatEther(await ethers.provider.getBalance(deployer.address)), "ETH\n");

  // Get network
  const network = await ethers.provider.getNetwork();
  const chainId = Number(network.chainId);

  console.log("Network:", network.name);
  console.log("Chain ID:", chainId, "\n");

  // Network-specific configurations
  const config = getNetworkConfig(chainId);

  if (!config) {
    throw new Error(`Unsupported network: ${chainId}`);
  }

  console.log("Configuration:");
  console.log("- Aave Pool Address Provider:", config.aavePoolAddressProvider);
  console.log("- Min Profit USD:", ethers.formatEther(config.minProfitUSD), "USD");
  console.log("- Max Slippage:", config.maxSlippageBps / 100, "%\n");

  // Deploy FlashLoanArbitrage
  console.log("Deploying FlashLoanArbitrage...");

  const FlashLoanArbitrage = await ethers.getContractFactory("FlashLoanArbitrage");
  const arbitrage = await FlashLoanArbitrage.deploy(
    config.aavePoolAddressProvider,
    config.minProfitUSD,
    config.maxSlippageBps
  );

  await arbitrage.waitForDeployment();

  const arbitrageAddress = await arbitrage.getAddress();

  console.log("✅ FlashLoanArbitrage deployed to:", arbitrageAddress);
  console.log("   Gas used:", (await ethers.provider.getTransactionReceipt(arbitrage.deploymentTransaction()!.hash))?.gasUsed.toString(), "\n");

  // Whitelist DEX routers
  console.log("Whitelisting DEX routers...");

  for (const dex of config.dexRouters) {
    console.log(`- Whitelisting ${dex.name}:`, dex.address);
    const tx = await arbitrage.setDEXWhitelist(dex.address, true);
    await tx.wait();
    console.log("  ✅ Whitelisted");
  }

  console.log("\n====================================");
  console.log("Deployment Summary");
  console.log("====================================");
  console.log("FlashLoanArbitrage:", arbitrageAddress);
  console.log("Owner:", deployer.address);
  console.log("Network:", network.name);
  console.log("\n====================================");
  console.log("Next Steps");
  console.log("====================================");
  console.log("1. Verify contract on block explorer:");
  console.log(`   npx hardhat verify --network ${network.name} ${arbitrageAddress} "${config.aavePoolAddressProvider}" "${config.minProfitUSD}" "${config.maxSlippageBps}"`);
  console.log("\n2. Fund the contract (if needed for gas)");
  console.log("\n3. Configure backend with contract address");
  console.log("\n4. Test with small amounts first!");
  console.log("====================================\n");

  // Save deployment info
  const deploymentInfo = {
    network: network.name,
    chainId: chainId,
    deployer: deployer.address,
    timestamp: new Date().toISOString(),
    contracts: {
      FlashLoanArbitrage: arbitrageAddress,
    },
    config: {
      aavePoolAddressProvider: config.aavePoolAddressProvider,
      minProfitUSD: config.minProfitUSD.toString(),
      maxSlippageBps: config.maxSlippageBps,
      dexRouters: config.dexRouters,
    },
  };

  const fs = require("fs");
  const deploymentDir = "./deployments";

  if (!fs.existsSync(deploymentDir)) {
    fs.mkdirSync(deploymentDir);
  }

  fs.writeFileSync(
    `${deploymentDir}/${network.name}-${Date.now()}.json`,
    JSON.stringify(deploymentInfo, null, 2)
  );

  console.log(`Deployment info saved to ${deploymentDir}/\n`);
}

/**
 * Get network-specific configuration
 */
function getNetworkConfig(chainId: number) {
  const configs: Record<number, any> = {
    // Polygon Mainnet
    137: {
      aavePoolAddressProvider: "0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb",
      minProfitUSD: ethers.parseEther("10"), // $10
      maxSlippageBps: 200, // 2%
      dexRouters: [
        { name: "Uniswap V3", address: "0xE592427A0AEce92De3Edee1F18E0157C05861564" },
        { name: "SushiSwap", address: "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506" },
        { name: "QuickSwap", address: "0xa5E0829CaCEd8fFDD4De3c43696c57F7D7A678ff" },
      ],
    },

    // Mumbai Testnet
    80001: {
      aavePoolAddressProvider: "0x5343b5bA672Ae99d627A1C87866b8E53F47Db2E6",
      minProfitUSD: ethers.parseEther("1"), // $1 for testing
      maxSlippageBps: 500, // 5% for testing
      dexRouters: [
        { name: "Uniswap V3", address: "0xE592427A0AEce92De3Edee1F18E0157C05861564" },
      ],
    },

    // Arbitrum Mainnet
    42161: {
      aavePoolAddressProvider: "0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb",
      minProfitUSD: ethers.parseEther("10"),
      maxSlippageBps: 200,
      dexRouters: [
        { name: "Uniswap V3", address: "0xE592427A0AEce92De3Edee1F18E0157C05861564" },
        { name: "SushiSwap", address: "0x1b02dA8Cb0d097eB8D57A175b88c7D8b47997506" },
      ],
    },

    // Optimism Mainnet
    10: {
      aavePoolAddressProvider: "0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb",
      minProfitUSD: ethers.parseEther("10"),
      maxSlippageBps: 200,
      dexRouters: [
        { name: "Uniswap V3", address: "0xE592427A0AEce92De3Edee1F18E0157C05861564" },
      ],
    },

    // Base Mainnet
    8453: {
      aavePoolAddressProvider: "0xe20fCBdBfFC4Dd138cE8b2E6FBb6CB49777ad64D",
      minProfitUSD: ethers.parseEther("10"),
      maxSlippageBps: 200,
      dexRouters: [
        { name: "Uniswap V3", address: "0x2626664c2603336E57B271c5C0b26F421741e481" },
      ],
    },
  };

  return configs[chainId];
}

// Execute deployment
main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
