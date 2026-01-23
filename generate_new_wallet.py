#!/usr/bin/env python3
"""Generate a new secure wallet for Arbitrum deployment"""
from eth_account import Account
import secrets

print("=" * 80)
print("GENERATING NEW SECURE WALLET")
print("=" * 80)

# Generate cryptographically secure random private key
private_key_bytes = secrets.token_bytes(32)
private_key = "0x" + private_key_bytes.hex()

# Create account from private key
account = Account.from_key(private_key)

print("\n✅ New wallet generated successfully!\n")
print("=" * 80)
print("WALLET DETAILS - SAVE THESE SECURELY!")
print("=" * 80)

print(f"\n📍 Address: {account.address}")
print(f"🔑 Private Key: {private_key}")

print("\n" + "=" * 80)
print("⚠️  IMPORTANT SECURITY INSTRUCTIONS")
print("=" * 80)

print("\n1. 📝 SAVE THESE DETAILS:")
print("   - Write them down on PAPER (not digital)")
print("   - Store paper in secure location")
print("   - Make a backup copy in different location")

print("\n2. 🔒 NEVER SHARE:")
print("   - Never share private key with ANYONE")
print("   - Never enter it on websites")
print("   - Never send via email/chat")
print("   - Never store in cloud storage")

print("\n3. ✅ SAFE TO SHARE:")
print(f"   - Address: {account.address}")
print("   - This is your public address for receiving funds")

print("\n4. 💰 NEXT STEPS:")
print(f"   - Send 0.01 ETH to: {account.address}")
print("   - Network: Arbitrum One")
print("   - I will update all configuration files automatically")

print("\n" + "=" * 80)
print("READY TO UPDATE CONFIGURATION")
print("=" * 80)

print("\nPress Enter when you're ready for me to update .env.arbitrum with this new wallet...")
input()

# Update .env.arbitrum
print("\n📝 Updating .env.arbitrum...")

with open('.env.arbitrum', 'r') as f:
    config = f.read()

# Replace private key
config = config.replace(
    'PRIVATE_KEY=0x0bfca4742670ad3c4574aa959c8a114f2a2fcc52f8a8c3874553dd1ab3c9d5b2',
    f'PRIVATE_KEY={private_key}'
)

with open('.env.arbitrum', 'w') as f:
    f.write(config)

print(f"✅ Updated .env.arbitrum")
print(f"   New address: {account.address}")
print(f"   New private key: {private_key[:20]}...{private_key[-10:]}")

# Save to a secure file for reference
with open('new_wallet_BACKUP.txt', 'w') as f:
    f.write(f"NEW WALLET FOR ARBITRUM DEPLOYMENT\n")
    f.write(f"=" * 80 + "\n\n")
    f.write(f"Address: {account.address}\n")
    f.write(f"Private Key: {private_key}\n\n")
    f.write(f"⚠️  DELETE THIS FILE AFTER SAVING DETAILS SECURELY!\n")
    f.write(f"⚠️  NEVER COMMIT THIS FILE TO GIT!\n")

print(f"\n💾 Backup saved to: new_wallet_BACKUP.txt")
print(f"   ⚠️  DELETE this file after saving details securely!")
print(f"   ⚠️  This file contains your private key!")

print("\n" + "=" * 80)
print("✅ CONFIGURATION UPDATED - READY TO DEPLOY")
print("=" * 80)

print(f"\nNext steps:")
print(f"1. Send 0.01 ETH to {account.address} on Arbitrum network")
print(f"2. Verify balance: ./venv/bin/python check_arbitrum_balance.py")
print(f"3. Deploy contracts: ./venv/bin/python deploy_arbitrum.py")
