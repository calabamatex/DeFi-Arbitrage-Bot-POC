"""Security tests - verify no secrets are committed to the codebase."""

import os
import re
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

# Build sensitive strings at runtime so this test file itself does not
# contain the raw secrets and therefore does not trigger self-detection.
_COMPROMISED_KEY_SUFFIXES = [
    'e888271c7f9424c0fc7e62bcd0f50a72ae9363d112a55ff9',
    'c1469f6a408936209fd167c513a59ca6bf1e2601b0dfae4',
    '4574aa959c8a114f2a2fcc52f8a8c3874553dd1ab3c9d5b2',
]
_COMPROMISED_KEY_PREFIXES = [
    '0xcf4cbdb74541d0df',
    '0xd19cc102fc4f1dc45',
    '0x0bfca4742670ad3c',
]
COMPROMISED_KEYS = [p + s for p, s in zip(_COMPROMISED_KEY_PREFIXES, _COMPROMISED_KEY_SUFFIXES)]

# Alchemy key split so this file doesn't self-match
_ALCHEMY_PART_A = 'UwY7HrYza9vl'
_ALCHEMY_PART_B = 'bNxkAIpme'
ALCHEMY_KEY_FRAGMENT = _ALCHEMY_PART_A + _ALCHEMY_PART_B

# Files that are allowed to contain test/well-known keys
ALLOWLISTED_FILES = {
    'manual_execution_test.py',           # Anvil default test key (well-known, not secret)
    'deploy_contracts_web3.py',           # Anvil default test key (well-known, not secret)
    'execute_profitable_arbitrage.py',    # Anvil default test key (well-known, not secret)
}


def get_all_files(exclude_dirs=None):
    """Get all text files in the project, excluding specified directories."""
    exclude_dirs = exclude_dirs or {'.git', 'node_modules', '__pycache__', '.eggs', 'venv', 'env', '.venv'}
    files = []
    for root, dirs, filenames in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for f in filenames:
            if f.endswith(('.py', '.sh', '.md', '.env', '.txt', '.json', '.yaml', '.yml', '.toml')):
                files.append(os.path.join(root, f))
    return files


class TestNoPrivateKeysCommitted:
    """Verify private keys are not in any tracked files."""

    def test_no_compromised_keys_in_codebase(self):
        """Verify none of the known compromised keys appear in any file."""
        for filepath in get_all_files():
            try:
                with open(filepath, 'r', errors='ignore') as f:
                    content = f.read()
                for key in COMPROMISED_KEYS:
                    assert key not in content, (
                        f"Compromised private key found in {filepath}"
                    )
            except (UnicodeDecodeError, PermissionError):
                pass

    def test_no_real_private_keys_in_python_files(self):
        """Verify no real private keys are hardcoded in Python files."""
        private_key_pattern = re.compile(r'PRIVATE_KEY\s*=\s*["\']0x[0-9a-fA-F]{64}["\']')
        for filepath in get_all_files():
            if not filepath.endswith('.py'):
                continue
            basename = os.path.basename(filepath)
            if basename in ALLOWLISTED_FILES:
                continue
            try:
                with open(filepath, 'r') as f:
                    content = f.read()
                matches = private_key_pattern.findall(content)
                assert len(matches) == 0, (
                    f"Hardcoded private key found in {filepath}: {matches}"
                )
            except (UnicodeDecodeError, PermissionError):
                pass

    def test_no_alchemy_key_in_codebase(self):
        """Verify the compromised Alchemy API key is not present."""
        for filepath in get_all_files():
            try:
                with open(filepath, 'r', errors='ignore') as f:
                    content = f.read()
                assert ALCHEMY_KEY_FRAGMENT not in content, (
                    f"Compromised Alchemy API key found in {filepath}"
                )
            except (UnicodeDecodeError, PermissionError):
                pass


class TestGitignoreCoversSecrets:
    """Verify .gitignore properly excludes secret files."""

    def test_gitignore_excludes_env_variants(self):
        """Verify .gitignore excludes .env.* files."""
        gitignore_path = PROJECT_ROOT / '.gitignore'
        assert gitignore_path.exists(), ".gitignore must exist"

        content = gitignore_path.read_text()
        assert '.env' in content, ".gitignore must exclude .env"
        assert '.env.*' in content, ".gitignore must exclude .env.* patterns"

    def test_gitignore_excludes_wallet_backups(self):
        """Verify .gitignore excludes wallet backup files."""
        content = (PROJECT_ROOT / '.gitignore').read_text()
        assert 'new_wallet_BACKUP.txt' in content or '*BACKUP*' in content


class TestNoHardcodedAdminCodes:
    """Verify no hardcoded admin/reset codes remain."""

    def test_no_hardcoded_reset_code(self):
        """Verify admin codes are loaded from environment, not hardcoded."""
        risk_mgr_path = PROJECT_ROOT / 'src' / 'utils' / 'risk_manager.py'
        content = risk_mgr_path.read_text()
        assert '"RESET_SHUTDOWN"' not in content, (
            "Hardcoded admin code 'RESET_SHUTDOWN' still in risk_manager.py"
        )

    def test_no_hardcoded_emergency_code(self):
        """Verify emergency shutdown code is loaded from environment."""
        shutdown_path = PROJECT_ROOT / 'src' / 'utils' / 'emergency_shutdown.py'
        content = shutdown_path.read_text()
        assert '"EMERGENCY_SHUTDOWN_2024"' not in content, (
            "Hardcoded admin code 'EMERGENCY_SHUTDOWN_2024' still in emergency_shutdown.py"
        )


class TestGenerateWalletDoesNotWriteKeys:
    """Verify generate_new_wallet.py does not write keys to disk."""

    def test_no_file_write_in_wallet_generator(self):
        """Verify the wallet generator doesn't write private keys to files."""
        wallet_path = PROJECT_ROOT / 'generate_new_wallet.py'
        if not wallet_path.exists():
            pytest.skip("generate_new_wallet.py not found")

        content = wallet_path.read_text()
        assert 'open(' not in content, (
            "generate_new_wallet.py should not write files"
        )
        assert 'new_wallet_BACKUP' not in content, (
            "generate_new_wallet.py should not reference wallet backup files"
        )
