const API = (import.meta.env.VITE_API_URL as string) || "http://127.0.0.1:8000";
const TOKEN_KEY = "paper_token";

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (t: string) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function downloadFile(path: string, filename: string): Promise<void> {
  const token = tokenStore.get();
  const res = await fetch(API + path, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new ApiError(res.status, res.statusText);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/** Turn a FastAPI error `detail` into a readable string. `detail` is a plain
 * string for HTTPExceptions, but a list of {loc, msg} objects for 422
 * validation errors — which would otherwise stringify to "[object Object]". */
function formatDetail(detail: unknown): string | undefined {
  if (detail == null) return undefined;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((e) => {
        const loc = Array.isArray(e?.loc) ? e.loc[e.loc.length - 1] : undefined;
        const msg = e?.msg ?? JSON.stringify(e);
        return loc && loc !== "body" ? `${loc}: ${msg}` : msg;
      })
      .join("; ");
  }
  return JSON.stringify(detail);
}

async function req<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const token = tokenStore.get();
  const res = await fetch(API + path, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(opts.headers || {}),
    },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = formatDetail(body.detail) ?? JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

const get = <T>(p: string) => req<T>(p);
const post = <T>(p: string, body?: unknown) =>
  req<T>(p, { method: "POST", body: body ? JSON.stringify(body) : undefined });
const put = <T>(p: string, body?: unknown) =>
  req<T>(p, { method: "PUT", body: body ? JSON.stringify(body) : undefined });
const del = <T>(p: string) => req<T>(p, { method: "DELETE" });

// --- types ---
export interface User {
  id: string;
  email: string;
  full_name: string;
  email_verified: boolean;
}
export interface Tenant {
  id: string;
  name: string;
  type: "company" | "fund" | "firm";
}
export interface Entity {
  id: string;
  tenant_id: string;
  name: string;
  type: string;
  cin: string | null;
  pan: string | null;
  incorporation_date: string | null;
  stage: string;
}
export interface IncorporationFounder {
  name: string;
  email?: string | null;
  din?: string | null;
  shares: number;
  is_director: boolean;
}
export interface Incorporation {
  id: string;
  tenant_id: string;
  status: string;
  name_options: string[];
  company_name: string | null;
  entity_type: string;
  state: string;
  registered_office: string;
  authorised_capital: string;
  paid_up_capital: string;
  par_value: string;
  fy_end: string | null;
  founders: IncorporationFounder[];
  srn: string | null;
  cin: string | null;
  entity_id: string | null;
}
export interface ChecklistItem {
  key: string;
  title: string;
  hint: string;
  tab: string;
  done: boolean;
}
export interface StageGuide {
  entity_id: string;
  stage: string;
  label: string;
  headline: string;
  suggested_stage: string | null;
  stages: { key: string; label: string }[];
  tabs: string[];
  features: Record<string, boolean>;
  checklist: ChecklistItem[];
  progress: { done: number; total: number };
}
export interface SecurityClass {
  id: string;
  name: string;
  kind: string;
  par_value: string;
  pref_multiple: string;
  participating: boolean;
  seniority: number;
  anti_dilution: string;
  orig_issue_price: string | null;
}
export interface AntiDilutionHolder {
  stakeholder_id: string;
  stakeholder_name: string | null;
  held: number;
  additional_shares: number;
}
export interface AntiDilutionPreview {
  security_class_id: string;
  method: string;
  orig_issue_price: string;
  new_price: string;
  adjusted_price: string;
  conversion_ratio: string;
  holders: AntiDilutionHolder[];
}
export interface WaterfallPayout {
  stakeholder_id: string;
  stakeholder_name: string | null;
  payout: string;
}
export interface WaterfallResult {
  entity_id: string;
  exit_amount: string;
  distributed: string;
  payouts: WaterfallPayout[];
}
export interface RightsIssue {
  id: string;
  security_class_id: string;
  ratio_num: number;
  ratio_den: number;
  price_per_unit: string;
  record_date: string;
  status: string;
}
export interface Entitlement {
  stakeholder_id: string;
  stakeholder_name: string | null;
  held: number;
  entitled: number;
  subscribed: number;
}
export interface Stakeholder {
  id: string;
  name: string;
  type: string;
  email: string | null;
}
export interface CapTableRow {
  stakeholder_id: string;
  stakeholder_name: string;
  stakeholder_type: string;
  security_class_id: string;
  security_class: string;
  kind: string;
  quantity: number;
  amount_invested: string;
  ownership_pct: number;
}
export interface CapTable {
  entity_id: string;
  total_shares: number;
  total_invested: string;
  holders: CapTableRow[];
}
export interface FullyDilutedRow {
  stakeholder_id: string | null;
  name: string | null;
  type: string | null;
  issued: number;
  options: number;
  converts: number;
  total: number;
  pct: number;
}
export interface FullyDiluted {
  entity_id: string;
  assumed_price: string | null;
  issued_shares: number;
  option_shares: number;
  pool_unallocated: number;
  convertible_shares: number;
  fully_diluted_shares: number;
  rows: FullyDilutedRow[];
  excluded_instruments: string[];
}
export interface StepDef {
  key: string;
  title: string;
  type: string;
  assignee_role: string | null;
}
export interface WorkflowDefinition {
  key: string;
  version: number;
  title: string;
  steps: StepDef[];
}
export interface StepInstance {
  step_key: string;
  title: string;
  type: string;
  order_index: number;
  status: "pending" | "active" | "complete" | "skipped";
  assignee_role: string | null;
  output: Record<string, unknown> | null;
}
export interface WorkflowRun {
  id: string;
  entity_id: string;
  definition_key: string;
  definition_version: number;
  title: string;
  status: "running" | "completed" | "cancelled";
  context: Record<string, unknown>;
  steps: StepInstance[];
}
export interface DocTemplate {
  key: string;
  name: string;
  doc_type: string;
  body: string;
}
export interface Document {
  id: string;
  entity_id: string;
  type: string;
  title: string;
  status: "draft" | "generated" | "signed";
  template_key: string | null;
  current_version: number;
  subject_type: string | null;
  subject_id: string | null;
  content: string | null;
}
export interface SignatureRequest {
  id: string;
  document_id: string;
  provider: string;
  status: "pending" | "completed" | "declined";
  signatories: unknown[];
  completed_at: string | null;
}
export interface DataRoomItem {
  id: string;
  document_id: string;
  document_title: string | null;
  folder: string;
  order_index: number;
}
export interface Grant {
  id: string;
  email: string;
  permissions: string;
  expiry: string | null;
}
export interface DataRoom {
  id: string;
  entity_id: string;
  name: string;
  scope: string;
  items: DataRoomItem[];
  grants: Grant[];
}
export interface Engagement {
  document_id: string | null;
  actor: string;
  views: number;
}
export interface Obligation {
  id: string;
  form_code: string;
  title: string;
  category: string;
  period_label: string;
  due_date: string;
  status: "due" | "in_prep" | "filed" | "acknowledged";
  assignee: string | null;
  srn: string | null;
  overdue: boolean;
}
export interface Fund {
  id: string;
  entity_id: string;
  sebi_category: string;
  structure: string;
  currency: string;
  target_corpus: string;
  carry_pct: string;
  hurdle_pct: string;
  mgmt_fee_pct: string;
  fee_basis: string;
}
export interface LP {
  id: string;
  name: string;
  email: string | null;
  commitment: string;
}
export interface DrawdownNotice {
  id: string;
  lp_id: string;
  amount: string;
  paid: boolean;
  acknowledged_at: string | null;
}
export interface CapitalCall {
  id: string;
  call_no: number;
  pct: string;
  purpose: string | null;
  due_date: string | null;
  notices: DrawdownNotice[];
}
export interface Distribution {
  id: string;
  dist_no: number;
  gross_amount: string;
  kind: string;
  carry_amount: string;
  roc_amount: string;
  pref_amount: string;
  catchup_amount: string;
  date: string | null;
}
export interface CapitalAccount {
  lp_id: string;
  lp_name: string;
  committed: string;
  drawn: string;
  remaining: string;
  distributed: string;
  fees_charged: string;
  units: string;
}
export interface CapitalAccounts {
  fund_id: string;
  totals: { committed: string; drawn: string; remaining: string; distributed: string };
  accounts: CapitalAccount[];
}
export interface PortfolioInvestment {
  id: string;
  company_name: string;
  instrument: string;
  amount: string;
  ownership_pct: string;
  invested_on: string | null;
  current_value: string | null;
  marked_on: string | null;
}
export interface EsopScheme {
  id: string;
  name: string;
  pool_size: number;
}
export interface EsopGrant {
  id: string;
  scheme_id: string;
  stakeholder_id: string;
  stakeholder_name: string | null;
  grant_type: "option" | "rsu" | "rsa";
  quantity: number;
  exercise_price: string;
  grant_date: string;
  cliff_months: number;
  total_months: number;
  vested: number;
  exercised: number;
  exercisable: number;
  unvested: number;
}
export interface AdvisorAccess {
  id: string;
  entity_id: string;
  email: string;
  firm_name: string;
  role: string;
}
export interface AdvisorEntity {
  entity_id: string;
  entity_name: string;
  entity_type: string;
  tenant_name: string;
  firm_name: string;
  role: string;
}
export interface Valuation {
  id: string;
  method: string;
  fmv_per_share: string;
  valuation_date: string;
  valuer_name: string | null;
  valid_until: string | null;
  basis: string | null;
  status: string;
}
export interface CurrentFmv {
  fmv_per_share: string | null;
  valuation_id: string | null;
  valuation_date: string | null;
}
export interface ScorecardFactor {
  key: string;
  label: string;
  weight: string;
}
export interface ValuationEstimateResult {
  methods: Record<string, string>;
  detail: Record<string, Record<string, string>>;
  weights: Record<string, string>;
  blended_value: string;
  fd_shares: number;
  per_share: string | null;
  disclaimer: string;
}
export interface ValuationEstimate {
  id: string;
  label: string;
  inputs: Record<string, unknown>;
  results: ValuationEstimateResult;
  created_at: string;
}
export interface Smartfill {
  base_annual_revenue: string;
  base_annual_expenses: string;
  assumed_growth_pct: string;
  months_of_data: number;
  projections: { year: number; revenue: string; expenses: string }[];
}
export interface Provider {
  id: string;
  name: string;
  category: string;
  firm: string | null;
  email: string | null;
  profile: string | null;
  active: boolean;
  verified: boolean;
}
export interface ServiceEngagement {
  id: string;
  entity_id: string;
  provider_id: string;
  provider_name: string | null;
  provider_category: string | null;
  scope: string | null;
  status: string;
  deliverable_doc_id: string | null;
}
export interface Touchpoint {
  id: string;
  date: string;
  attendee: string | null;
  summary: string | null;
}
export interface AuditEngagement {
  id: string;
  type: string;
  period_label: string;
  status: string;
  findings: string | null;
}
export interface AdminSubscription {
  id: string;
  entity_id: string;
  tier: string;
  status: string;
  provider_id: string | null;
  touchpoints: Touchpoint[];
  audits: AuditEngagement[];
}
export interface SPV {
  id: string;
  entity_id: string;
  sponsor: string;
  target_company: string;
  structure: string;
  portco_entity_id: string | null;
  carry_pct: string;
  min_ticket: string;
}
export interface CoInvestor {
  id: string;
  name: string;
  email: string | null;
  commitment: string;
  contributed: string;
  paid: boolean;
  status: string;
}
export interface SPVSummary {
  spv_id: string;
  co_investor_count: number;
  committed: string;
  contributed: string;
  by_status: Record<string, number>;
}
export interface Round {
  id: string;
  entity_id: string;
  name: string;
  instrument: string;
  pre_money: string;
  target_amount: string;
  price_per_share: string;
  security_class_id: string | null;
  valuation_id: string | null;
  status: string;
}
export interface RoundCommitment {
  id: string;
  investor_name: string;
  investor_email: string | null;
  investor_kind: string;
  amount: string;
  shares: number | null;
  is_foreign: boolean;
  status: string;
  stakeholder_id: string | null;
}
export interface RoundSummary {
  round_id: string;
  status: string;
  instrument: string;
  pre_money: string;
  target_amount: string;
  committed: string;
  post_money: string;
  price_per_share: string;
  existing_shares: number;
  new_shares: number;
  implied_new_ownership_pct: number;
  commitment_count: number;
}
export interface Resolution {
  id: string;
  meeting_id: string | null;
  type: string;
  title: string;
  text: string;
  status: string;
  passed_date: string | null;
  document_id: string | null;
}
export interface AgendaItem {
  id: string;
  order_index: number;
  title: string;
}
export interface Meeting {
  id: string;
  entity_id: string;
  type: string;
  title: string;
  date: string;
  location: string | null;
  quorum: number | null;
  status: string;
  minutes: string | null;
  notice_document_id: string | null;
  resolutions: Resolution[];
  agenda_items: AgendaItem[];
}
export interface Director {
  id: string;
  name: string;
  din: string | null;
  designation: string;
  appointed_on: string;
  resigned_on: string | null;
  status: string;
}
export interface AuditEntry {
  id: string;
  actor_email: string | null;
  method: string;
  path: string;
  status_code: number;
  created_at: string;
}
export interface AppNotification {
  id: string;
  type: string;
  title: string;
  body: string | null;
  read: boolean;
  created_at: string;
}
export interface ClassSlice {
  name: string;
  kind: string | null;
  quantity: number;
  pct: number;
}
export interface TimelineEvent {
  id: string;
  date: string;
  kind: string;
  text: string;
}
export interface EntityTask {
  kind: string;
  tab: string;
  severity: "red" | "amber" | "ok";
  title: string;
  detail: string;
}
export interface EntityTasks {
  tasks: EntityTask[];
  counts: { total: number; overdue: number };
}
export interface ValueHistory {
  series: { date: string; value: string }[];
  current_value: string;
  holdings: number;
}
export interface Dashboard {
  entity: { id: string; name: string; type: string };
  cap_table: {
    total_shares: number;
    total_invested: string;
    holders: number;
    by_class: ClassSlice[];
  };
  capital: {
    authorized_shares: number | null;
    issued: number;
    available: number | null;
    esop_pool: number;
    esop_granted: number;
  };
  valuation: {
    status: "active" | "expired" | "missing";
    fmv_per_share: string | null;
    method: string | null;
    valuation_date: string | null;
    valid_until: string | null;
    valuer_name: string | null;
  };
  fundraising: { rounds: number; open_rounds: number };
  compliance: { total: number; overdue: number };
  esop: { schemes: number; options_granted: number };
  governance: { meetings: number; pending_resolutions: number };
  documents: number;
  data_rooms: number;
  fund?: { committed: string; drawn: string; lps: number };
}
export interface FileItem {
  id: string;
  title: string;
  type: string;
  status: string;
  current_version: number;
  subject_type: string | null;
  created_at: string;
}
export interface TaxRecord {
  id: string;
  type: string;
  period_label: string;
  reference: string | null;
  amount: string | null;
  filed_on: string | null;
  document_id: string | null;
}
export interface TeamMember {
  id: string;
  name: string;
  email: string | null;
  title: string | null;
  employment_type: string;
  joined_on: string | null;
  left_on: string | null;
  stakeholder_id: string | null;
  status: string;
}
export interface Counterparty {
  id: string;
  name: string;
  kind: string;
  contact_name: string | null;
  contact_email: string | null;
}
export interface InvestorAccess {
  id: string;
  email: string;
  stakeholder_id: string | null;
  status: string;
}
export interface InvestorUpdate {
  id: string;
  title: string;
  body: string;
  created_at: string;
}
export interface PortalInstrument {
  id: string;
  instrument_type: string;
  investor_kind: string;
  principal: string;
  valuation_cap: string | null;
  discount_pct: string;
  issue_date: string;
  status: string;
  converted_shares: number | null;
}
export interface PortalConsent {
  id: string;
  title: string | null;
  type: string | null;
  status: string;
}
export interface PortalSaleRequest {
  id: string;
  quantity: number;
  price_per_unit: string;
  status: string;
}
export interface PortalCompany {
  entity_id: string;
  entity_name: string;
  entity_type: string;
  holdings: CapTableRow[];
  current_value: string;
  instruments: PortalInstrument[];
  consents: PortalConsent[];
  sale_requests: PortalSaleRequest[];
  stakeholder_id: string | null;
  documents: { id: string; title: string; data_room: string }[];
  updates: InvestorUpdate[];
}
export interface SecondaryRequestRow {
  id: string;
  seller: string | null;
  security_class: string | null;
  quantity: number;
  price_per_unit: string;
  status: string;
  buyer: string | null;
}
export interface ScenarioRow {
  name: string | null;
  type: string | null;
  before: number;
  before_pct: number;
  after_safes_pct: number;
  after: number;
  after_pct: number;
  dilution_pct: number;
}
export interface Scenario {
  price_per_share: string;
  pre_money: string;
  new_money: string;
  post_money: string;
  pool_top_up: number;
  new_shares: number;
  safe_shares_converted: number;
  fd_pre: number;
  fd_post: number;
  rows: ScenarioRow[];
}
export interface WaterfallRange {
  exit_amounts: string[];
  rows: { stakeholder_id: string; stakeholder_name: string | null; payouts: string[] }[];
}
export interface ExerciseRequestRow {
  id: string;
  employee: string | null;
  grant_id: string;
  quantity: number;
  cashless: boolean;
  status: string;
}
export interface CapTableImportReport {
  valid: boolean;
  errors: { row: number; error: string }[];
  rows: unknown[];
  summary: {
    issuances: number;
    stakeholders_to_create: string[];
    classes_to_create: string[];
    total_shares: number;
    total_invested: string;
    warning: string | null;
  } | null;
  applied?: boolean;
  classes_created?: number;
  stakeholders_created?: number;
  issuances_created?: number;
}
export interface ConsentTally {
  tally: { approved: number; rejected: number; pending: number };
  consents: { id: string; email: string; status: string; decided_at: string | null }[];
}
export interface Deal {
  id: string;
  fund_id: string;
  company_name: string;
  sector: string | null;
  stage: string;
  amount: string;
  notes: string | null;
  investment_id: string | null;
}
export interface DealContact {
  id: string;
  name: string;
  role: string | null;
  email: string | null;
  note: string | null;
}
export interface DealActivity {
  id: string;
  kind: string;
  body: string;
  occurred_on: string;
}
export interface DealCrm {
  contacts: DealContact[];
  activities: DealActivity[];
}
export interface FundPerformance {
  fund_id: string;
  as_of: string;
  paid_in: string;
  distributed: string;
  nav: string;
  positions_marked: number;
  positions_at_cost: number;
  dpi: string | null;
  rvpi: string | null;
  tvpi: string | null;
  xirr_pct: number | null;
  management_fee_accrued: string;
  fee_basis: string;
  mgmt_fee_pct: string;
  units_outstanding: string;
  nav_per_unit: string | null;
}
export interface FundPlan {
  has_plan: boolean;
  inputs: {
    fund_size: string;
    fund_life_years: number;
    investment_period_years: number;
    est_expenses: string;
    reserve_pct: string;
    avg_initial_cheque: string;
    avg_entry_valuation: string;
    projected_gross_moic: string;
    mgmt_fee_pct: string;
    carry_pct: string;
  };
  derived: {
    lifetime_fees: string;
    investable: string;
    initial_capital: string;
    reserve_capital: string;
    num_initial_deals: number;
    avg_entry_ownership_pct: string;
    gross_proceeds: string;
    gp_carry: string;
    net_to_lps: string;
    gross_tvpi: string | null;
    net_tvpi: string | null;
    net_irr_pct: number | null;
  };
  pacing: { year: number; initial: string; reserve: string; deployed: string; cumulative: string }[];
  actual: {
    committed: string;
    deployed: string;
    deals: number;
    committed_vs_target_pct: number | null;
    deployed_vs_initial_pct: number | null;
    deals_vs_plan_pct: number | null;
  };
}
export interface FundPlanInput {
  fund_size: string;
  fund_life_years: number;
  investment_period_years: number;
  est_expenses: string;
  reserve_pct: string;
  avg_initial_cheque: string;
  avg_entry_valuation: string;
  projected_gross_moic: string;
}
export interface LPProspect {
  id: string;
  name: string;
  firm: string | null;
  kind: string;
  email: string | null;
  stage: string;
  target_commitment: string;
  notes: string | null;
  lp_id: string | null;
}
export interface FundraiseSummary {
  fund_id: string;
  target_corpus: string;
  committed: string;
  soft_circled: string;
  pipeline: string;
  progress_pct: number | null;
  by_stage: Record<string, { count: number; target: string }>;
  prospects: LPProspect[];
}
export interface PortfolioValuation {
  id: string;
  as_of: string;
  value: string;
  methodology: string;
  methodology_label: string;
  valuer: string | null;
  is_independent: boolean;
  note: string | null;
}
export interface PortfolioValuationInput {
  as_of: string;
  value: string;
  methodology: string;
  valuer?: string | null;
  is_independent: boolean;
  note?: string | null;
}
export interface ValuationSummary {
  fund_id: string;
  policy: { valuer_name: string | null; frequency_months: number };
  methodologies: Record<string, string>;
  totals: { holdings: number; valued: number; stale: number; independent: number };
  holdings: {
    investment_id: string;
    company_name: string;
    cost: string;
    valuations: number;
    latest: PortfolioValuation | null;
    stale: boolean;
  }[];
}
export interface PortfolioKPI {
  id: string;
  period_label: string;
  as_of: string;
  revenue: string | null;
  cash: string | null;
  monthly_burn: string | null;
  headcount: number | null;
  runway_months: number | null;
  note: string | null;
}
export interface PortfolioKPIInput {
  period_label: string;
  as_of: string;
  revenue?: string | null;
  cash?: string | null;
  monthly_burn?: string | null;
  headcount?: number | null;
  note?: string | null;
}
export interface PortfolioMonitoring {
  fund_id: string;
  totals: {
    companies: number;
    reporting: number;
    latest_revenue: string;
    cash: string;
    low_runway: number;
  };
  companies: {
    investment_id: string;
    company_name: string;
    ownership_pct: string;
    periods: number;
    latest: PortfolioKPI | null;
    revenue_growth_pct: number | null;
    runway_months: number | null;
    low_runway: boolean;
    revenue_series: { x: string; y: number }[];
  }[];
}
export interface FundFinancials {
  fund_id: string;
  as_of: string;
  operations: {
    realized_gains: string;
    unrealized_appreciation: string;
    total_investment_income: string;
    management_fees: string;
    net_increase_from_operations: string;
  };
  cash_flow: {
    contributions: string;
    investments_made: string;
    distributions_to_lps: string;
    carry_paid: string;
    management_fees_paid: string;
    net_change_in_cash: string;
    ending_cash: string;
  };
  balance_sheet: {
    investments_at_fair_value: string;
    cash: string;
    total_assets: string;
    liabilities: string;
    net_assets: string;
  };
  capital_roll_forward: {
    beginning: string;
    contributions: string;
    net_increase_from_operations: string;
    distributions_to_lps: string;
    carry_to_gp: string;
    ending_net_assets: string;
  };
  disclosures: {
    committed: string;
    uncalled: string;
    invested_at_cost: string;
    positions_at_cost: number;
  };
  balances: boolean;
}
export interface LookThrough {
  fund_id: string;
  share_pct: number;
  holdings: {
    company_name: string;
    instrument: string;
    fund_cost: string;
    fund_value: string;
    look_through_cost: string;
    look_through_value: string;
    moic: string | null;
  }[];
  totals: { look_through_cost: string; look_through_value: string };
}
export interface SOIHolding {
  id: string;
  company_name: string;
  instrument: string;
  invested_on: string | null;
  cost: string;
  current_value: string;
  marked: boolean;
  ownership_pct: string;
  moic: string | null;
  unrealized_gain: string;
  pct_of_nav: number;
}
export interface ScheduleOfInvestments {
  fund_id: string;
  holdings: SOIHolding[];
  totals: {
    cost: string;
    current_value: string;
    unrealized_gain: string;
    moic: string | null;
    count: number;
  };
}
export interface PortalCallNotice {
  notice_id: string;
  call_no: number | null;
  purpose: string | null;
  due_date: string | null;
  amount: string;
  paid: boolean;
  acknowledged_at: string | null;
  overdue: boolean;
}
export interface PortalFundEntry {
  fund_id: string;
  fund_name: string | null;
  sebi_category: string;
  account: { committed: string; drawn: string; remaining: string; distributed: string } | null;
  capital_calls: PortalCallNotice[];
  look_through: LookThrough;
  performance: FundPerformance;
  statements: { id: string; title: string; created_at: string }[];
  updates: InvestorUpdate[];
}
export interface LPSummary {
  funds: number;
  committed: string;
  drawn: string;
  remaining: string;
  distributed: string;
  nav_value: string;
  pending_calls: number;
}
export interface EquityGrant {
  grant_id: string;
  exercise_requests: { id: string; quantity: number; status: string }[];
  entity_name: string | null;
  granted: number;
  vested: number;
  exercised: number;
  exercisable: number;
  exercise_price: string;
  grant_date: string;
  current_fmv: string | null;
  unrealized_gain: string | null;
  vesting_pct: number;
  full_vest_date: string;
  next_vests: { date: string; quantity: number }[];
  grant_type: "option" | "rsu" | "rsa";
  today_value: string | null;
  exercised_value: string | null;
  max_potential_value: string | null;
  unit_value: string | null;
  segments: { exercised: number; vested: number; unvested: number };
}
export interface EsopOverview {
  pool_size: number;
  granted: number;
  available: number;
  used_pct: number;
  vested: number;
  exercised: number;
  exercisable: number;
  unvested: number;
  grantees: number;
  schemes: number;
  by_type: Record<string, number>;
  leaderboard: { name: string; granted: number }[];
  pool_segments: {
    exercised: number;
    vested_unexercised: number;
    unvested: number;
    available: number;
  };
}
export interface EsopExpense {
  as_of: string;
  grants: {
    grant_id: string;
    grant_type: string;
    quantity: number;
    fair_value_per_unit: string;
    total_fair_value: string;
    recognized_to_date: string;
    unrecognized: string;
  }[];
  by_financial_year: { fy: string; expense: string }[];
  unpriced_grants: number;
  totals: { total_fair_value: string; recognized_to_date: string; unrecognized: string };
}
export interface InvestorMetrics {
  shares_issued: number;
  stakeholders: number;
  capital_raised: string;
  fmv_per_share: string | null;
  valuation_date: string | null;
  open_rounds: number;
  options_granted: number;
  runway_months: number | null;
  latest_cash: string | null;
  monthly_burn: string | null;
  compliance_overdue: number;
}
export interface ExerciseWindow {
  id: string;
  name: string;
  opens_on: string;
  closes_on: string;
  state?: "open" | "upcoming" | "closed";
}
export interface LiquidityEvent {
  id: string;
  name: string;
  kind: string;
  price_per_share: string;
  opens_on: string;
  closes_on: string;
  status: string;
  tenders: number;
  shares_tendered: number;
  indicative_payout: string;
}
export interface PortalLiquidityEvent {
  id: string;
  name: string;
  kind: string;
  entity_name: string | null;
  price_per_share: string;
  closes_on: string;
  my_tendered: number;
  holdings: { security_class_id: string; security_class: string; kind: string; quantity: number }[];
}
export interface GrantScheduleEvent {
  date: string;
  units: number;
  cumulative: number;
  past: boolean;
}
export interface GrantDetail {
  grant_id: string;
  grant_type: "option" | "rsu" | "rsa";
  entity_name: string | null;
  granted: number;
  vested: number;
  exercised: number;
  exercisable: number;
  unvested: number;
  exercise_price: string;
  grant_date: string;
  current_fmv: string | null;
  vesting_pct: number;
  full_vest_date: string;
  next_vests: { date: string; quantity: number }[];
  unit_value: string | null;
  today_value: string | null;
  exercised_value: string | null;
  max_potential_value: string | null;
  segments: { exercised: number; vested: number; unvested: number };
  schedule: GrantScheduleEvent[];
}
export interface PortalSPVDeal {
  co_investor_id: string;
  spv_name: string | null;
  sponsor: string;
  target_company: string;
  structure: string;
  carry_pct: string;
  min_ticket: string;
  status: string;
  commitment: string;
  contributed: string;
  documents: { id: string; title: string; status: string }[];
  updates: InvestorUpdate[];
}
export interface DiligenceFinding {
  code: string;
  severity: "high" | "medium" | "low";
  title: string;
  detail: string;
  tab: string;
}
export interface DiligenceResult {
  entity_id: string;
  as_of: string;
  score: number;
  checks_run: number;
  findings: DiligenceFinding[];
  counts: Record<string, number>;
}
export interface FunnelLink {
  id: string;
  entity_id: string;
  round_id: string;
  data_room_id: string | null;
  token: string;
  active: boolean;
}
export interface FunnelProspect {
  id: string;
  name: string;
  firm: string | null;
  email: string | null;
  stage: string;
  check_size: string | null;
  last_contact: string | null;
  data_room_views: number;
  commitment: { id: string; amount: string; status: string } | null;
}
export interface FunnelView {
  link: { token: string; active: boolean; data_room_id: string | null } | null;
  prospects: FunnelProspect[];
}
export interface PublicFunnelInfo {
  company: string | null;
  round: string | null;
  instrument: string | null;
  target_amount: string | null;
  has_data_room: boolean;
}
export interface TermSheetFinding {
  code: string;
  severity: "red" | "amber" | "ok";
  title: string;
  detail: string;
  snippet: string | null;
}
export interface TermSheetScan {
  verdict: string;
  counts: Record<string, number>;
  rules_run: number;
  findings: TermSheetFinding[];
  disclaimer: string;
}
export interface InstrumentExecution {
  board: string | null;
  agreement: string | null;
  signature: string | null;
}
export interface PortalDashboard {
  summary: {
    companies: number;
    funds: number;
    spvs: number;
    total_invested: string;
    portfolio_value: string;
    moic: string | null;
    total_committed: string;
    options_vested: number;
    options_exercisable: number;
  };
  lp_summary: LPSummary;
  companies: PortalCompany[];
  funds: PortalFundEntry[];
  spvs: PortalSPVDeal[];
  equity_grants: EquityGrant[];
  liquidity_events: PortalLiquidityEvent[];
}
export interface Prospect {
  id: string;
  name: string;
  firm: string | null;
  email: string | null;
  stage: string;
  check_size: string | null;
  notes: string | null;
  round_id: string | null;
  last_contact: string | null;
  commitment_id: string | null;
}
export interface Eligibility {
  eligible: boolean;
  entity_type: string;
  reasons: string[];
}
export interface Recognition {
  id: string;
  entity_id: string;
  status: string;
  dpiit_number: string | null;
  recognised_on: string | null;
  valid_until: string | null;
}
export interface Benefit {
  id: string;
  type: string;
  status: string;
  reference: string | null;
}
export interface Runway {
  snapshots: { period: string; cash_balance: string; monthly_burn: string; revenue: string }[];
  latest_cash: string | null;
  latest_revenue?: string | null;
  avg_monthly_burn: string | null;
  runway_months: number | null;
}
export interface SBO {
  id: string;
  name: string;
  pan: string | null;
  percentage: string;
  nature: string | null;
}
export interface Charge {
  id: string;
  holder: string;
  amount: string;
  charge_type: string;
  created_on: string;
  satisfied: boolean;
}
export interface Registration {
  id: string;
  kind: string;
  state: string;
  number: string | null;
  status: string;
}
export interface Alert {
  entity_id: string;
  entity_name: string;
  kind: string;
  title: string;
  due_date: string;
  overdue: boolean;
}
export interface Instrument {
  id: string;
  investor_name: string;
  investor_kind: string;
  instrument_type: string;
  principal: string;
  valuation_cap: string | null;
  discount_pct: string;
  interest_pct: string;
  issue_date: string;
  status: string;
  converted_shares: number | null;
}
export interface DematRec {
  id: string;
  security_class_id: string;
  isin: string | null;
  depository: string;
  status: string;
}
export interface FounderVesting {
  id: string;
  stakeholder_id: string;
  security_class_id: string;
  total_shares: number;
  vested: number;
  unvested: number;
  cliff_months: number;
  total_months: number;
  start_date: string;
  repurchased: boolean;
}
export interface DataRoomQuestion {
  id: string;
  asker: string;
  question: string;
  answer: string | null;
  answered_by: string | null;
}
export interface Contract {
  id: string;
  counterparty_id: string;
  counterparty_name: string | null;
  counterparty_kind: string | null;
  title: string;
  type: string;
  value: string | null;
  currency: string;
  start_date: string | null;
  end_date: string | null;
  renewal_date: string | null;
  auto_renew: boolean;
  status: string;
  document_id: string | null;
  days_to_renewal: number | null;
  renewal_overdue: boolean;
}

// --- endpoints ---
export const api = {
  signup: (b: { email: string; full_name: string; password: string }) =>
    post<User>("/auth/signup", b),
  login: (b: { email: string; password: string }) =>
    post<{ access_token: string }>("/auth/login", b),
  refresh: () => post<{ access_token: string }>("/auth/refresh"),
  verifyEmail: (token: string) => post<User>("/auth/verify-email", { token }),
  me: () => get<User>("/auth/me"),

  listTenants: () => get<Tenant[]>("/tenants"),
  createTenant: (b: { name: string; type: string }) => post<Tenant>("/tenants", b),

  listEntities: (tid: string) => get<Entity[]>(`/tenants/${tid}/entities`),
  createEntity: (tid: string, b: Partial<Entity>) =>
    post<Entity>(`/tenants/${tid}/entities`, b),
  getEntity: (eid: string) => get<Entity>(`/entities/${eid}`),
  stageGuide: (eid: string) => get<StageGuide>(`/entities/${eid}/stage-guide`),
  listIncorporations: (tid: string) => get<Incorporation[]>(`/tenants/${tid}/incorporations`),
  createIncorporation: (tid: string, b: unknown) =>
    post<Incorporation>(`/tenants/${tid}/incorporations`, b),
  prepareIncorporation: (tid: string, iid: string) =>
    post<Incorporation>(`/tenants/${tid}/incorporations/${iid}/prepare`),
  incorporationFiled: (tid: string, iid: string, srn: string) =>
    post<Incorporation>(`/tenants/${tid}/incorporations/${iid}/filed`, { srn }),
  incorporationRegistered: (tid: string, iid: string, b: unknown) =>
    post<{ entity_id: string; shares_issued: number; directors_registered: number; obligations_created: number }>(
      `/tenants/${tid}/incorporations/${iid}/registered`, b
    ),
  setStage: (eid: string, stage: string) => put<StageGuide>(`/entities/${eid}/stage`, { stage }),

  listSecurityClasses: (eid: string) =>
    get<SecurityClass[]>(`/entities/${eid}/security-classes`),
  createSecurityClass: (eid: string, b: unknown) =>
    post<SecurityClass>(`/entities/${eid}/security-classes`, b),
  listStakeholders: (eid: string) => get<Stakeholder[]>(`/entities/${eid}/stakeholders`),
  createStakeholder: (eid: string, b: unknown) =>
    post<Stakeholder>(`/entities/${eid}/stakeholders`, b),
  createIssuance: (eid: string, b: unknown) => post(`/entities/${eid}/issuances`, b),
  capTable: (eid: string) => get<CapTable>(`/entities/${eid}/cap-table`),
  fullyDiluted: (eid: string, assumedPrice?: string) =>
    get<FullyDiluted>(
      `/entities/${eid}/cap-table/fully-diluted` +
        (assumedPrice ? `?assumed_price=${encodeURIComponent(assumedPrice)}` : "")
    ),
  modelScenario: (eid: string, b: unknown) => post<Scenario>(`/entities/${eid}/scenarios/model`, b),
  waterfallRange: (eid: string, amounts: string) =>
    get<WaterfallRange>(`/entities/${eid}/waterfall-range?amounts=${encodeURIComponent(amounts)}`),
  requestExercise: (b: unknown) =>
    post<{ id: string; status: string }>(`/portal/exercise-requests`, b),
  listExerciseRequests: (eid: string) =>
    get<ExerciseRequestRow[]>(`/entities/${eid}/exercise-requests`),
  decideExerciseRequest: (rid: string, b: unknown) =>
    post<{ id: string; status: string; net_shares?: number; perquisite_value?: string }>(
      `/exercise-requests/${rid}/decide`, b
    ),
  antiDilution: (eid: string, classId: string, newPrice: string, newShares: string) =>
    get<AntiDilutionPreview>(
      `/entities/${eid}/security-classes/${classId}/anti-dilution?new_price=${encodeURIComponent(newPrice)}&new_shares=${encodeURIComponent(newShares)}`
    ),
  createTransfer: (eid: string, b: unknown) => post(`/entities/${eid}/transfers`, b),
  createConversion: (eid: string, b: unknown) => post(`/entities/${eid}/conversions`, b),
  createCorporateAction: (eid: string, b: unknown) =>
    post(`/entities/${eid}/corporate-actions`, b),
  listRightsIssues: (eid: string) => get<RightsIssue[]>(`/entities/${eid}/rights-issues`),
  createRightsIssue: (eid: string, b: unknown) => post<RightsIssue>(`/entities/${eid}/rights-issues`, b),
  rightsEntitlements: (rid: string) =>
    get<{ rights_issue_id: string; status: string; entitlements: Entitlement[] }>(
      `/rights-issues/${rid}/entitlements`
    ),
  subscribeRights: (rid: string, b: unknown) => post(`/rights-issues/${rid}/subscriptions`, b),
  closeRights: (rid: string) =>
    post<{ issued_shares: number; amount_raised: string }>(`/rights-issues/${rid}/close`),
  waterfall: (eid: string, exitAmount: string) =>
    get<WaterfallResult>(`/entities/${eid}/waterfall?exit_amount=${encodeURIComponent(exitAmount)}`),

  listDefinitions: () => get<WorkflowDefinition[]>("/workflow-definitions"),
  listRuns: (eid: string) => get<WorkflowRun[]>(`/entities/${eid}/workflows`),
  startRun: (eid: string, b: { definition_key: string; context?: object }) =>
    post<WorkflowRun>(`/entities/${eid}/workflows`, b),
  getRun: (rid: string) => get<WorkflowRun>(`/workflows/${rid}`),
  completeStep: (rid: string, stepKey: string, output: object) =>
    post<WorkflowRun>(`/workflows/${rid}/steps/${stepKey}/complete`, { output }),

  listTemplates: () => get<DocTemplate[]>("/document-templates"),
  listDocuments: (eid: string) => get<Document[]>(`/entities/${eid}/documents`),
  createDocument: (eid: string, b: unknown) => post<Document>(`/entities/${eid}/documents`, b),
  getDocument: (did: string) => get<Document>(`/documents/${did}`),
  requestSignature: (did: string, b: unknown) =>
    post<SignatureRequest>(`/documents/${did}/signatures`, b),
  completeSignature: (sid: string) => post<SignatureRequest>(`/signatures/${sid}/complete`),

  listDataRooms: (eid: string) => get<DataRoom[]>(`/entities/${eid}/data-rooms`),
  createDataRoom: (eid: string, b: { name: string; scope?: string }) =>
    post<DataRoom>(`/entities/${eid}/data-rooms`, b),
  getDataRoom: (id: string) => get<DataRoom>(`/data-rooms/${id}`),
  addDataRoomItem: (id: string, b: { document_id: string; folder?: string }) =>
    post<DataRoom>(`/data-rooms/${id}/items`, b),
  addGrant: (id: string, b: { email: string }) => post<DataRoom>(`/data-rooms/${id}/grants`, b),
  viewItem: (id: string, itemId: string) =>
    post<Document>(`/data-rooms/${id}/items/${itemId}/view`),
  engagement: (id: string) => get<Engagement[]>(`/data-rooms/${id}/engagement`),

  listCompliance: (eid: string, asOf?: string) =>
    get<Obligation[]>(`/entities/${eid}/compliance${asOf ? `?as_of=${asOf}` : ""}`),
  generateCompliance: (eid: string, b: { financial_year_end: string }) =>
    post<Obligation[]>(`/entities/${eid}/compliance/generate`, b),
  updateObligation: (id: string, b: { status: string; srn?: string }) =>
    post<Obligation>(`/compliance/${id}/status`, b),
  generatePeriodicCompliance: (eid: string, b: { financial_year_end: string }) =>
    post<Obligation[]>(`/entities/${eid}/compliance/generate-periodic`, b),
  complianceHealth: (eid: string) =>
    get<{ total: number; filed: number; overdue: number; open: number; score: number }>(
      `/entities/${eid}/compliance/health`
    ),

  getFund: (eid: string) => get<Fund>(`/entities/${eid}/fund`),
  createFund: (eid: string, b: unknown) => post<Fund>(`/entities/${eid}/fund`, b),
  listLPs: (fid: string) => get<LP[]>(`/funds/${fid}/lps`),
  addLP: (fid: string, b: unknown) => post<LP>(`/funds/${fid}/lps`, b),
  listCalls: (fid: string) => get<CapitalCall[]>(`/funds/${fid}/capital-calls`),
  createCall: (fid: string, b: unknown) => post<CapitalCall>(`/funds/${fid}/capital-calls`, b),
  payNotice: (fid: string, nid: string) =>
    post<DrawdownNotice>(`/funds/${fid}/drawdown-notices/${nid}/pay`),
  listDistributions: (fid: string) => get<Distribution[]>(`/funds/${fid}/distributions`),
  distribute: (fid: string, b: unknown) => post<Distribution>(`/funds/${fid}/distributions`, b),
  capitalAccounts: (fid: string) => get<CapitalAccounts>(`/funds/${fid}/capital-accounts`),
  fundPlan: (fid: string) => get<FundPlan>(`/funds/${fid}/plan`),
  saveFundPlan: (fid: string, b: FundPlanInput) => put<FundPlan>(`/funds/${fid}/plan`, b),
  listPortfolio: (fid: string) => get<PortfolioInvestment[]>(`/funds/${fid}/portfolio`),
  portfolioMonitoring: (fid: string) =>
    get<PortfolioMonitoring>(`/funds/${fid}/portfolio-monitoring`),
  addPortfolioKpi: (fid: string, iid: string, b: PortfolioKPIInput) =>
    post<PortfolioKPI[]>(`/funds/${fid}/portfolio/${iid}/kpis`, b),
  listPortfolioKpis: (fid: string, iid: string) =>
    get<PortfolioKPI[]>(`/funds/${fid}/portfolio/${iid}/kpis`),
  addInvestment: (fid: string, b: unknown) =>
    post<PortfolioInvestment>(`/funds/${fid}/portfolio`, b),
  markInvestment: (fid: string, iid: string, b: unknown) =>
    put<PortfolioInvestment>(`/funds/${fid}/portfolio/${iid}/mark`, b),
  scheduleOfInvestments: (fid: string) =>
    get<ScheduleOfInvestments>(`/funds/${fid}/soi`),
  soiReport: (fid: string) => post<Document>(`/funds/${fid}/soi/report`),
  fundPerformance: (fid: string) => get<FundPerformance>(`/funds/${fid}/performance`),
  fundFinancials: (fid: string) => get<FundFinancials>(`/funds/${fid}/financials`),
  fundFinancialsReport: (fid: string) => post<Document>(`/funds/${fid}/financials/report`),
  valuationSummary: (fid: string) => get<ValuationSummary>(`/funds/${fid}/valuations`),
  setValuationPolicy: (fid: string, b: { valuer_name: string | null; valuation_frequency_months: number }) =>
    put<Fund>(`/funds/${fid}/valuation-policy`, b),
  recordValuation: (fid: string, iid: string, b: PortfolioValuationInput) =>
    post<PortfolioValuation[]>(`/funds/${fid}/portfolio/${iid}/valuations`, b),
  listPortfolioValuations: (fid: string, iid: string) =>
    get<PortfolioValuation[]>(`/funds/${fid}/portfolio/${iid}/valuations`),
  valuationReport: (fid: string) => post<Document>(`/funds/${fid}/valuations/report`),
  fundraiseSummary: (fid: string) => get<FundraiseSummary>(`/funds/${fid}/fundraise`),
  addLpProspect: (fid: string, b: Partial<LPProspect>) =>
    post<FundraiseSummary>(`/funds/${fid}/prospects`, b),
  setLpProspectStage: (fid: string, pid: string, stage: string) =>
    post<FundraiseSummary>(`/funds/${fid}/prospects/${pid}/stage`, { stage }),
  convertLpProspect: (fid: string, pid: string, commitment: string | null) =>
    post<LP>(`/funds/${fid}/prospects/${pid}/convert`, { commitment }),
  lpStatement: (fid: string, lpId: string) =>
    post<Document>(`/funds/${fid}/lps/${lpId}/statement`),
  requestConsents: (rid: string) =>
    post<{ requested: number; total: number }>(`/resolutions/${rid}/consents`),
  listConsents: (rid: string) => get<ConsentTally>(`/resolutions/${rid}/consents`),
  decideConsent: (cid: string, approve: boolean) =>
    post<{ id: string; status: string }>(`/portal/consents/${cid}`, { approve }),
  requestSale: (b: unknown) =>
    post<{ id: string; status: string }>(`/portal/secondary-requests`, b),
  listSecondaryRequests: (eid: string) =>
    get<SecondaryRequestRow[]>(`/entities/${eid}/secondary-requests`),
  decideSecondary: (rid: string, b: unknown) =>
    post<{ id: string; status: string; transfer_id?: string }>(
      `/secondary-requests/${rid}/decide`, b
    ),
  taxStatements: (fid: string, fyEnd: string) =>
    post<{ form_64c: number; form_64d: number; total_distributed: string }>(
      `/funds/${fid}/tax-statements`,
      { financial_year_end: fyEnd }
    ),
  chargeFees: (fid: string) =>
    post<{ charged: string; charges: { lp_id: string; amount: string }[] }>(
      `/funds/${fid}/fees/charge`
    ),
  listDeals: (fid: string) => get<Deal[]>(`/funds/${fid}/deals`),
  createDeal: (fid: string, b: unknown) => post<Deal>(`/funds/${fid}/deals`, b),
  setDealStage: (did: string, stage: string) => post<Deal>(`/deals/${did}/stage`, { stage }),
  investDeal: (did: string, b: unknown) => post<Deal>(`/deals/${did}/invest`, b),
  dealCrm: (did: string) => get<DealCrm>(`/deals/${did}/crm`),
  addDealContact: (did: string, b: { name: string; role?: string | null; email?: string | null; note?: string | null }) =>
    post<DealCrm>(`/deals/${did}/contacts`, b),
  addDealActivity: (did: string, b: { kind: string; body: string; occurred_on?: string | null }) =>
    post<DealCrm>(`/deals/${did}/activities`, b),
  generateAifCompliance: (eid: string, b: { financial_year_end: string }) =>
    post<Obligation[]>(`/entities/${eid}/compliance/generate-aif`, b),

  listSchemes: (eid: string) => get<EsopScheme[]>(`/entities/${eid}/esop/schemes`),
  createScheme: (eid: string, b: { name: string; pool_size: number }) =>
    post<EsopScheme>(`/entities/${eid}/esop/schemes`, b),
  listGrants: (eid: string) => get<EsopGrant[]>(`/entities/${eid}/esop/grants`),
  createGrant: (eid: string, b: unknown) => post<EsopGrant>(`/entities/${eid}/esop/grants`, b),
  exerciseGrant: (gid: string, b: unknown) =>
    post(`/esop/grants/${gid}/exercise`, b),
  listExerciseWindows: (eid: string) =>
    get<ExerciseWindow[]>(`/entities/${eid}/exercise-windows`),
  createExerciseWindow: (eid: string, b: unknown) =>
    post<ExerciseWindow>(`/entities/${eid}/exercise-windows`, b),

  listLiquidityEvents: (eid: string) =>
    get<LiquidityEvent[]>(`/entities/${eid}/liquidity-events`),
  createLiquidityEvent: (eid: string, b: unknown) =>
    post<LiquidityEvent>(`/entities/${eid}/liquidity-events`, b),
  settleLiquidityEvent: (eid: string, evId: string) =>
    post<{ tenders_settled: number; shares_bought_back: number; total_paid: string }>(
      `/entities/${eid}/liquidity-events/${evId}/settle`
    ),
  tenderShares: (b: unknown) => post<{ id: string; status: string; quantity: number }>("/portal/tenders", b),

  esopOverview: (eid: string) => get<EsopOverview>(`/entities/${eid}/esop/overview`),
  esopExpense: (eid: string, p: { volatility: number; risk_free: number; expected_life: number }) =>
    get<EsopExpense>(
      `/entities/${eid}/esop/expense?volatility=${p.volatility}&risk_free=${p.risk_free}&expected_life=${p.expected_life}`
    ),
  esopExpenseReport: (eid: string, b: unknown) =>
    post<Document>(`/entities/${eid}/esop/expense-report`, b),
  schemePack: (eid: string, schemeId: string) =>
    post<Document[]>(`/entities/${eid}/esop/schemes/${schemeId}/pack`),
  investorReportPreview: (eid: string) =>
    get<InvestorMetrics>(`/entities/${eid}/investor-report/preview`),
  createInvestorReport: (eid: string, b: unknown) =>
    post<Document>(`/entities/${eid}/investor-reports`, b),

  listAdvisorAccess: (eid: string) =>
    get<AdvisorAccess[]>(`/entities/${eid}/advisor-access`),
  grantAdvisorAccess: (eid: string, b: unknown) =>
    post<AdvisorAccess>(`/entities/${eid}/advisor-access`, b),
  revokeAdvisorAccess: (eid: string, id: string) =>
    del(`/entities/${eid}/advisor-access/${id}`),
  advisorEntities: () => get<AdvisorEntity[]>("/advisor/entities"),

  listValuations: (eid: string) => get<Valuation[]>(`/entities/${eid}/valuations`),
  createValuation: (eid: string, b: unknown) => post<Valuation>(`/entities/${eid}/valuations`, b),
  currentValuation: (eid: string) => get<CurrentFmv>(`/entities/${eid}/valuations/current`),
  scorecardFactors: (eid: string) =>
    get<{ factors: ScorecardFactor[] }>(
      `/entities/${eid}/valuation-estimates/scorecard-factors`
    ),
  valuationSmartfill: (eid: string, growthPct: number, years: number) =>
    get<Smartfill>(
      `/entities/${eid}/valuation-estimates/smartfill?growth_pct=${growthPct}&years=${years}`
    ),
  listValuationEstimates: (eid: string) =>
    get<ValuationEstimate[]>(`/entities/${eid}/valuation-estimates`),
  createValuationEstimate: (eid: string, b: unknown) =>
    post<ValuationEstimate>(`/entities/${eid}/valuation-estimates`, b),
  valuationEstimateReport: (eid: string, id: string) =>
    post<Document>(`/entities/${eid}/valuation-estimates/${id}/report`),

  listProviders: (category?: string) =>
    get<Provider[]>(`/service-providers${category ? `?category=${category}` : ""}`),
  registerProvider: (b: unknown) => post<Provider>("/service-providers", b),
  listEngagements: (eid: string) => get<ServiceEngagement[]>(`/entities/${eid}/engagements`),
  createEngagement: (eid: string, b: unknown) =>
    post<ServiceEngagement>(`/entities/${eid}/engagements`, b),
  updateEngagement: (id: string, b: { status: string }) =>
    post<ServiceEngagement>(`/engagements/${id}/status`, b),

  getSubscription: (eid: string) =>
    get<AdminSubscription>(`/entities/${eid}/admin-subscription`),
  subscribe: (eid: string, b: { tier: string }) =>
    post<AdminSubscription>(`/entities/${eid}/admin-subscription`, b),
  addTouchpoint: (sid: string, b: unknown) =>
    post<Touchpoint>(`/admin-subscriptions/${sid}/touchpoints`, b),
  scheduleAudit: (sid: string, b: unknown) =>
    post<AuditEngagement>(`/admin-subscriptions/${sid}/audits`, b),
  updateAudit: (sid: string, aid: string, b: { status: string }) =>
    post<AuditEngagement>(`/admin-subscriptions/${sid}/audits/${aid}/status`, b),

  getSPV: (eid: string) => get<SPV>(`/entities/${eid}/spv`),
  createSPV: (eid: string, b: unknown) => post<SPV>(`/entities/${eid}/spv`, b),
  listCoInvestors: (sid: string) => get<CoInvestor[]>(`/spvs/${sid}/co-investors`),
  addCoInvestor: (sid: string, b: unknown) => post<CoInvestor>(`/spvs/${sid}/co-investors`, b),
  contributeCoInvestor: (sid: string, cid: string) =>
    post<CoInvestor>(`/spvs/${sid}/co-investors/${cid}/contribute`),
  spvSummary: (sid: string) => get<SPVSummary>(`/spvs/${sid}/summary`),
  setSPVTerms: (sid: string, b: unknown) => post<SPV>(`/spvs/${sid}/terms`, b),
  commitToSPV: (b: unknown) => post<{ id: string; status: string; commitment: string }>("/portal/spv-commitments", b),
  spvInvest: (sid: string, b: unknown) => post(`/spvs/${sid}/invest`, b),

  listRounds: (eid: string) => get<Round[]>(`/entities/${eid}/rounds`),
  createRound: (eid: string, b: unknown) => post<Round>(`/entities/${eid}/rounds`, b),
  listCommitments: (rid: string) => get<RoundCommitment[]>(`/rounds/${rid}/commitments`),
  addCommitment: (rid: string, b: unknown) =>
    post<RoundCommitment>(`/rounds/${rid}/commitments`, b),
  updateCommitment: (rid: string, cid: string, b: { status: string }) =>
    post<RoundCommitment>(`/rounds/${rid}/commitments/${cid}/status`, b),
  roundSummary: (rid: string) => get<RoundSummary>(`/rounds/${rid}/summary`),
  generateTermSheet: (rid: string) => post<Document>(`/rounds/${rid}/term-sheet`),
  generateOfferLetter: (rid: string, cid: string) =>
    post<Document>(`/rounds/${rid}/commitments/${cid}/offer-letter`),
  getDiligence: (eid: string) => get<DiligenceResult>(`/entities/${eid}/diligence`),
  generateDiligenceReport: (eid: string) => post<Document>(`/entities/${eid}/diligence/report`),
  createFunnelLink: (eid: string, rid: string, b: unknown) =>
    post<FunnelLink>(`/entities/${eid}/rounds/${rid}/funnel-link`, b),
  deactivateFunnelLink: (eid: string, rid: string) =>
    post<FunnelLink>(`/entities/${eid}/rounds/${rid}/funnel-link/deactivate`),
  getFunnel: (eid: string, rid: string) => get<FunnelView>(`/entities/${eid}/rounds/${rid}/funnel`),
  publicFunnel: (token: string) => get<PublicFunnelInfo>(`/public/funnel/${token}`),
  publicFunnelInterest: (token: string, b: unknown) =>
    post<{ status: string; data_room_granted: boolean }>(`/public/funnel/${token}/interest`, b),
  charterAmendment: (eid: string, b: unknown) =>
    post<{ resolution_id: string; document_id: string; status: string }>(
      `/entities/${eid}/charter-amendments`, b
    ),
  offboardMember: (mid: string, b: unknown) =>
    post<{ member_id: string; lapsed_options: number; grants_affected: number }>(
      `/team/${mid}/offboard`, b
    ),
  scanTermSheet: (eid: string, text: string) =>
    post<TermSheetScan>(`/entities/${eid}/termsheet/scan`, { text }),
  instrumentsExecution: (eid: string) =>
    get<Record<string, InstrumentExecution>>(`/entities/${eid}/instruments/execution`),
  generateInstrumentAgreement: (iid: string) =>
    post<Document>(`/instruments/${iid}/agreement`),
  requestInstrumentBoardApproval: (iid: string) =>
    post<Resolution>(`/instruments/${iid}/board-approval`),
  closeRound: (rid: string) =>
    post<{ issued: number; instruments_converted: number; foreign_investors: boolean }>(
      `/rounds/${rid}/close`
    ),

  listMeetings: (eid: string) => get<Meeting[]>(`/entities/${eid}/meetings`),
  createMeeting: (eid: string, b: unknown) => post<Meeting>(`/entities/${eid}/meetings`, b),
  recordMinutes: (mid: string, b: unknown) => post<Meeting>(`/meetings/${mid}/minutes`, b),
  listResolutions: (eid: string) => get<Resolution[]>(`/entities/${eid}/resolutions`),
  createResolution: (eid: string, b: unknown) =>
    post<Resolution>(`/entities/${eid}/resolutions`, b),
  setResolutionStatus: (rid: string, b: { status: string }) =>
    post<Resolution>(`/resolutions/${rid}/status`, b),
  generateResolutionDoc: (rid: string) => post<Document>(`/resolutions/${rid}/document`),
  addAgendaItem: (mid: string, b: unknown) => post<Meeting>(`/meetings/${mid}/agenda`, b),
  generateNotice: (mid: string) => post<Document>(`/meetings/${mid}/notice`),
  listDirectors: (eid: string) => get<Director[]>(`/entities/${eid}/directors`),
  appointDirector: (eid: string, b: unknown) => post<Director>(`/entities/${eid}/directors`, b),
  resignDirector: (did: string, b: unknown) => post<Director>(`/directors/${did}/resign`, b),
  indemnifyDirector: (did: string) => post<Document>(`/directors/${did}/indemnification`),

  auditLog: () => get<AuditEntry[]>("/audit-log"),
  notifications: (unreadOnly = false) =>
    get<AppNotification[]>(`/notifications${unreadOnly ? "?unread_only=true" : ""}`),
  markAllNotificationsRead: () => post<{ ok: boolean }>("/notifications/read-all"),

  dashboard: (eid: string) => get<Dashboard>(`/entities/${eid}/dashboard`),
  entityTasks: (eid: string) => get<EntityTasks>(`/entities/${eid}/tasks`),
  captableTimeline: (eid: string) =>
    get<{ events: TimelineEvent[] }>(`/entities/${eid}/timeline`),
  portalValueHistory: () => get<ValueHistory>("/portal/value-history"),
  ackNotice: (nid: string) =>
    post<{ notice_id: string; acknowledged_at: string }>(`/portal/notices/${nid}/ack`),
  grantDetail: (grantId: string) => get<GrantDetail>(`/portal/grants/${grantId}/detail`),
  files: (eid: string, q?: string) =>
    get<FileItem[]>(`/entities/${eid}/files${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  listTaxRecords: (eid: string) => get<TaxRecord[]>(`/entities/${eid}/tax-records`),
  addTaxRecord: (eid: string, b: unknown) => post<TaxRecord>(`/entities/${eid}/tax-records`, b),

  listTeam: (eid: string) => get<TeamMember[]>(`/entities/${eid}/team`),
  addTeamMember: (eid: string, b: unknown) => post<TeamMember>(`/entities/${eid}/team`, b),
  onboardMember: (mid: string) =>
    post<{ stakeholder_id: string; documents: string[] }>(`/team/${mid}/onboard`),

  listCounterparties: (eid: string) => get<Counterparty[]>(`/entities/${eid}/counterparties`),
  addCounterparty: (eid: string, b: unknown) =>
    post<Counterparty>(`/entities/${eid}/counterparties`, b),
  listContracts: (eid: string) => get<Contract[]>(`/entities/${eid}/contracts`),
  addContract: (eid: string, b: unknown) => post<Contract>(`/entities/${eid}/contracts`, b),
  updateContractStatus: (cid: string, b: { status: string }) =>
    post<Contract>(`/contracts/${cid}/status`, b),
  generateContractDoc: (cid: string, template_key: string) =>
    post<Document>(`/contracts/${cid}/document`, { template_key }),

  listInvestorAccess: (eid: string) => get<InvestorAccess[]>(`/entities/${eid}/investor-access`),
  grantInvestorAccess: (eid: string, b: unknown) =>
    post<InvestorAccess>(`/entities/${eid}/investor-access`, b),
  listInvestorUpdates: (eid: string) => get<InvestorUpdate[]>(`/entities/${eid}/investor-updates`),
  publishInvestorUpdate: (eid: string, b: unknown) =>
    post<InvestorUpdate>(`/entities/${eid}/investor-updates`, b),
  portal: () => get<PortalDashboard>("/portal"),

  listPipeline: (eid: string) => get<Prospect[]>(`/entities/${eid}/investor-pipeline`),
  addProspect: (eid: string, b: unknown) => post<Prospect>(`/entities/${eid}/investor-pipeline`, b),
  pipelineSummary: (eid: string) =>
    get<{ by_stage: Record<string, { count: number; value: string }>; open_value: string; committed_value: string; total: number }>(
      `/entities/${eid}/investor-pipeline/summary`
    ),
  updateProspectStage: (pid: string, b: { stage: string }) =>
    post<Prospect>(`/pipeline/${pid}/stage`, b),
  convertProspect: (pid: string) =>
    post<{ commitment_id: string; round_id: string }>(`/pipeline/${pid}/convert`),

  startupEligibility: (eid: string) => get<Eligibility>(`/entities/${eid}/startup/eligibility`),
  getRecognition: (eid: string) => get<Recognition>(`/entities/${eid}/startup/recognition`),
  upsertRecognition: (eid: string, b: unknown) =>
    put<Recognition>(`/entities/${eid}/startup/recognition`, b),
  listBenefits: (eid: string) => get<Benefit[]>(`/entities/${eid}/startup/benefits`),
  applyBenefit: (eid: string, b: unknown) => post<Benefit>(`/entities/${eid}/startup/benefits`, b),
  updateBenefitStatus: (bid: string, b: unknown) =>
    post<Benefit>(`/startup-benefits/${bid}/status`, b),

  addSnapshot: (eid: string, b: unknown) => post(`/entities/${eid}/finance/snapshots`, b),
  runway: (eid: string) => get<Runway>(`/entities/${eid}/finance/runway`),

  listSBO: (eid: string) => get<SBO[]>(`/entities/${eid}/sbo`),
  addSBO: (eid: string, b: unknown) => post<SBO>(`/entities/${eid}/sbo`, b),
  listCharges: (eid: string) => get<Charge[]>(`/entities/${eid}/charges`),
  addCharge: (eid: string, b: unknown) => post<Charge>(`/entities/${eid}/charges`, b),
  satisfyCharge: (cid: string) => post<Charge>(`/charges/${cid}/satisfy`),
  listRegistrations: (eid: string) => get<Registration[]>(`/entities/${eid}/registrations`),
  addRegistration: (eid: string, b: unknown) => post<Registration>(`/entities/${eid}/registrations`, b),

  alerts: (withinDays = 30) => get<Alert[]>(`/alerts?within_days=${withinDays}`),
  sweepAlerts: () => post<{ notifications_created: number }>("/alerts/sweep"),

  listInstruments: (eid: string) => get<Instrument[]>(`/entities/${eid}/instruments`),
  createInstrument: (eid: string, b: unknown) => post<Instrument>(`/entities/${eid}/instruments`, b),
  convertInstrument: (id: string, b: unknown) =>
    post<{ converted_shares: number; conversion_price: string }>(`/instruments/${id}/convert`, b),
  listDemat: (eid: string) => get<DematRec[]>(`/entities/${eid}/demat`),
  addDemat: (eid: string, b: unknown) => post<DematRec>(`/entities/${eid}/demat`, b),

  downloadCapTableCsv: (eid: string) => downloadFile(`/entities/${eid}/cap-table.csv`, "cap-table.csv"),
  downloadComplianceCsv: (eid: string) => downloadFile(`/entities/${eid}/compliance.csv`, "compliance.csv"),
  downloadDocumentPdf: (docId: string, title: string) =>
    downloadFile(`/documents/${docId}/pdf`, `${title.replace(/[^\w -]/g, "-")}.pdf`),
  downloadPortalDocPdf: (docId: string, title: string) =>
    downloadFile(`/portal/documents/${docId}/pdf`, `${title.replace(/[^\w -]/g, "-")}.pdf`),
  importCapTable: (eid: string, csv: string, apply: boolean) =>
    post<CapTableImportReport>(`/entities/${eid}/cap-table/import`, { csv, apply }),
  downloadImportTemplate: (eid: string) =>
    downloadFile(`/entities/${eid}/cap-table/import-template`, "cap-table-import.csv"),

  listFounderVesting: (eid: string) => get<FounderVesting[]>(`/entities/${eid}/founder-vesting`),
  createFounderVesting: (eid: string, b: unknown) =>
    post<FounderVesting>(`/entities/${eid}/founder-vesting`, b),
  repurchaseUnvested: (id: string) =>
    post<{ repurchased_shares: number }>(`/founder-vesting/${id}/repurchase-unvested`),

  listQuestions: (rid: string) => get<DataRoomQuestion[]>(`/data-rooms/${rid}/questions`),
  askQuestion: (rid: string, b: unknown) => post<DataRoomQuestion>(`/data-rooms/${rid}/questions`, b),
  answerQuestion: (qid: string, b: unknown) =>
    post<DataRoomQuestion>(`/data-room-questions/${qid}/answer`, b),
};
