import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApiError,
  defaultRequest,
  fetchOverview,
  fetchPolicy,
  type CurvePoint,
  type OverviewRequest,
  type OverviewResponse,
  type PolicyResult,
  type SegmentRow,
} from "./api";

const pct = (value: number, digits = 2) => `${(value * 100).toFixed(digits)} pp`;

const ratio = (value: number | null, digits = 1) =>
  value === null ? "n/a" : `${(value * 100).toFixed(digits)}%`;

const money = (value: number) =>
  value.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });

const count = (value: number) => Math.round(value).toLocaleString("en-US");

const pValue = (value: number) => {
  if (!Number.isFinite(value)) return "n/a";
  if (value < 0.0001) return "<0.0001";
  return value.toFixed(4);
};

const policyLabel = (name: string) => {
  if (name === "uplift model") return "Model-targeted";
  if (name === "treat_all") return "Treat everyone";
  return "Random at this budget";
};

function QiniChart({ curve }: { curve: CurvePoint[] }) {
  const width = 820;
  const height = 360;
  const pad = { top: 26, right: 28, bottom: 52, left: 78 };
  const innerWidth = width - pad.left - pad.right;
  const innerHeight = height - pad.top - pad.bottom;
  const maxY = Math.max(...curve.map((point) => Math.max(point.model, point.random)), 0.0001);
  const x = (fraction: number) => pad.left + fraction * innerWidth;
  const y = (value: number) => pad.top + innerHeight - (value / maxY) * innerHeight;
  const line = (pick: (point: CurvePoint) => number) =>
    curve.map((point) => `${x(point.fraction).toFixed(2)},${y(pick(point)).toFixed(2)}`).join(" ");
  const ticks = [0, 0.25, 0.5, 0.75, 1];
  const yTicks = [0, 0.25, 0.5, 0.75, 1];

  return (
    <svg
      className="qini-chart"
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label="Cumulative incremental visits per thousand customers, model ranking versus random targeting"
    >
      {yTicks.map((tick) => (
        <g key={tick}>
          <line
            x1={pad.left}
            x2={width - pad.right}
            y1={y(maxY * tick)}
            y2={y(maxY * tick)}
            className="chart-grid"
          />
          <text x={pad.left - 12} y={y(maxY * tick) + 4} textAnchor="end" className="chart-tick">
            {(maxY * tick * 1000).toFixed(1)}
          </text>
        </g>
      ))}
      {ticks.map((tick) => (
        <g key={tick}>
          <line
            x1={x(tick)}
            x2={x(tick)}
            y1={pad.top}
            y2={height - pad.bottom}
            className="chart-grid"
          />
          <text
            x={x(tick)}
            y={height - pad.bottom + 22}
            textAnchor={tick === 0 ? "start" : tick === 1 ? "end" : "middle"}
            className="chart-tick"
          >
            {tick === 0 ? "0" : `${tick * 100}%`}
          </text>
        </g>
      ))}
      <line
        x1={x(0.1)}
        x2={x(0.1)}
        y1={pad.top}
        y2={height - pad.bottom}
        className="chart-marker"
      />
      <text x={x(0.1) + 8} y={pad.top + 14} className="chart-note">
        top decile
      </text>
      <polyline points={line((point) => point.random)} className="chart-random" />
      <polyline points={line((point) => point.model)} className="chart-model" />
      <text x={pad.left} y={18} className="chart-axis-title">
        incremental visits / 1,000 customers
      </text>
      <text
        x={width - pad.right}
        y={height - 10}
        textAnchor="end"
        className="chart-axis-title"
      >
        share of holdout ranked by predicted uplift
      </text>
    </svg>
  );
}

function SegmentTable({ rows }: { rows: SegmentRow[] }) {
  const ordered = [...rows].reverse();
  const max = Math.max(
    ...ordered.flatMap((row) => [row.predicted_uplift, row.observed_uplift ?? 0]),
    0.0001,
  );

  return (
    <div className="segment-table" role="table" aria-label="Observed uplift by predicted rank">
      <div className="segment-row segment-head" role="row">
        <span role="columnheader">Rank</span>
        <span role="columnheader">Customers</span>
        <span role="columnheader">Predicted</span>
        <span role="columnheader">Observed / 95% CI</span>
      </div>
      {ordered.map((row) => (
        <div className="segment-row" role="row" key={row.segment}>
          <span className="segment-rank" role="cell">
            {row.label}
          </span>
          <span role="cell" className="segment-n">
            {count(row.n)}
            <small>{ratio(row.treated_share, 0)} treated</small>
          </span>
          <span role="cell" className="segment-bar-cell">
            <span className="bar predicted" style={{ width: `${(row.predicted_uplift / max) * 100}%` }} />
            <b>{pct(row.predicted_uplift, 2)}</b>
          </span>
          <span role="cell" className="segment-bar-cell observed-cell">
            {row.observed_uplift === null ? (
              <span className="muted">not estimable</span>
            ) : (
              <>
                <span
                  className="bar observed"
                  style={{ width: `${((row.observed_uplift ?? 0) / max) * 100}%` }}
                />
                <b>{pct(row.observed_uplift, 2)}</b>
                <small>
                  [{pct(row.ci_low ?? 0, 2)}, {pct(row.ci_high ?? 0, 2)}]
                </small>
              </>
            )}
          </span>
        </div>
      ))}
    </div>
  );
}

function PolicyRows({ rows }: { rows: PolicyResult[] }) {
  return (
    <div className="policy-table" role="table" aria-label="Policy comparison">
      <div className="policy-row policy-head" role="row">
        <span role="columnheader">Policy</span>
        <span role="columnheader">Customers</span>
        <span role="columnheader">Incremental</span>
        <span role="columnheader">Profit</span>
      </div>
      {rows.map((row) => (
        <div
          className={`policy-row ${row.name === "uplift model" ? "is-model" : ""}`}
          role="row"
          key={row.name}
        >
          <span role="cell">
            <b>{policyLabel(row.name)}</b>
            <small>{ratio(row.budget_fraction, 0)} budget</small>
          </span>
          <span role="cell">{count(row.n_target)}</span>
          <span role="cell">{count(row.incremental_conversions)}</span>
          <span role="cell" className={row.profit < 0 ? "negative" : ""}>
            <b>{money(row.profit)}</b>
            <small>{row.ci_low === null ? "point estimate" : `CI ${money(row.ci_low)} to ${money(row.ci_high ?? 0)}`}</small>
          </span>
        </div>
      ))}
    </div>
  );
}

export default function App() {
  const [request, setRequest] = useState<OverviewRequest>(defaultRequest);
  const [data, setData] = useState<OverviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [policyLoading, setPolicyLoading] = useState(false);
  const [budget, setBudget] = useState(20);
  const [value, setValue] = useState(2);
  const [cost, setCost] = useState(0.05);
  const sequence = useRef(0);

  const load = useCallback(async (next: OverviewRequest) => {
    const ticket = ++sequence.current;
    setLoading(true);
    setError(null);
    try {
      const payload = await fetchOverview(next);
      if (ticket !== sequence.current) return;
      setData(payload);
      setBudget(Math.round(payload.uplift.policy.budget_fraction * 100));
    } catch (cause) {
      if (ticket !== sequence.current) return;
      setError(cause instanceof ApiError ? cause.message : "Could not load the experiment.");
    } finally {
      if (ticket === sequence.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(defaultRequest);
  }, [load]);

  const reprice = useCallback(
    async (nextBudget: number, nextValue: number, nextCost: number) => {
      setPolicyLoading(true);
      setError(null);
      try {
        const result = await fetchPolicy({
          ...request,
          budget_fraction: nextBudget / 100,
          value_per_conversion: nextValue,
          cost_per_contact: nextCost,
        });
        setData((current) =>
          current
            ? {
                ...current,
                uplift: {
                  ...current.uplift,
                  policy: result.policy,
                  baselines: result.baselines,
                },
              }
            : current,
        );
      } catch (cause) {
        setError(cause instanceof ApiError ? cause.message : "Could not re-price the policy.");
      } finally {
        setPolicyLoading(false);
      }
    },
    [request],
  );

  const changeOutcome = (outcome: string) => {
    const next = { ...request, outcome };
    setRequest(next);
    void load(next);
  };

  const applyBudget = () => {
    void reprice(budget, value, cost);
  };

  const readout = data?.readout;
  const uplift = data?.uplift;
  const maxSmd = Math.max(
    ...(readout?.balance ?? []).map((row) => Math.abs(row.smd ?? 0)),
    0,
  );
  const rows = uplift ? [uplift.policy, ...uplift.baselines] : [];

  return (
    <div className="page">
      <a className="skip" href="#main">
        Skip to content
      </a>
      <header className="masthead">
        <div className="wordmark">
          upliftlab <span>/ 02</span>
        </div>
        <div className="masthead-note">Causal incrementality, not attribution</div>
        <div className="status">
          <span className="status-dot" aria-hidden="true" />
          holdout locked
        </div>
      </header>

      <main id="main">
        <section className="hero">
          <div className="hero-copy">
            <p className="eyebrow">Experiment readout / uplift policy</p>
            <h1>
              Who responds,
              <br />
              <em>and what is it worth?</em>
            </h1>
            <p className="lede">
              A randomized e-mail experiment read backwards: first the average effect, then a
              customer-level ranking, then the budget decision. Every number comes from one
              reproducible run, and every estimate keeps its interval.
            </p>
            <div className="hero-meta">
              <span>Hillstrom / 64,000 customers</span>
              <span>Seed 42</span>
              <span>{readout ? `${readout.bootstrap.toLocaleString()} bootstrap draws` : "Loading"}</span>
            </div>
          </div>
          <aside className="hero-ledger" aria-label="Headline results">
            <div className="ledger-line">
              <span>Holdout ATE</span>
              <strong>{readout ? `+${pct(readout.ate.estimate)}` : "—"}</strong>
            </div>
            <div className="ledger-line">
              <span>Confidence interval</span>
              <strong>
                {readout
                  ? `[${pct(readout.ate.ci_low)}, ${pct(readout.ate.ci_high)}]`
                  : "—"}
              </strong>
            </div>
            <div className="ledger-line">
              <span>Sample ratio</span>
              <strong>{readout ? `p = ${pValue(readout.srm.p_value)}` : "—"}</strong>
            </div>
            <div className="ledger-line">
              <span>Qini vs random</span>
              <strong>{uplift ? uplift.metrics.qini?.toFixed(3) ?? "n/a" : "—"}</strong>
            </div>
            <div className="ledger-line">
              <span>Policy profit at {budget}%</span>
              <strong className="signal">
                {uplift ? money(uplift.policy.profit) : "—"}
              </strong>
            </div>
            <p className="ledger-foot">
              Holdout ATE is the average for everyone. The policy value is the part a budget can
              actually buy.
            </p>
          </aside>
        </section>

        {error && (
          <section className="error-panel" role="alert">
            <div>
              <p className="eyebrow">Run failed</p>
              <h2>{error}</h2>
              <p>
                The API keeps the dataset cache and the fitted model separate. Retry the readout,
                or check the service log.
              </p>
            </div>
            <button type="button" className="button" onClick={() => void load(request)}>
              Retry
            </button>
          </section>
        )}

        {loading && !data && (
          <section className="loading" aria-live="polite">
            <span className="loading-line" />
            <p>Fitting the readout and the uplift model. The holdout is untouched until the end.</p>
          </section>
        )}

        {data && readout && uplift && (
          <>
            <section className="section readout-section" aria-labelledby="readout-title">
              <header className="section-head">
                <span className="section-index">01 / READOUT</span>
                <div>
                  <h2 id="readout-title">The experiment is clean. The average is large.</h2>
                  <p>
                    The e-mail assignment passes the sample-ratio check. The intent-to-treat effect
                    is measured on the full randomized sample, not on opened or clicked messages.
                  </p>
                </div>
                <label className="select-wrap">
                  <span>Outcome</span>
                  <select
                    value={request.outcome}
                    onChange={(event) => changeOutcome(event.target.value)}
                  >
                    <option value="visit">Visit</option>
                    <option value="conversion">Conversion</option>
                  </select>
                </label>
              </header>

              <div className="metric-grid">
                <article className="metric">
                  <span>Average treatment effect</span>
                  <strong>+{pct(readout.ate.estimate)}</strong>
                  <small>
                    {pct(readout.ate.ci_low)} to {pct(readout.ate.ci_high)} at{" "}
                    {Math.round((1 - readout.alpha) * 100)}%
                  </small>
                </article>
                <article className="metric">
                  <span>Welch p-value</span>
                  <strong>{pValue(readout.ate.p_value)}</strong>
                  <small>{count(readout.ate.n_treated)} treated / {count(readout.ate.n_control)} control</small>
                </article>
                <article className="metric">
                  <span>Largest imbalance</span>
                  <strong>{maxSmd.toFixed(3)}</strong>
                  <small>Absolute standardized mean difference</small>
                </article>
                <article className="metric">
                  <span>CUPED variance reduction</span>
                  <strong>{ratio(readout.cuped.variance_reduction)}</strong>
                  <small>r = {readout.cuped.correlation.toFixed(3)} with `history`</small>
                </article>
              </div>
              <p className="fine-print">
                SRM p = {pValue(readout.srm.p_value)}. The treated arm is a 1:1 mixture of Mens and
                Womens e-mail. CUPED is a sensitivity check here; its 20% target is not met because
                pre-period spend barely correlates with visit. That miss is reported, not hidden.
              </p>
            </section>

            <section className="section chart-section" aria-labelledby="ranking-title">
              <header className="section-head">
                <span className="section-index">02 / RANKING</span>
                <div>
                  <h2 id="ranking-title">The model ranks, but the ranking is weak.</h2>
                  <p>
                    The curve below sorts the holdout by predicted uplift. A useful ranking should
                    stay above the random diagonal, then flatten as the persuadable customers run
                    out. This one sits close to random: Qini {uplift.metrics.qini?.toFixed(3) ?? "n/a"}.
                  </p>
                </div>
                <div className="chart-key" aria-label="Chart legend">
                  <span><i className="key-model" /> model ranking</span>
                  <span><i className="key-random" /> random targeting</span>
                </div>
              </header>
              <div className="chart-frame">
                <QiniChart curve={uplift.curve} />
              </div>
              <div className="chart-summary">
                <div>
                  <span>Top-decile uplift</span>
                  <strong>{pct(uplift.metrics.uplift_top_decile)}</strong>
                </div>
                <div>
                  <span>Share of incremental visits in top decile</span>
                  <strong>{ratio(uplift.metrics.top_decile_share)}</strong>
                </div>
                <div>
                  <span>AUUC</span>
                  <strong>{uplift.metrics.auuc.toFixed(4)}</strong>
                </div>
                <div>
                  <span>Model</span>
                  <strong>{uplift.selected_candidate}</strong>
                </div>
              </div>
            </section>

            <section className="section policy-section" aria-labelledby="policy-title">
              <header className="section-head">
                <span className="section-index">03 / POLICY</span>
                <div>
                  <h2 id="policy-title">A budget turns a ranking into a decision.</h2>
                  <p>
                    Target the highest predicted uplift first. The profit below uses observed
                    holdout outcomes, the stated value per {request.outcome}, and the contact cost.
                    It is an estimate with a bootstrap interval, not a promise.
                  </p>
                </div>
              </header>

              <div className="policy-grid">
                <div className="policy-controls">
                  <div className="control">
                    <label htmlFor="budget">
                      Contact budget <b>{budget}%</b>
                    </label>
                    <input
                      id="budget"
                      type="range"
                      min="5"
                      max="100"
                      step="5"
                      value={budget}
                      onChange={(event) => setBudget(Number(event.target.value))}
                      onPointerUp={applyBudget}
                      onKeyUp={(event) => {
                        if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
                          applyBudget();
                        }
                      }}
                    />
                    <div className="range-labels">
                      <span>5%</span>
                      <span>100%</span>
                    </div>
                  </div>
                  <div className="control-pair">
                    <div className="control">
                      <label htmlFor="value">Value per {request.outcome}</label>
                      <input
                        id="value"
                        type="number"
                        min="0"
                        step="0.5"
                        value={value}
                        onChange={(event) => setValue(Number(event.target.value))}
                      />
                    </div>
                    <div className="control">
                      <label htmlFor="cost">Cost per contact</label>
                      <input
                        id="cost"
                        type="number"
                        min="0"
                        step="0.01"
                        value={cost}
                        onChange={(event) => setCost(Number(event.target.value))}
                      />
                    </div>
                  </div>
                  <button type="button" className="button" onClick={applyBudget} disabled={policyLoading}>
                    {policyLoading ? "Re-pricing…" : "Re-price policy"}
                  </button>
                  <p className="control-note">
                    The model is cached. Changing the budget re-prices the holdout without refitting.
                  </p>
                </div>

                <div className="policy-result" aria-live="polite">
                  <p className="eyebrow">Estimated profit / {budget}% budget</p>
                  <p className={`profit ${uplift.policy.profit < 0 ? "negative" : ""}`}>
                    {money(uplift.policy.profit)}
                  </p>
                  <p className="profit-ci">
                    {uplift.policy.ci_low === null
                      ? "Point estimate only"
                      : `${money(uplift.policy.ci_low)} to ${money(uplift.policy.ci_high ?? 0)} at 95%`}
                  </p>
                  <div className="policy-facts">
                    <div>
                      <span>Customers</span>
                      <strong>{count(uplift.policy.n_target)}</strong>
                    </div>
                    <div>
                      <span>Incremental visits</span>
                      <strong>{count(uplift.policy.incremental_conversions)}</strong>
                    </div>
                    <div>
                      <span>ROI</span>
                      <strong>{ratio(uplift.policy.roi)}</strong>
                    </div>
                  </div>
                </div>
              </div>

              <PolicyRows rows={rows} />
              <p className="fine-print">
                Random and treat-everyone are point estimates. The model interval conditions on the
                selected customers and resamples outcomes within arm; it does not include model
                selection uncertainty.
              </p>
            </section>

            <section className="section segments-section" aria-labelledby="segments-title">
              <header className="section-head">
                <span className="section-index">04 / CALIBRATION</span>
                <div>
                  <h2 id="segments-title">The ranking does not become monotone on holdout.</h2>
                  <p>
                    Customers are split into equal predicted-uplift buckets. The top bucket is
                    predicted to respond more, but the observed curve is uneven. That is the main
                    negative finding in this run, and it belongs in the readout.
                  </p>
                </div>
              </header>
              <SegmentTable rows={uplift.segments} />
              <p className="fine-print">
                Observed uplift is a Welch difference in means inside each bucket. Buckets are rank
                summaries, not individual treatment effects.
              </p>
            </section>

            <section className="section caveats-section" aria-labelledby="caveats-title">
              <header className="section-head">
                <span className="section-index">05 / LIMITS</span>
                <div>
                  <h2 id="caveats-title">What this run does not prove.</h2>
                  <p>The caveats are generated from the same result object as the tables.</p>
                </div>
              </header>
              <ul className="caveat-list">
                {uplift.caveats.map((caveat) => (
                  <li key={caveat}>{caveat}</li>
                ))}
              </ul>
            </section>
          </>
        )}
      </main>

      <footer className="footer">
        <span>upliftlab / Phase 2 vertical slice</span>
        <span>Code MIT · Hillstrom data not redistributed</span>
        <span>FastAPI + React + scikit-learn</span>
      </footer>
    </div>
  );
}
