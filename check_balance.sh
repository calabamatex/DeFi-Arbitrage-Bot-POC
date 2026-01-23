#!/bin/bash
# Quick check of deployer wallet balance

./venv/bin/python -c "
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from eth_account import Account
from dotenv import load_dotenv
import os

load_dotenv()

web3 = Web3(Web3.HTTPProvider(os.getenv('ALCHEMY_POLYGON_RPC_URL')))
web3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

account = Account.from_key(os.getenv('PRIVATE_KEY'))
balance = web3.eth.get_balance(account.address)
gas_price = web3.eth.gas_price

print('='*80)
print('Polygon Mainnet Deployer Wallet')
print('='*80)
print(f'Address: {account.address}')
print(f'Balance: {web3.from_wei(balance, \"ether\")} MATIC')
print(f'USD Value: ~\${float(web3.from_wei(balance, \"ether\")) * 0.65:.2f} (at \$0.65/MATIC)')
print(f'')
print(f'Current Gas Price: {web3.from_wei(gas_price, \"gwei\")} gwei')
print(f'Estimated Deploy Cost: ~\${(3.7e6 * int(gas_price) / 1e18) * 0.65:.2f}')
print(f'')

if balance >= web3.to_wei(0.5, 'ether'):
    print('✅ READY TO DEPLOY - Sufficient balance')
    print('')
    print('Run: ./deploy_mainnet.sh')
else:
    needed = web3.from_wei(web3.to_wei(0.5, 'ether') - balance, 'ether')
    print(f'❌ Need {needed:.4f} more MATIC')
    print(f'   Send to: {account.address}')
    print(f'   Network: Polygon (NOT Ethereum!)')
print('='*80)
"
