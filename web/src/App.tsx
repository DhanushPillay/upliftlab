import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ApiError,
  defaultRequest,
  fetchOverview,
  type CurvePoint,
  type OverviewRequest,
  type OverviewResponse,
  type PolicyResult,
  type SegmentRow,
} from "./api";

type BudgetMode = "fraction" | "dollars";
type DiagnosticsTab = "balance" | "readout" | "caveats";

const money = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const integer = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

const DIAGNOSTIC_TABS = [
  ["balance", "Balance"],
  ["readout", "Readout"],
  ["caveats", "Caveats"],
] as const;

function formatCount(value: number | null | undefined): string {
  return value == null ? "n/a" : integer.format(Math.round(value));
}

function formatMoney(value: number | null | undefined): string {
  return value == null || !Number.isFinite(value) ? "n/a" : money.format(value);
}

function formatCompactMoney(value: number): string {
  if (Math.abs(value) >= 1000) {
    return `${value < 0 ? "-" : ""}$${(Math.abs(value) / 1000).toFixed(1)}k`;
  }
  return `${value < 0 ? "-" : ""}$${Math.round(Math.abs(value))}`;
}

function formatPercent(value: number | null | undefined, digits = 1): string {
  return value == null || !Number.isFinite(value) ? "n/a" : `${(value * 100).toFixed(digits)}%`;
}

function formatPp(value: number, digits = 2): string {
  return `${(value * 100).toFixed(digits)} pp`;
}

function formatPpRange(low: number, high: number): string {
  return `${(low * 100).toFixed(2)} to ${(high * 100).toFixed(2)} pp`;
}

function signedPp(value: number, digits = 2): string {
  return `${value >= 0 ? "+" : ""}${(value * 100).toFixed(digits)} pp`;
}

function policyLabel(name: string): string {
  if (name === "uplift model") return "Model-targeted";
  if (name === "treat_all") return "Treat everyone";
  if (name === "random") return "Random at this budget";
  return name;
}

function signatureOf(
  mode: BudgetMode,
  budget: number,
  dollars: number,
  value: number,
  cost: number,
): string {
  return [mode, budget, dollars, value, cost].join("|");
}

function nearestBudgetIndex(points: PolicyResult[], fraction: number): number {
  let best = 0;
  let distance = Number.POSITIVE_INFINITY;
  points.forEach((point, index) => {
    const next = Math.abs(point.budget_fraction - fraction);
    if (next < distance) {
      distance = next;
      best = index;
    }
  });
  return best;
}

function useElementWidth<T extends HTMLElement>(initial: number) {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(initial);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const observer = new ResizeObserver((entries) => {
      const next = entries[0]?.contentRect.width;
      if (next && next > 0) setWidth(Math.round(next));
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return [ref, width] as const;
}

function chartHeight(width: number): number {
  return Math.round(Math.max(220, Math.min(320, width * 0.52)));
}

function QiniChart({ curve }: { curve: CurvePoint[] }) {
  const [frame, width] = useElementWidth<HTMLDivElement>(680);
  const height = chartHeight(width);
  const pad = { left: 54, right: 18, top: 18, bottom: 38 };
  const plotWidth = width - pad.left - pad.right;
  const plotHeight = height - pad.top - pad.bottom;

  const values = curve.flatMap((point) => [point.model * 1000, point.random * 1000, 0]);
  const rawMin = Math.min(...values);
  const rawMax = Math.max(...values);
  const spread = rawMax - rawMin || 1;
  const yMin = Math.min(0, rawMin);
  const yMax = rawMax + spread * 0.08;

  const x = (fraction: number) => pad.left + fraction * plotWidth;
  const y = (value: number) => pad.top + ((yMax - value) / (yMax - yMin)) * plotHeight;

  const buildPath = (key: "model" | "random") =>
    curve
      .map((point, index) => {
        const command = index === 0 ? "M" : "L";
        return `${command}${x(point.fraction).toFixed(2)},${y(point[key] * 1000).toFixed(2)}`;
      })
      .join(" ");

  const yTicks = Array.from({ length: 5 }, (_, index) => yMin + ((yMax - yMin) * index) / 4);
  const xTicks = [0, 0.25, 0.5, 0.75, 1];

  if (curve.length === 0) {
    return <div className="empty-state">No ranking curve returned.</div>;
  }

  return (
    <div className="chart-body" ref={frame}>
      <svg
        className="chart-svg"
        width="100%"
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="Cumulative incremental visits per thousand customers, model ranking against random ranking"
      >
        <title>Cumulative uplift curve</title>
        {yTicks.map((tick) => (
          <g key={`y-${tick}`}>
            <line
              className="chart-gridline"
              x1={pad.left}
              x2={width - pad.right}
              y1={y(tick)}
              y2={y(tick)}
            />
            <text className="chart-tick" x={pad.left - 10} y={y(tick) + 3} textAnchor="end">
              {tick.toFixed(1)}
            </text>
          </g>
        ))}
        {xTicks.map((tick) => (
          <g key={`x-${tick}`}>
            <line
              className="chart-gridline"
              x1={x(tick)}
              x2={x(tick)}
              y1={pad.top}
              y2={height - pad.bottom}
            />
            <text
              className="chart-tick"
              x={x(tick)}
              y={height - pad.bottom + 18}
              textAnchor="middle"
            >
              {Math.round(tick * 100)}%
            </text>
          </g>
        ))}
        <line
          className="chart-zero"
          x1={pad.left}
          x2={width - pad.right}
          y1={y(0)}
          y2={y(0)}
        />
        <line
          className="chart-decile"
          x1={x(0.1)}
          x2={x(0.1)}
          y1={pad.top}
          y2={height - pad.bottom}
        />
        <text className="chart-marker" x={x(0.1) + 6} y={pad.top + 11}>
          top decile
        </text>
        <path className="chart-random" d={buildPath("random")} />
        <path className="chart-model" d={buildPath("model")} />
        <text className="chart-axis-title" x={pad.left} y={12}>
          incremental visits / 1,000 customers
        </text>
        <text
          className="chart-axis-title"
          x={width - pad.right}
          y={height - 4}
          textAnchor="end"
        >
          share of holdout ranked
        </text>
      </svg>
    </div>
  );
}

function ProfitChart({
  points,
  activeFraction,
}: {
  points: PolicyResult[];
  activeFraction: number;
}) {
  const [frame, width] = useElementWidth<HTMLDivElement>(680);
  const height = chartHeight(width);
  const pad = { left: 62, right: 18, top: 22, bottom: 38 };
  const plotWidth = width - pad.left - pad.right;
  const plotHeight = height - pad.top - pad.bottom;

  const [activeIndex, setActiveIndex] = useState(0);
  const currentIndex = useMemo(
    () => nearestBudgetIndex(points, activeFraction),
    [points, activeFraction],
  );

  useEffect(() => {
    setActiveIndex(currentIndex);
  }, [currentIndex]);

  const profits = points.map((point) => point.profit);
  const rawMax = Math.max(0, ...profits);
  const rawMin = Math.min(0, ...profits);
  const spread = rawMax - rawMin || 1;
  const yMax = rawMax + spread * 0.12;
  const yMin = Math.min(0, rawMin);

  const x = (fraction: number) => pad.left + fraction * plotWidth;
  const y = (value: number) => pad.top + ((yMax - value) / (yMax - yMin)) * plotHeight;

  const linePath = points
    .map((point, index) => {
      const command = index === 0 ? "M" : "L";
      return `${command}${x(point.budget_fraction).toFixed(2)},${y(point.profit).toFixed(2)}`;
    })
    .join(" ");

  const areaPath =
    points.length > 0
      ? `M${x(points[0].budget_fraction).toFixed(2)},${y(0).toFixed(2)} ${points
          .map((point) => `L${x(point.budget_fraction).toFixed(2)},${y(point.profit).toFixed(2)}`)
          .join(" ")} L${x(points[points.length - 1].budget_fraction).toFixed(2)},${y(0).toFixed(2)} Z`
      : "";

  const yTicks = Array.from({ length: 5 }, (_, index) => yMin + ((yMax - yMin) * index) / 4);
  const xTicks = [0.25, 0.5, 0.75, 1];
  const active = points[Math.min(activeIndex, points.length - 1)];

  const updateFromPointer = (event: React.PointerEvent<SVGSVGElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const viewX = ((event.clientX - rect.left) / rect.width) * width;
    const fraction = Math.min(1, Math.max(0, (viewX - pad.left) / plotWidth));
    setActiveIndex(nearestBudgetIndex(points, fraction));
  };

  if (points.length === 0) {
    return <div className="empty-state">No profit curve returned.</div>;
  }

  return (
    <div className="profit-chart">
      <div className="chart-readout">
        <div>
          <span>Budget</span>
          <strong>{formatPercent(active.budget_fraction, 0)}</strong>
        </div>
        <div>
          <span>Contacts</span>
          <strong>{formatCount(active.n_target)}</strong>
        </div>
        <div>
          <span>Profit</span>
          <strong className="accent">{formatMoney(active.profit)}</strong>
        </div>
        <div>
          <span>ROI</span>
          <strong className={active.roi != null && active.roi < 0 ? "negative" : undefined}>
            {formatPercent(active.roi)}
          </strong>
        </div>
      </div>
      <div className="chart-body" ref={frame}>
        <svg
          className="chart-svg is-interactive"
          width="100%"
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          tabIndex={0}
          aria-label="Profit by holdout budget share. Use left and right arrow keys to inspect points."
          onPointerMove={updateFromPointer}
          onPointerLeave={() => setActiveIndex(currentIndex)}
          onKeyDown={(event) => {
            if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
              event.preventDefault();
              const delta = event.key === "ArrowRight" ? 1 : -1;
              setActiveIndex((index) =>
                Math.min(points.length - 1, Math.max(0, index + delta)),
              );
            }
            if (event.key === "Home") {
              event.preventDefault();
              setActiveIndex(0);
            }
            if (event.key === "End") {
              event.preventDefault();
              setActiveIndex(points.length - 1);
            }
          }}
        >
          <title>Profit versus budget</title>
          {yTicks.map((tick) => (
            <g key={`y-${tick}`}>
              <line
                className="chart-gridline"
                x1={pad.left}
                x2={width - pad.right}
                y1={y(tick)}
                y2={y(tick)}
              />
              <text className="chart-tick" x={pad.left - 10} y={y(tick) + 3} textAnchor="end">
                {formatCompactMoney(tick)}
              </text>
            </g>
          ))}
          {xTicks.map((tick) => (
            <g key={`x-${tick}`}>
              <line
                className="chart-gridline"
                x1={x(tick)}
                x2={x(tick)}
                y1={pad.top}
                y2={height - pad.bottom}
              />
              <text
                className="chart-tick"
                x={x(tick)}
                y={height - pad.bottom + 18}
                textAnchor="middle"
              >
                {Math.round(tick * 100)}%
              </text>
            </g>
          ))}
          <line
            className="chart-zero"
            x1={pad.left}
            x2={width - pad.right}
            y1={y(0)}
            y2={y(0)}
          />
          <path className="chart-area" d={areaPath} />
          <path className="chart-model" d={linePath} />
          <line
            className="chart-cursor"
            x1={x(active.budget_fraction)}
            x2={x(active.budget_fraction)}
            y1={pad.top}
            y2={height - pad.bottom}
          />
          <circle
            className="chart-dot"
            cx={x(active.budget_fraction)}
            cy={y(active.profit)}
            r={4.5}
          />
          <text className="chart-axis-title" x={pad.left} y={11}>
            profit after contact cost
          </text>
          <text
            className="chart-axis-title"
            x={width - pad.right}
            y={height - 4}
            textAnchor="end"
          >
            share of holdout contacted
          </text>
        </svg>
      </div>
      <span className="sr-only" aria-live="polite">
        {formatPercent(active.budget_fraction, 0)} budget, {formatCount(active.n_target)}{" "}
        contacts, {formatMoney(active.profit)} profit
      </span>
    </div>
  );
}

function PolicyTable({ rows, budgetDollars }: { rows: PolicyResult[]; budgetDollars: number | null }) {
  return (
    <div className="table-wrap">
      <table className="policy-table">
        <thead>
          <tr>
            <th scope="col">Policy</th>
            <th scope="col">Budget</th>
            <th scope="col" className="col-contacts">
              Contacts
            </th>
            <th scope="col" className="col-incremental">
              Incremental
            </th>
            <th scope="col">Profit</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const isModel = row.name === "uplift model";
            return (
              <tr key={row.name} className={isModel ? "is-model" : undefined}>
                <th scope="row">
                  <span className="policy-name">{policyLabel(row.name)}</span>
                  {isModel ? <span className="tag">selected</span> : null}
                </th>
                <td>
                  <span className="mono">{formatPercent(row.budget_fraction, 0)}</span>
                  {isModel && budgetDollars != null ? (
                    <span className="cell-note">{formatMoney(budgetDollars)}</span>
                  ) : null}
                </td>
                <td className="col-contacts mono">{formatCount(row.n_target)}</td>
                <td className="col-incremental mono">
                  {row.incremental_conversions.toFixed(1)}
                </td>
                <td>
                  <span className={row.profit < 0 ? "money negative" : "money"}>
                    {formatMoney(row.profit)}
                  </span>
                  {row.ci_low != null && row.ci_high != null ? (
                    <span className="cell-note">
                      CI {formatMoney(row.ci_low)} to {formatMoney(row.ci_high)}
                    </span>
                  ) : (
                    <span className="cell-note">point estimate</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function SegmentTable({ rows }: { rows: SegmentRow[] }) {
  const maxValue = Math.max(
    ...rows.flatMap((row) => [row.predicted_uplift, row.observed_uplift ?? 0]),
    0.0001,
  );

  if (rows.length === 0) {
    return <div className="empty-state">No rank buckets returned.</div>;
  }

  return (
    <div className="table-wrap">
      <table className="segment-table">
        <thead>
          <tr>
            <th scope="col">Rank</th>
            <th scope="col">Predicted</th>
            <th scope="col">Observed</th>
            <th scope="col" className="col-ci">
              95% CI
            </th>
          </tr>
        </thead>
        <tbody>
          {[...rows].reverse().map((row) => (
            <tr key={row.segment}>
              <th scope="row">
                <span className="rank-label">{row.label}</span>
                <span className="cell-note">
                  {formatCount(row.n)} · {formatPercent(row.treated_share, 0)} treated
                </span>
              </th>
              <td>
                <div className="bar-cell">
                  <span
                    className="bar predicted"
                    style={{ width: `${Math.max(3, (row.predicted_uplift / maxValue) * 56)}px` }}
                  />
                  <span className="mono">{formatPp(row.predicted_uplift)}</span>
                </div>
              </td>
              <td>
                {row.observed_uplift == null ? (
                  <span className="muted">not estimable</span>
                ) : (
                  <div className="bar-cell">
                    <span
                      className="bar observed"
                      style={{
                        width: `${Math.max(3, (row.observed_uplift / maxValue) * 56)}px`,
                      }}
                    />
                    <span className="mono">{formatPp(row.observed_uplift)}</span>
                  </div>
                )}
              </td>
              <td className="col-ci mono">
                {row.ci_low == null || row.ci_high == null
                  ? "n/a"
                  : formatPpRange(row.ci_low, row.ci_high)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function BalanceTable({ balance }: { balance: OverviewResponse["readout"]["balance"] }) {
  const rows = [...balance].sort(
    (left, right) => Math.abs(right.smd ?? 0) - Math.abs(left.smd ?? 0),
  );

  if (rows.length === 0) {
    return <div className="empty-state">No covariates reported.</div>;
  }

  return (
    <div className="table-wrap">
      <table className="balance-table">
        <thead>
          <tr>
            <th scope="col">Covariate</th>
            <th scope="col">Treated mean</th>
            <th scope="col">Control mean</th>
            <th scope="col">SMD</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const smd = row.smd ?? 0;
            return (
              <tr key={row.covariate}>
                <th scope="row">{row.covariate}</th>
                <td className="mono">{row.treated_mean.toFixed(3)}</td>
                <td className="mono">{row.control_mean.toFixed(3)}</td>
                <td>
                  <div className="smd-cell">
                    <span className={Math.abs(smd) > 0.1 ? "smd-flag flagged" : "smd-flag"}>
                      {smd >= 0 ? "+" : ""}
                      {smd.toFixed(3)}
                    </span>
                    <span className="smd-track">
                      <span
                        className={smd < 0 ? "smd-bar negative" : "smd-bar"}
                        style={{ width: `${Math.min(100, Math.abs(smd) * 300)}%` }}
                      />
                    </span>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Skeleton() {
  return (
    <div className="skeleton" aria-hidden="true">
      <div className="skeleton-kpis">
        {Array.from({ length: 4 }, (_, index) => (
          <span key={index} className="skeleton-block" />
        ))}
      </div>
      <div className="skeleton-panels">
        <span className="skeleton-block" />
        <span className="skeleton-block" />
      </div>
    </div>
  );
}

function App() {
  const [request, setRequest] = useState<OverviewRequest>(defaultRequest);
  const [data, setData] = useState<OverviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [budgetMode, setBudgetMode] = useState<BudgetMode>("fraction");
  const [budget, setBudget] = useState(20);
  const [dollars, setDollars] = useState(128);
  const [value, setValue] = useState(2);
  const [cost, setCost] = useState(0.05);
  const [appliedSignature, setAppliedSignature] = useState<string | null>(null);
  const [appliedEconomics, setAppliedEconomics] = useState({ value: 2, cost: 0.05 });
  const [controlsOpen, setControlsOpen] = useState(false);
  const [tab, setTab] = useState<DiagnosticsTab>("balance");
  const sequence = useRef(0);

  const signature = useMemo(
    () => signatureOf(budgetMode, budget, dollars, value, cost),
    [budgetMode, budget, dollars, value, cost],
  );
  const dirty = appliedSignature === null || signature !== appliedSignature;

  const load = useCallback(async (next: OverviewRequest, nextSignature: string) => {
    const ticket = ++sequence.current;
    setLoading(true);
    setError(null);
    try {
      const payload = await fetchOverview(next);
      if (sequence.current !== ticket) return;
      setData(payload);
      setAppliedSignature(nextSignature);
      setAppliedEconomics({
        value: next.value_per_conversion,
        cost: next.cost_per_contact,
      });
      const policy = payload.uplift.policy;
      if (payload.uplift.budget_dollars != null) {
        setBudgetMode("dollars");
        setDollars(payload.uplift.budget_dollars);
      } else {
        setBudgetMode("fraction");
        setBudget(Math.max(5, Math.min(100, Math.round(policy.budget_fraction * 100))));
      }
    } catch (cause) {
      if (sequence.current !== ticket) return;
      setError(cause instanceof ApiError ? cause.message : "The API request failed.");
    } finally {
      if (sequence.current === ticket) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const initial = signatureOf("fraction", 20, 128, 2, 0.05);
    void load(defaultRequest, initial);
  }, [load]);

  const withBudget = useCallback(
    (base: OverviewRequest): OverviewRequest =>
      budgetMode === "fraction"
        ? { ...base, budget_fraction: budget / 100, budget_dollars: undefined }
        : { ...base, budget_fraction: undefined, budget_dollars: dollars },
    [budgetMode, budget, dollars],
  );

  const applyBudget = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (budgetMode === "dollars" && (!Number.isFinite(dollars) || dollars <= 0)) {
      setError("Enter a dollar budget greater than zero.");
      return;
    }
    if (budgetMode === "fraction" && (!Number.isFinite(budget) || budget <= 0 || budget > 100)) {
      setError("Enter a holdout share between 1 and 100%.");
      return;
    }
    if (!Number.isFinite(value) || value < 0) {
      setError("Value per conversion must be zero or positive.");
      return;
    }
    if (!Number.isFinite(cost) || cost < 0) {
      setError("Cost per contact must be zero or positive.");
      return;
    }
    if (budgetMode === "dollars" && cost <= 0) {
      setError("A dollar budget needs a positive cost per contact.");
      return;
    }
    void load(withBudget(request), signature);
  };

  const changeOutcome = (outcome: string) => {
    const next = { ...request, outcome };
    setRequest(next);
    void load(withBudget(next), signature);
  };

  const readout = data?.readout;
  const uplift = data?.uplift;
  const holdoutRows = uplift?.split.holdout ?? 0;
  const estimatedContacts =
    budgetMode === "fraction"
      ? Math.ceil((budget / 100) * holdoutRows)
      : cost > 0
        ? Math.ceil(dollars / cost)
        : 0;
  const policyRows = uplift ? [uplift.policy, ...uplift.baselines] : [];

  return (
    <div className="app">
      <a className="skip-link" href="#main">
        Skip to results
      </a>

      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            u
          </span>
          <span className="brand-name">upliftlab</span>
          <span className="brand-phase">T-learner</span>
        </div>
        <div className="topbar-context">
          <span className="chip">Hillstrom</span>
          <label className="outcome-control">
            <span>Outcome</span>
            <select
              id="outcome"
              name="outcome"
              value={request.outcome}
              onChange={(event) => changeOutcome(event.target.value)}
            >
              <option value="visit">Visit</option>
              <option value="conversion">Conversion</option>
            </select>
          </label>
          <span className="status">
            <span className="status-dot" aria-hidden="true" />
            holdout locked
          </span>
        </div>
      </header>

      <div className="shell">
        <aside className="rail">
          <button
            className="rail-toggle"
            type="button"
            aria-expanded={controlsOpen}
            onClick={() => setControlsOpen((open) => !open)}
          >
            Policy controls
            <span aria-hidden="true">{controlsOpen ? "−" : "+"}</span>
          </button>
          <div className={controlsOpen ? "rail-body is-open" : "rail-body"}>
            <div className="rail-heading">
              <span className="eyebrow">Budget</span>
              <h2>Price the contact list</h2>
            </div>
            <form onSubmit={applyBudget}>
              <fieldset className="mode-field">
                <legend className="field-label">Budget mode</legend>
                <div className="segmented">
                  <button
                    type="button"
                    aria-pressed={budgetMode === "fraction"}
                    onClick={() => setBudgetMode("fraction")}
                  >
                    Share
                  </button>
                  <button
                    type="button"
                    aria-pressed={budgetMode === "dollars"}
                    onClick={() => setBudgetMode("dollars")}
                  >
                    Dollars
                  </button>
                </div>
              </fieldset>

              {budgetMode === "fraction" ? (
                <label className="field">
                  <span className="field-label">
                    Holdout share <strong>{budget}%</strong>
                  </span>
                  <input
                    id="budget-share"
                    name="budget_share"
                    type="range"
                    min={5}
                    max={100}
                    step={5}
                    value={budget}
                    onChange={(event) => setBudget(Number(event.target.value))}
                  />
                  <span className="field-hint">
                    {formatCount(estimatedContacts)} contacts at the current holdout
                  </span>
                </label>
              ) : (
                <label className="field">
                  <span className="field-label">Campaign budget</span>
                  <span className="input-prefix">
                    <span aria-hidden="true">$</span>
                    <input
                      id="budget-dollars"
                      name="budget_dollars"
                      type="number"
                      min={1}
                      step={1}
                      inputMode="decimal"
                      value={dollars}
                      onChange={(event) => setDollars(Number(event.target.value))}
                    />
                  </span>
                  <span className="field-hint">
                    {formatCount(estimatedContacts)} contacts at {formatMoney(cost)} each
                  </span>
                </label>
              )}

              <label className="field">
                <span className="field-label">Value per conversion</span>
                <span className="input-prefix">
                  <span aria-hidden="true">$</span>
                  <input
                    id="value-per-conversion"
                    name="value_per_conversion"
                    type="number"
                    min={0}
                    step={0.25}
                    inputMode="decimal"
                    value={value}
                    onChange={(event) => setValue(Number(event.target.value))}
                  />
                </span>
              </label>

              <label className="field">
                <span className="field-label">Cost per contact</span>
                <span className="input-prefix">
                  <span aria-hidden="true">$</span>
                  <input
                    id="cost-per-contact"
                    name="cost_per_contact"
                    type="number"
                    min={0}
                    step={0.01}
                    inputMode="decimal"
                    value={cost}
                    onChange={(event) => setCost(Number(event.target.value))}
                  />
                </span>
              </label>

              <button className="apply" type="submit" disabled={loading || !dirty}>
                {loading ? "Re-pricing..." : dirty ? "Re-price policy" : "Policy up to date"}
              </button>
              {dirty && !loading ? (
                <p className="dirty-note">Changes are not applied yet.</p>
              ) : null}
              <p className="rail-note">
                Re-prices the cached holdout ranking. The model is not refit.
              </p>
            </form>
          </div>
        </aside>

        <main id="main" aria-busy={loading} className={loading && data ? "is-refreshing" : undefined}>
          {loading && data ? <div className="refresh-bar" aria-hidden="true" /> : null}

          {error ? (
            <div className="error-panel" role="alert">
              <div>
                <strong>Request failed</strong>
                <p>{error}</p>
              </div>
              <button type="button" onClick={() => void load(withBudget(request), signature)}>
                Retry
              </button>
            </div>
          ) : null}

          {!data && loading ? <Skeleton /> : null}

          {!data && !loading && !error ? (
            <div className="empty-state">No results returned. Adjust the controls and retry.</div>
          ) : null}

          {data && readout && uplift ? (
            <>
              <section className="page-head">
                <div>
                  <span className="eyebrow">Experiment readout / uplift policy</span>
                  <h1>Targeting console</h1>
                </div>
                <p>
                  Rank holdout customers by predicted uplift, then price the contact budget
                  against random and treat-all.
                </p>
              </section>

              <section className="kpis" aria-label="Headline results">
                <div className="kpi">
                  <span className="kpi-label">Holdout ATE</span>
                  <strong className="kpi-value">{signedPp(readout.ate.estimate)}</strong>
                  <span className="kpi-detail">
                    95% CI {formatPp(readout.ate.ci_low)} to {formatPp(readout.ate.ci_high)}
                  </span>
                </div>
                <div className="kpi">
                  <span className="kpi-label">Qini coefficient</span>
                  <strong className="kpi-value">
                    {uplift.metrics.qini == null ? "n/a" : uplift.metrics.qini.toFixed(3)}
                  </strong>
                  <span className="kpi-detail">
                    {uplift.metrics.qini != null && uplift.metrics.qini < 0.05
                      ? "near random ranking"
                      : "ranking vs random"}
                  </span>
                </div>
                <div className="kpi">
                  <span className="kpi-label">Policy profit</span>
                  <strong className="kpi-value">{formatMoney(uplift.policy.profit)}</strong>
                  <span className="kpi-detail">
                    {formatCount(uplift.policy.n_target)} contacts ·{" "}
                    {formatPercent(uplift.policy.budget_fraction, 0)} of holdout
                  </span>
                </div>
                <div className="kpi">
                  <span className="kpi-label">Policy ROI</span>
                  <strong className="kpi-value">{formatPercent(uplift.policy.roi)}</strong>
                  <span className="kpi-detail">
                    {formatMoney(appliedEconomics.value)} per conversion ·{" "}
                    {formatMoney(appliedEconomics.cost)} per contact
                  </span>
                </div>
              </section>

              <div className="chart-grid">
                <section className="panel">
                  <header className="panel-head">
                    <div>
                      <span className="eyebrow">Ranking quality</span>
                      <h2>Cumulative uplift</h2>
                    </div>
                    <div className="legend">
                      <span>
                        <i className="swatch model" /> model
                      </span>
                      <span>
                        <i className="swatch random" /> random
                      </span>
                    </div>
                  </header>
                  <div className="chart-frame">
                    <QiniChart curve={uplift.curve} />
                  </div>
                  <div className="panel-foot">
                    <span>
                      Top decile uplift <strong>{formatPp(uplift.metrics.uplift_top_decile)}</strong>
                    </span>
                    <span>
                      AUUC <strong>{uplift.metrics.auuc.toFixed(4)}</strong>
                    </span>
                    <span>
                      Candidate <strong>{uplift.selected_candidate}</strong>
                    </span>
                  </div>
                </section>

                <section className="panel">
                  <header className="panel-head">
                    <div>
                      <span className="eyebrow">Spend curve</span>
                      <h2>Profit by budget</h2>
                    </div>
                    <span className="panel-tag">holdout re-pricing</span>
                  </header>
                  <div className="chart-frame">
                    <ProfitChart points={uplift.profit_curve} activeFraction={uplift.policy.budget_fraction} />
                  </div>
                  <p className="panel-note">
                    Descriptive curve over the same ranking. Points are correlated, not
                    independent campaign estimates.
                  </p>
                </section>
              </div>

              <div className="decision-grid">
                <section className="panel">
                  <header className="panel-head">
                    <div>
                      <span className="eyebrow">Policy comparison</span>
                      <h2>Who to contact</h2>
                    </div>
                    <span className="panel-tag">
                      {uplift.budget_dollars != null
                        ? `${formatMoney(uplift.budget_dollars)} budget`
                        : `${formatPercent(uplift.policy.budget_fraction, 0)} budget`}
                    </span>
                  </header>
                  <PolicyTable rows={policyRows} budgetDollars={uplift.budget_dollars} />
                  <p className="panel-note">
                    Treat-all spends the full holdout, so it answers a different budget question.
                    The model interval conditions on the selected customers and excludes model
                    selection uncertainty.
                  </p>
                </section>

                <section className="panel">
                  <header className="panel-head">
                    <div>
                      <span className="eyebrow">Holdout check</span>
                      <h2>Observed by rank</h2>
                    </div>
                    <span className="panel-tag">{uplift.segments.length} rank buckets</span>
                  </header>
                  <SegmentTable rows={uplift.segments} />
                  <p className="panel-note">
                    Rank buckets, not causal strata. A flat or non-monotone curve means the model
                    did not separate persuadable customers.
                  </p>
                </section>
              </div>

              <section className="panel diagnostics">
                <header className="panel-head">
                  <div>
                    <span className="eyebrow">Diagnostics</span>
                    <h2>Readout detail</h2>
                  </div>
                  <div
                    className="tabs"
                    role="tablist"
                    aria-label="Diagnostics"
                    onKeyDown={(event) => {
                      const index = DIAGNOSTIC_TABS.findIndex(([id]) => id === tab);
                      const delta =
                        event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
                      if (delta === 0) return;
                      event.preventDefault();
                      const next =
                        DIAGNOSTIC_TABS[
                          (index + delta + DIAGNOSTIC_TABS.length) % DIAGNOSTIC_TABS.length
                        ];
                      setTab(next[0]);
                      document.getElementById(`tab-${next[0]}`)?.focus();
                    }}
                  >
                    {DIAGNOSTIC_TABS.map(([id, label]) => (
                      <button
                        key={id}
                        type="button"
                        role="tab"
                        id={`tab-${id}`}
                        aria-selected={tab === id}
                        aria-controls={`panel-${id}`}
                        tabIndex={tab === id ? 0 : -1}
                        onClick={() => setTab(id)}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </header>

                {tab === "balance" ? (
                  <div role="tabpanel" id="panel-balance" aria-labelledby="tab-balance" tabIndex={0}>
                    <BalanceTable balance={readout.balance} />
                    <p className="panel-note">
                      Standardized mean difference. Values above 0.1 are flagged, not adjusted
                      away.
                    </p>
                  </div>
                ) : null}

                {tab === "readout" ? (
                  <div
                    role="tabpanel"
                    id="panel-readout"
                    aria-labelledby="tab-readout"
                    className="definition-grid"
                    tabIndex={0}
                  >
                    <div>
                      <span>Estimator</span>
                      <strong>{readout.ate.method}</strong>
                    </div>
                    <div>
                      <span>Standard error</span>
                      <strong className="mono">{readout.ate.standard_error.toFixed(5)}</strong>
                    </div>
                    <div>
                      <span>Welch p-value</span>
                      <strong className="mono">
                        {readout.ate.p_value < 0.0001
                          ? "<0.0001"
                          : readout.ate.p_value.toFixed(4)}
                      </strong>
                    </div>
                    <div>
                      <span>Bootstrap CI</span>
                      <strong className="mono">
                        {formatPp(readout.bootstrap_result.ci_low)} to{" "}
                        {formatPp(readout.bootstrap_result.ci_high)}
                      </strong>
                    </div>
                    <div>
                      <span>Sample ratio p-value</span>
                      <strong className="mono">
                        {readout.srm.p_value < 0.0001
                          ? "<0.0001"
                          : readout.srm.p_value.toFixed(4)}
                      </strong>
                    </div>
                    <div>
                      <span>CUPED variance reduction</span>
                      <strong className="mono">
                        {formatPercent(readout.cuped.variance_reduction)}
                      </strong>
                    </div>
                    <div>
                      <span>Treated / control</span>
                      <strong className="mono">
                        {formatCount(readout.ate.n_treated)} / {formatCount(readout.ate.n_control)}
                      </strong>
                    </div>
                    <div>
                      <span>Holdout rows</span>
                      <strong className="mono">{formatCount(holdoutRows)}</strong>
                    </div>
                  </div>
                ) : null}

                {tab === "caveats" ? (
                  <div role="tabpanel" id="panel-caveats" aria-labelledby="tab-caveats" tabIndex={0}>
                    <ul className="caveat-list">
                      {uplift.caveats.map((caveat) => (
                        <li key={caveat}>{caveat}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </section>
            </>
          ) : null}
        </main>
      </div>

      <footer className="footer">
        <span>Code MIT</span>
        <span>Hillstrom data not redistributed</span>
        <span>FastAPI + React + scikit-learn</span>
      </footer>
    </div>
  );
}

export default App;
