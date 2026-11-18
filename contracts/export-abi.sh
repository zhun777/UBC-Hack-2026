#!/usr/bin/env bash
# Writes the ABIs the backend needs to contracts/abi/. Run after `forge build`.
# File names match what backend/chain.py loads: APPToken.json and RewardsVault.json.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p abi
forge inspect src/PointsToken.sol:PointsToken abi --json > abi/APPToken.json
forge inspect src/RewardsVault.sol:RewardsVault abi --json > abi/RewardsVault.json
rm -f abi/PointsToken.json
echo "wrote abi/APPToken.json and abi/RewardsVault.json"
