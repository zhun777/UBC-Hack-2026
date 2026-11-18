# Backend

Python (FastAPI) server between the frontend and the contracts. The frontend calls only this;
this is the only part that holds keys and talks to the chain and Circle.

## Run it

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env          # then fill in your own values
.venv/bin/uvicorn main:app --reload
```

The API is at http://localhost:8000, and interactive docs are at http://localhost:8000/docs.

```bash
.venv/bin/pytest                          # unit + API tests (fake chain, no network)
.venv/bin/python scripts/smoke_test.py    # whole demo against the running server
```

## Modes (in `.env`)

| Setting | Values |
|---|---|
| `CHAIN_MODE` | `fake`: no blockchain, points kept in SQLite; works before the contracts exist. `arc`: real contracts on Arc testnet, reads `contracts/deployments.json` and `contracts/abi/`. |
| `WALLET_MODE` | `test`: backend keeps a key per user in SQLite. `circle`: Circle developer-controlled wallets (not wired up yet). |

The frontend sees the same API in every mode.

## Switching to the real contracts

1. Pull once `contracts/deployments.json` and `contracts/abi/` are committed.
2. Make the network wallet: `.venv/bin/python scripts/new_network_wallet.py`. It prints the
   address. Fund it from the Circle faucet, and make sure it's the RewardsVault owner.
3. Set `CHAIN_MODE=arc` in `.env`, restart, and check http://localhost:8000/health.
4. Run the smoke test. It uses $1.50 of the network wallet's test USDC.

## Files

| File | Does |
|---|---|
| `main.py` | The 7 endpoints from the Integration spec, plus `GET /health` |
| `chain.py` | Contract calls (`ArcChain`) and the stand-in (`FakeChain`) |
| `wallets.py` | `get_or_create_wallet` and `send_tx`, for test or Circle wallets |
| `rpc.py` | Connection to Arc; signs and sends transactions |
| `watcher.py` | Reads `Spent` events, marks orders paid, writes payouts |
| `units.py` | Every API-to-chain conversion: cents, USDC units, keccak IDs |
| `db.py` | SQLite tables: users, wallets, orders, payouts, history |
| `config.py` | Reads `.env`, `brands.json`, `deployments.json` and ABIs |

`app.db` (SQLite) holds test private keys, and `.env` holds secrets. Both are git-ignored: never commit them.

## Additions to the Integration spec

- `GET /orders/{code}`, `GET /payouts` and `GET /me` history also return `brand_name`
  (orders also return `branch_name` and `explorer_url`). `GET /me` also returns `wallet_address`.
- `explorer_url` is `null` in fake mode, so hide the "Verify onchain" link when it's null.
- Two more error codes: `INVALID_REQUEST` (bad input) and `SERVER_ERROR` (a bug on our side).
- `branch` is optional in `POST /payment-request`; it defaults to the brand's first branch.
- Order codes skip 0, O, 1 and I so they're easy to type.
