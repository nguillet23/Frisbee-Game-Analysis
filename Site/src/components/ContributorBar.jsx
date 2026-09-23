// Hand-rolled contribution bar — no charting library dependency (this
// project generally hand-rolls over adding a compiled/heavy dependency
// where a simple version suffices, e.g. EDA's from-scratch k-means).
export default function ContributorBar({ feature, value, maxAbs }) {
  const pct = maxAbs > 0 ? (Math.abs(value) / maxAbs) * 100 : 0;
  const positive = value >= 0;
  return (
    <div className="contrib-row">
      <span className="contrib-label">{formatFeatureName(feature)}</span>
      <div className="contrib-track">
        <div
          className={`contrib-fill ${positive ? "contrib-positive" : "contrib-negative"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="contrib-value">{value > 0 ? `+${value}` : value}</span>
    </div>
  );
}

function formatFeatureName(feature) {
  return feature
    .replace(/_/g, " ")
    .replace(/\blast3\b/, "(last 3 games)")
    .replace(/\bseason to date\b/, "(season to date)")
    .replace(/^archetype (.+)/, "role: $1");
}
