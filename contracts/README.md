# Contracts

Two Solidity contracts on Arc testnet that hold the money behind every reward point.

- **PointsToken** (`src/PointsToken.sol`): the points. Whole numbers only (0 decimals). Only the vault can mint or burn them, and customers cannot send them to each other.
- **RewardsVault** (`src/RewardsVault.sol`): holds the USDC. Each brand operator pre-funds a reward budget; the network issues points from that budget; a customer spends points at any brand operator, and the USDC behind them goes straight to that operator.

1 point is always backed by $0.01 of USDC (`POINT_VALUE = 10_000` USDC units). At every moment:

```
USDC in the vault = sum of brand budgets + points outstanding x $0.01
```

Anyone can check this onchain with `isFullyBacked()`.

## Functions

| Function | Who calls it | What it does |
| --- | --- | --- |
| `addBrand(brandId, settlement, currency)` | Owner | Registers a brand operator and where it gets paid |
| `setBrandActive(brandId, active)` | Owner | Pauses or resumes an operator |
| `setBrandSettlement(brandId, settlement)` | Owner | Changes where an operator gets paid |
| `fundBrand(brandId, usdcAmount)` | Anyone, after approving the vault | Adds USDC to that operator's reward budget |
| `issueReward(brandId, user, points)` | Owner (the backend's network wallet) | Takes `points x $0.01` from the brand's budget and mints the points |
| `spendAtBrand(brandId, branchId, orderId, points)` | The customer's own wallet | Burns the points, pays `points x $0.01` USDC to that brand's settlement address. Each order ID can be paid once |
| `getBrand(brandId)` | View | Settlement address, currency, active, exists, budget |
| `orderPaid(orderId)` | View | Whether an order has been paid |
| `totalLiabilities()` / `isFullyBacked()` | View | The backing check |
| `brandIds(i)` / `brandCount()` | View | List of registered brands |

Events: `BrandAdded`, `BrandActiveSet`, `BrandSettlementSet`, `BrandFunded(brandId, funder, usdcAmount)`, `RewardIssued(brandId, user, points, usdcAmount)`, `Spent(user, brandId, branchId, orderId, points, usdcAmount)`.

Errors are custom errors with plain names (`InsufficientPoints`, `InsufficientBudget`, `OrderAlreadyPaid`, `UnknownBrand`, `BrandInactive`, …), so the backend can map each one to a message.

## Notes for the backend

- **IDs:** `brandId` and `branchId` are `keccak256` of the slug, for example `keccak256("cafe-sg")`. `orderId` is `keccak256` of the 6-character order code. The deploy script writes each brand's ID into `deployments.json`.
- **Units:** points are whole numbers. USDC amounts are 6-decimal units (`1000000` = $1.00).
- **Earning:** the backend works out the points (USD amount x the brand's earn rate, rounded down) and calls `issueReward` from the network wallet.
- **Spending:** the backend works out the points (USD price x 100, rounded up) and sends `spendAtBrand` from the customer's wallet, so the customer's address is `msg.sender`. That wallet needs a little USDC for gas, or Circle Gas Station.
- **Changes from the original spec:** there is no `redeem`, `setThreshold` or `creditOf`; `issueReward` takes `(brandId, user, points)` instead of `(user, dollars)`; and `spendAtBrand` takes points instead of a USDC amount.
- **Files:** `deployments.json` holds the addresses, chain ID and deploy block (start the event watcher there). `abi/` holds the ABIs, named `APPToken.json` and `RewardsVault.json` to match what `backend/chain.py` loads. In `deployments.json` the token address is under `appToken`.

## Run the tests

Needs [Foundry](https://book.getfoundry.sh/getting-started/installation).

```bash
forge test
```

35 tests: 9 for the token, 25 for the vault (including the full demo run with the plan's exact numbers), and one fuzzed invariant test that makes about 12,800 random fund, issue and spend calls and checks the backing after each one.

## Deploy to Arc testnet

1. `cp .env.example .env` and fill in `DEPLOYER_PRIVATE_KEY`, `US_SETTLEMENT` and `SG_SETTLEMENT`.
2. Get test USDC for the deployer from [faucet.circle.com](https://faucet.circle.com). On Arc, USDC is also the gas token.
3. Dry run, then deploy:

```bash
source .env
forge script script/Deploy.s.sol:Deploy --rpc-url $ARC_RPC_URL
forge script script/Deploy.s.sol:Deploy --rpc-url $ARC_RPC_URL --broadcast
bash export-abi.sh
```

4. Commit `deployments.json` and `abi/`, then post the two addresses in the group chat.

The deployer becomes the owner, so use the same key as the backend's `NETWORK_PRIVATE_KEY`. Set `FUND_US_USDC` and `FUND_SG_USDC` to fund the budgets during deployment, or leave them at 0 and fund them later with `fundBrand`.

## How we use Arc

- **USDC-native settlement:** every point is backed by USDC in the vault, and each purchase made with points pays the brand operator in USDC within one block. Operators in different countries settle without bank transfers.
- **Fees in USDC:** gas on Arc is paid in USDC, so the network's costs are in dollars and never depend on a volatile token's price.
- **Verifiable backing:** anyone can call `isFullyBacked()` or compare the vault's USDC balance with `totalLiabilities()` on the explorer.

Deployed addresses (Arc testnet, chain ID 5042002): _fill in after deployment_.

- PointsToken: `0x…`
- RewardsVault: `0x…`
