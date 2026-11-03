import { z } from "zod";
const cents = z.number().int().safe();
const date = z.iso.date();
const status = z.enum([
  "PROPOSED",
  "APPROVED",
  "INVOICE_DRAFTED",
  "INVOICE_SENT",
  "PAYMENT_PENDING",
  "AWAITING_VERIFICATION",
  "PARTIALLY_PAID",
  "VERIFIED_PAID",
  "OFFLINE_MARKED_PAID",
  "CANCELLED",
  "FAILED",
  "UNRESOLVED",
  "REFUNDED",
]);
export const entrySchema = z.object({
  entry_id: z.string(),
  amount_cents: cents,
  currency: z.literal("USD"),
  status,
  sequence: z.number().int().positive(),
  provider_status: z.string().nullable(),
  provider_invoice_id: z.string().nullable(),
  invoice_url: z.url().refine((value) => {
    const url = new URL(value);
    return url.protocol === 'https:' && !url.username && !url.password &&
      ['www.sandbox.paypal.com', 'sandbox.paypal.com', 'api-m.sandbox.paypal.com'].includes(url.hostname);
  }).nullable(),
  created_at: z.string(),
  updated_at: z.string(),
  verified_at: z.string().nullable(),
});
const daySchema = z.object({
  date,
  opening_balance_cents: cents,
  receipts_cents: cents,
  expenses_cents: cents,
  closing_balance_cents: cents,
});
export const forecastSchema = z.object({
  currency: z.literal("USD"),
  safety_reserve_cents: cents,
  first_reserve_breach_date: date.nullable(),
  days: z.array(daySchema).min(1).max(30),
  is_demo: z.literal(true),
  disclaimer: z.string(),
});
export const sessionSchema = z.object({
  authenticated: z.boolean(),
  password_configured: z.boolean(),
  csrf_token: z.string().nullable(),
  payments_enabled: z.boolean(),
  read_only_demo: z.boolean(),
});
export const dashboardSchema = z.object({
  business_name: z.string(),
  as_of_date: date,
  is_demo_data: z.literal(true),
  forecast: forecastSchema,
  receivables: z.array(
    z.object({
      id: z.string(),
      customer: z.string(),
      description: z.string(),
      amount_cents: cents,
      due_date: date,
      ledger_entry: entrySchema.nullable(),
    }),
  ),
  expenses: z.array(
    z.object({
      id: z.string(),
      label: z.string(),
      date,
      amount_cents: cents,
      discretionary: z.boolean(),
    }),
  ),
  payments_enabled: z.boolean(),
  recovered_cash: cents.nullable(),
  notice: z.string(),
});
export const ledgerSchema = z.object({
  entries: z.array(entrySchema),
  recovered_cash: z.array(
    z.object({ amount_cents: cents, currency: z.literal("USD") }),
  ),
  is_demo_data: z.literal(true),
});
export const rescueSchema = z.object({
  summary: z.string(),
  risk_level: z.enum(["low", "medium", "high", "unknown"]),
  source: z.enum(["ai", "deterministic"]),
  is_demo: z.boolean(),
  assumptions: z.array(z.string()),
  integration_warnings: z.array(z.string()),
  recommended_actions: z.array(
    z.object({
      action_id: z.string(),
      title: z.string(),
      estimated_impact_cents: cents.nullable(),
      explanation: z.string().nullable(),
      assumptions: z.array(z.string()),
      evidence_ids: z.array(z.string()),
      requires_approval: z.literal(true),
    }),
  ),
});
export const scenarioSchema = z.object({
  hypothetical: z.literal(true),
  baseline_shortage_date: date.nullable(),
  scenario_shortage_date: date.nullable(),
  baseline_minimum_cash_balance_cents: cents,
  scenario_minimum_cash_balance_cents: cents,
  daily_differences: z.array(
    z.object({
      date,
      baseline_closing_balance_cents: cents,
      scenario_closing_balance_cents: cents,
      closing_balance_difference_cents: cents,
    }),
  ),
  assumptions: z.array(z.string()),
  limitations: z.array(z.string()),
});
export type Session = z.infer<typeof sessionSchema>;
export type Dashboard = z.infer<typeof dashboardSchema>;
export type Entry = z.infer<typeof entrySchema>;
export type Forecast = z.infer<typeof forecastSchema>;
export type Rescue = z.infer<typeof rescueSchema>;
export type Scenario = z.infer<typeof scenarioSchema>;
export type Ledger = z.infer<typeof ledgerSchema>;
export class ApiError extends Error {
  constructor(
    message: string,
    public status = 0,
  ) {
    super(message);
  }
}
export async function request<T>(
  path: string,
  schema: z.ZodType<T>,
  options: { method?: string; body?: unknown; csrf?: string | null } = {},
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 45000);
  try {
    const res = await fetch("/api/v1" + path, {
      method: options.method ?? "GET",
      credentials: "same-origin",
      signal: controller.signal,
      headers: {
        ...(options.body !== undefined
          ? { "Content-Type": "application/json" }
          : {}),
        ...(options.csrf ? { "X-CSRF-Token": options.csrf } : {}),
      },
      body:
        options.body === undefined ? undefined : JSON.stringify(options.body),
    });
    const data = await res.json();
    if (!res.ok)
      throw new ApiError(
        typeof data?.error?.message === "string"
          ? data.error.message
          : "The request could not be completed.",
        res.status,
      );
    const parsed = schema.safeParse(data);
    if (!parsed.success)
      throw new ApiError(
        "The server returned an unexpected response. Values have been hidden; please retry.",
      );
    return parsed.data;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(
      "Connection interrupted. The result is unknown. Refresh the ledger before trying a payment action again.",
    );
  } finally {
    clearTimeout(timer);
  }
}
// Division is presentation only. All stored and transmitted money is integer cents.
export const money = (value: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(
    value / 100,
  );
export const dayLabel = (value: string) =>
  new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  }).format(new Date(value + "T12:00:00Z"));
