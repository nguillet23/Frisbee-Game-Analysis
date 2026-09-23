const TIER_CLASS = {
  Elite: "tier-elite",
  "Above Average": "tier-above",
  Average: "tier-average",
  "Below Average": "tier-below",
  Limited: "tier-limited",
};

export default function GradeBadge({ grade, tier }) {
  const cls = TIER_CLASS[tier] ?? "tier-average";
  return (
    <span className={`grade-badge ${cls}`} title={`${tier} (role-relative percentile)`}>
      {grade}
    </span>
  );
}
