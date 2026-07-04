// questions.js
// Question bank + scoring engine for the assessment.
// Each category mirrors the 8 rows of the comparison table on the site.
// Each question is answered on a 1-5 scale, matching the 5 maturity levels.

const CATEGORIES = [
  {
    id: 'documentation',
    label: 'Process Documentation',
    question: 'How would you describe your process documentation today?',
    options: [
      { value: 1, label: 'Informal, inconsistent, scattered across teams' },
      { value: 2, label: 'Some documentation exists but is out of date' },
      { value: 3, label: 'Standardized templates used across most processes' },
      { value: 4, label: 'Centralized, version-controlled, regularly reviewed' },
      { value: 5, label: 'Living documentation, automatically kept current' },
    ],
  },
  {
    id: 'quality_compliance',
    label: 'Quality & Compliance',
    question: 'How does your organization handle quality and compliance?',
    options: [
      { value: 1, label: 'Reactive — issues addressed only after they occur' },
      { value: 2, label: 'Basic checks exist but are inconsistently applied' },
      { value: 3, label: 'Defined controls with regular audits' },
      { value: 4, label: 'Proactive monitoring with fast issue detection' },
      { value: 5, label: 'Continuously monitored, self-correcting controls' },
    ],
  },
  {
    id: 'metrics',
    label: 'Performance Metrics',
    question: 'How mature is your performance measurement?',
    options: [
      { value: 1, label: 'Little to no visibility into performance' },
      { value: 2, label: 'Manual tracking of a few basic metrics' },
      { value: 3, label: 'Defined KPIs tracked on a regular cadence' },
      { value: 4, label: 'Dashboards with near real-time visibility' },
      { value: 5, label: 'Predictive analytics driving proactive decisions' },
    ],
  },
  {
    id: 'decision_making',
    label: 'Decision Making',
    question: 'How are operational decisions typically made?',
    options: [
      { value: 1, label: 'Intuition-based, inconsistent criteria' },
      { value: 2, label: 'Some data used, but mostly ad hoc' },
      { value: 3, label: 'Defined criteria and data used consistently' },
      { value: 4, label: 'Evidence-based with clear accountability' },
      { value: 5, label: 'Fully data-driven, transparent, and optimized' },
    ],
  },
  {
    id: 'risk_management',
    label: 'Risk Management',
    question: 'How does your organization manage risk?',
    options: [
      { value: 1, label: 'Ad hoc, reactive to incidents as they occur' },
      { value: 2, label: 'Basic risk log maintained but rarely reviewed' },
      { value: 3, label: 'Defined risk process with regular reviews' },
      { value: 4, label: 'Proactive identification and mitigation planning' },
      { value: 5, label: 'Systematic, predictive, embedded in daily operations' },
    ],
  },
  {
    id: 'resource_allocation',
    label: 'Resource Allocation',
    question: 'How are resources planned and allocated?',
    options: [
      { value: 1, label: 'Firefighting — mostly unplanned effort' },
      { value: 2, label: 'Basic planning, frequently disrupted' },
      { value: 3, label: 'Planned allocation aligned to priorities' },
      { value: 4, label: 'Capacity-based planning with clear tradeoffs' },
      { value: 5, label: 'Optimized allocation using predictive models' },
    ],
  },
  {
    id: 'employee_capability',
    label: 'Employee Capability',
    question: 'How consistent are employee skills and training?',
    options: [
      { value: 1, label: 'Inconsistent, mostly on-the-job learning' },
      { value: 2, label: 'Some training exists but is not standardized' },
      { value: 3, label: 'Defined training paths for key roles' },
      { value: 4, label: 'Standardized, competency-based development' },
      { value: 5, label: 'Continuous upskilling tied to strategic needs' },
    ],
  },
  {
    id: 'innovation',
    label: 'Innovation',
    question: 'How does innovation happen in your organization?',
    options: [
      { value: 1, label: 'Limited, sporadic, mostly bottom-up' },
      { value: 2, label: 'Occasional initiatives, no formal process' },
      { value: 3, label: 'Defined process for evaluating new ideas' },
      { value: 4, label: 'Regular pilots with structured rollout' },
      { value: 5, label: 'Embedded in culture, continuous and systematic' },
    ],
  },
];

const MATURITY_LEVELS = [
  {
    level: 1,
    name: 'Initial / Ad Hoc',
    description:
      'Processes are unpredictable, poorly controlled, and reactive. Success depends on individual heroics.',
  },
  {
    level: 2,
    name: 'Repeatable / Managed',
    description:
      'Some processes are established with basic discipline. Requirements are captured and tracked.',
  },
  {
    level: 3,
    name: 'Defined / Standardized',
    description:
      'Processes are documented, standardized, and proactively managed across the organization.',
  },
  {
    level: 4,
    name: 'Quantitatively Managed',
    description:
      'Processes are measured and controlled quantitatively. Variation is understood and managed.',
  },
  {
    level: 5,
    name: 'Optimizing',
    description:
      'Focus on continuous improvement and innovation. The organization proactively optimizes its processes.',
  },
];

function getCategories() {
  // Public shape sent to the frontend (no scoring internals needed beyond this).
  return CATEGORIES.map(({ id, label, question, options }) => ({
    id,
    label,
    question,
    options,
  }));
}

function levelForScore(avgScore) {
  const rounded = Math.min(5, Math.max(1, Math.round(avgScore)));
  return MATURITY_LEVELS.find((l) => l.level === rounded);
}

/**
 * answers: { [categoryId]: number (1-5) }
 * Returns a full scoring + gap analysis result.
 */
function scoreAssessment(answers) {
  const perCategory = CATEGORIES.map((cat) => {
    const score = Number(answers[cat.id]);
    const safeScore = Number.isFinite(score) && score >= 1 && score <= 5 ? score : 1;
    return {
      id: cat.id,
      label: cat.label,
      score: safeScore,
      targetScore: 5,
      gap: 5 - safeScore,
    };
  });

  const total = perCategory.reduce((sum, c) => sum + c.score, 0);
  const avgScore = total / perCategory.length;
  const overallLevel = levelForScore(avgScore);

  const sortedByGap = [...perCategory].sort((a, b) => b.gap - a.gap);
  const topGaps = sortedByGap.filter((c) => c.gap > 0).slice(0, 3);

  const recommendations = topGaps.map((c) => ({
    category: c.label,
    gap: c.gap,
    recommendation: recommendationFor(c.id, c.score),
  }));

  return {
    overallScore: Math.round(avgScore * 100) / 100,
    overallLevel,
    categories: perCategory,
    topGaps,
    recommendations,
  };
}

function recommendationFor(categoryId, currentScore) {
  const nextLevel = Math.min(5, currentScore + 1);
  const templates = {
    documentation:
      'Centralize documentation in a single, version-controlled source of truth and assign clear ownership for keeping it current.',
    quality_compliance:
      'Introduce regular audits and move from reactive fixes to proactive quality controls with defined checkpoints.',
    metrics:
      'Define a small set of core KPIs and build a lightweight dashboard for consistent, near real-time visibility.',
    decision_making:
      'Establish clear, data-backed decision criteria and document the rationale behind key operational decisions.',
    risk_management:
      'Create a living risk register with scheduled reviews and assign owners for identified mitigation actions.',
    resource_allocation:
      'Move from reactive staffing to capacity-based planning tied to prioritized initiatives.',
    employee_capability:
      'Build standardized, competency-based training paths for critical roles instead of relying on informal onboarding.',
    innovation:
      'Formalize a lightweight process for evaluating and piloting new ideas so innovation isn\u2019t purely ad hoc.',
  };
  return (
    templates[categoryId] ||
    `Focus on moving this capability from its current level toward level ${nextLevel}.`
  );
}

module.exports = {
  CATEGORIES,
  MATURITY_LEVELS,
  getCategories,
  scoreAssessment,
};
