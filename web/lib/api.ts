// All calls to the backend live here. Screens import these functions and never
// call fetch directly. Formats follow the Integration spec in the build plan.
//
// While the backend isn't ready, each endpoint returns fake data. When an
// endpoint goes live, flip its flag in MOCK to false. Nothing else changes.

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const MOCK = {
  login: true,
  me: true,
  purchase: true,
  paymentRequest: true,
  getOrder: true,
  payOrder: true,
  payouts: true,
};

// ---------------------------------------------------------------- types

export type ErrorCode =
  | "USER_NOT_FOUND"
  | "BELOW_THRESHOLD"
  | "UNKNOWN_BRAND"
  | "ORDER_NOT_FOUND"
  | "ORDER_ALREADY_PAID"
  | "CHAIN_ERROR"
  | "NETWORK_ERROR"; // ours, not the backend's: the request never got an answer

export type LoginResponse = {
  user_id: string;
  email: string;
  wallet_address: string;
  is_new: boolean;
};

export type HistoryItem = {
  type: "earned" | "spent";
  points: number;
  brand: string;
  tx_hash: string;
  explorer_url: string;
  at: string;
};

export type Me = {
  user_id: string;
  email: string;
  points: number;
  points_value_cents: number;
  min_points_to_spend: number;
  history: HistoryItem[];
};

export type PurchaseRequest = {
  brand: string;
  amount_minor: number;
  currency: string;
};

export type PurchaseResponse = {
  points_earned: number;
  tx_hash: string;
  explorer_url: string;
};

export type PaymentRequest = {
  brand: string;
  branch: string;
  amount_minor: number;
  currency: string;
};

export type PaymentRequestResponse = {
  order_code: string;
  amount_usd_cents: number;
  status: "unpaid" | "paid";
  qr_payload: string;
};

export type Order = {
  order_code: string;
  brand: string;
  branch: string;
  amount_minor: number;
  currency: string;
  amount_usd_cents: number;
  status: "unpaid" | "paid";
  points_applied: number | null;
  card_remainder_minor: number | null;
  tx_hash: string | null;
};

export type PayResponse = {
  status: "paid";
  points_applied: number;
  card_remainder_minor: number;
  tx_hash: string;
  explorer_url: string;
};

export type Payout = {
  brand: string;
  branch: string;
  order_code: string;
  usdc_cents: number;
  local_minor: number;
  currency: string;
  status: "paid_mock";
  at: string;
};

export class ApiError extends Error {
  code: ErrorCode;

  constructor(code: ErrorCode, message: string) {
    super(message);
    this.code = code;
  }
}

/** Plain-English text for each error code, for showing on screen. */
export function errorMessage(err: unknown): string {
  if (!(err instanceof ApiError)) return "Something went wrong. Please try again.";
  switch (err.code) {
    case "USER_NOT_FOUND":
      return "We couldn't find your account. Please log in again.";
    case "BELOW_THRESHOLD":
      return "You need at least 100 points to pay with points.";
    case "UNKNOWN_BRAND":
      return "This store isn't part of the rewards network.";
    case "ORDER_NOT_FOUND":
      return "We couldn't find that order. Check the code and try again.";
    case "ORDER_ALREADY_PAID":
      return "This order has already been paid.";
    case "CHAIN_ERROR":
      return "The payment didn't go through. Please try again.";
    case "NETWORK_ERROR":
      return "Can't reach the server. Check your connection.";
  }
}

// ------------------------------------------------------------- session

const USER_ID_KEY = "user_id";

export function getUserId(): string | null {
  try {
    return localStorage.getItem(USER_ID_KEY);
  } catch {
    return null;
  }
}

export function logout() {
  try {
    localStorage.removeItem(USER_ID_KEY);
  } catch {}
}

function saveUserId(userId: string) {
  try {
    localStorage.setItem(USER_ID_KEY, userId);
  } catch {}
}

// ------------------------------------------------------------ endpoints

export async function login(email: string): Promise<LoginResponse> {
  const res = MOCK.login
    ? await mock.login(email)
    : await request<LoginResponse>("POST", "/auth/login", { email });
  saveUserId(res.user_id);
  return res;
}

export function getMe(): Promise<Me> {
  return MOCK.me ? mock.me() : request("GET", "/me");
}

export function purchase(body: PurchaseRequest): Promise<PurchaseResponse> {
  return MOCK.purchase
    ? mock.purchase(body)
    : request("POST", "/purchase", { user_id: getUserId(), ...body });
}

export function createPaymentRequest(body: PaymentRequest): Promise<PaymentRequestResponse> {
  return MOCK.paymentRequest ? mock.paymentRequest(body) : request("POST", "/payment-request", body);
}

export function getOrder(orderCode: string): Promise<Order> {
  return MOCK.getOrder ? mock.getOrder(orderCode) : request("GET", `/orders/${orderCode}`);
}

export function payOrder(orderCode: string): Promise<PayResponse> {
  return MOCK.payOrder ? mock.payOrder(orderCode) : request("POST", `/orders/${orderCode}/pay`);
}

export function getPayouts(): Promise<Payout[]> {
  return MOCK.payouts ? mock.payouts() : request("GET", "/payouts");
}

// ------------------------------------------------------- real requests

async function request<T>(method: "GET" | "POST", path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const userId = getUserId();
  if (userId) headers["X-User-Id"] = userId;

  let res: Response;
  try {
    res = await fetch(API_URL + path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError("NETWORK_ERROR", "Can't reach the server.");
  }

  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const err = data?.error;
    throw new ApiError(err?.code ?? "CHAIN_ERROR", err?.message ?? `Request failed (${res.status})`);
  }
  return data as T;
}

// ---------------------------------------------------------- fake data
// Pretends to be the backend. State is kept in localStorage so the cashier
// tab and the pay tab see the same orders. Delete this section once every
// MOCK flag is false.

const SGD_CENTS_PER_100_USD_CENTS = 135; // demo rate: US$1.00 = S$1.35
const MIN_POINTS = 100;
const MOCK_DELAY_MS = 600;
const MOCK_KEY = "mock_db";

type MockDb = {
  users: Record<string, { email: string; wallet: string; points: number; history: HistoryItem[] }>;
  orders: Record<string, Order>;
  payouts: Payout[];
};

function loadDb(): MockDb {
  try {
    const raw = localStorage.getItem(MOCK_KEY);
    if (raw) return JSON.parse(raw);
  } catch {}
  return { users: {}, orders: {}, payouts: [] };
}

function saveDb(db: MockDb) {
  try {
    localStorage.setItem(MOCK_KEY, JSON.stringify(db));
  } catch {}
}

const wait = () => new Promise((r) => setTimeout(r, MOCK_DELAY_MS));
const now = () => new Date().toISOString();
const randomHex = (bytes: number) =>
  "0x" + Array.from(crypto.getRandomValues(new Uint8Array(bytes)), (b) => b.toString(16).padStart(2, "0")).join("");
const fakeTx = () => {
  const tx_hash = randomHex(32);
  return { tx_hash, explorer_url: `https://testnet.arcscan.app/tx/${tx_hash}` };
};

function toUsdCents(amountMinor: number, currency: string): number {
  if (currency === "USD") return amountMinor;
  return Math.floor((amountMinor * 100) / SGD_CENTS_PER_100_USD_CENTS);
}

function newOrderCode(): string {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  return Array.from(crypto.getRandomValues(new Uint8Array(6)), (b) => chars[b % chars.length]).join("");
}

function currentUser(db: MockDb) {
  const id = getUserId();
  const user = id ? db.users[id] : undefined;
  if (!id || !user) throw new ApiError("USER_NOT_FOUND", "User not found.");
  return { id, user };
}

const mock = {
  async login(email: string): Promise<LoginResponse> {
    await wait();
    const db = loadDb();
    const existing = Object.entries(db.users).find(([, u]) => u.email === email);
    if (existing) {
      const [user_id, u] = existing;
      return { user_id, email, wallet_address: u.wallet, is_new: false };
    }
    const user_id = crypto.randomUUID();
    const wallet = randomHex(20);
    db.users[user_id] = { email, wallet, points: 0, history: [] };
    saveDb(db);
    return { user_id, email, wallet_address: wallet, is_new: true };
  },

  async me(): Promise<Me> {
    await wait();
    const { id, user } = currentUser(loadDb());
    return {
      user_id: id,
      email: user.email,
      points: user.points,
      points_value_cents: user.points,
      min_points_to_spend: MIN_POINTS,
      history: [...user.history].reverse(),
    };
  },

  async purchase(body: PurchaseRequest): Promise<PurchaseResponse> {
    await wait();
    const db = loadDb();
    const { user } = currentUser(db);
    const points = Math.floor(toUsdCents(body.amount_minor, body.currency) / 100);
    const tx = fakeTx();
    user.points += points;
    user.history.push({ type: "earned", points, brand: body.brand, ...tx, at: now() });
    saveDb(db);
    return { points_earned: points, ...tx };
  },

  async paymentRequest(body: PaymentRequest): Promise<PaymentRequestResponse> {
    await wait();
    const db = loadDb();
    const order_code = newOrderCode();
    const amount_usd_cents = toUsdCents(body.amount_minor, body.currency);
    db.orders[order_code] = {
      order_code,
      ...body,
      amount_usd_cents,
      status: "unpaid",
      points_applied: null,
      card_remainder_minor: null,
      tx_hash: null,
    };
    saveDb(db);
    return { order_code, amount_usd_cents, status: "unpaid", qr_payload: `apprewards://pay?order=${order_code}` };
  },

  async getOrder(orderCode: string): Promise<Order> {
    await wait();
    const order = loadDb().orders[orderCode.toUpperCase()];
    if (!order) throw new ApiError("ORDER_NOT_FOUND", "Order not found.");
    return order;
  },

  async payOrder(orderCode: string): Promise<PayResponse> {
    await wait();
    const db = loadDb();
    const { user } = currentUser(db);
    const order = db.orders[orderCode.toUpperCase()];
    if (!order) throw new ApiError("ORDER_NOT_FOUND", "Order not found.");
    if (order.status === "paid") throw new ApiError("ORDER_ALREADY_PAID", "Order already paid.");
    if (user.points < MIN_POINTS) throw new ApiError("BELOW_THRESHOLD", "You need at least 100 points to pay.");

    const points_applied = Math.min(user.points, order.amount_usd_cents);
    const remainderUsdCents = order.amount_usd_cents - points_applied;
    const card_remainder_minor =
      order.currency === "USD"
        ? remainderUsdCents
        : Math.ceil((remainderUsdCents * SGD_CENTS_PER_100_USD_CENTS) / 100);
    const tx = fakeTx();

    user.points -= points_applied;
    user.history.push({ type: "spent", points: points_applied, brand: order.brand, ...tx, at: now() });
    Object.assign(order, { status: "paid", points_applied, card_remainder_minor, tx_hash: tx.tx_hash });
    db.payouts.unshift({
      brand: order.brand,
      branch: order.branch,
      order_code: order.order_code,
      usdc_cents: points_applied,
      local_minor:
        order.currency === "USD"
          ? points_applied
          : Math.floor((points_applied * SGD_CENTS_PER_100_USD_CENTS) / 100),
      currency: order.currency,
      status: "paid_mock",
      at: now(),
    });
    saveDb(db);
    return { status: "paid", points_applied, card_remainder_minor, ...tx };
  },

  async payouts(): Promise<Payout[]> {
    await wait();
    return loadDb().payouts;
  },
};
