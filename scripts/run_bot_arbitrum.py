#!/usr/bin/env python3
"""
DEPRECATED: Use `python run_bot.py --chain arbitrum` instead.

This file is kept for backwards compatibility only.
"""
import sys
import os

print("NOTE: run_bot_arbitrum.py is deprecated.")
print("Use: python run_bot.py --chain arbitrum")
print()

# Inject --chain arbitrum and delegate to run_bot
sys.argv = [sys.argv[0], '--chain', 'arbitrum']
from run_bot import main
main()
