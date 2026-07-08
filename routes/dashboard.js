// routes/dashboard.js
// Read-only aggregation endpoint powering the analytics dashboard (public/dashboard.html).

const express = require('express');
const db = require('../db');
const { CATEGORIES } = require('../questions');

const router = express.Router();

function dayKey(iso) {
  return iso.slice(0, 10); // YYYY-MM-DD
}

function lastNDays(n) {
  const days = [];
  const now = new Date();
  for (let i = n - 1; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    days.push(d.toISOString().slice(0, 10));
  }
  return days;
}

function countByDay(records, days) {
  const counts = Object.fromEntries(days.map((d) => [d, 0]));
  for (const r of records) {
    const key = dayKey(r.createdAt);
    if (key in counts) counts[key] += 1;
  }
  return days.map((d) => counts[d]);
}

function countBy(records, keyFn) {
  const map = {};
  for (const r of records) {
    const key = keyFn(r) || 'unknown';
    map[key] = (map[key] || 0) + 1;
  }
  return map;
}

// GET /api/dashboard/stats
router.get('/stats', async (req, res) => {
  const [leads, sessions, results] = await Promise.all([
    db.all('leads'),
    db.all('sessions'),
    db.all('results'),
  ]);

  const days = lastNDays(30);

  const avgOverallScore = results.length
    ? Math.round(
        (results.reduce((sum, r) => sum + (r.result?.overallScore || 0), 0) / results.length) * 100
      ) / 100
    : 0;

  const maturityLevelDistribution = [1, 2, 3, 4, 5].map((level) => ({
    level,
    count: results.filter((r) => r.result?.overallLevel?.level === level).length,
  }));

  const categoryAverages = CATEGORIES.map((cat) => {
    const scores = results
      .map((r) => r.result?.categories?.find((c) => c.id === cat.id)?.score)
      .filter((s) => Number.isFinite(s));
    const avg = scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : 0;
    return {
      id: cat.id,
      label: cat.label,
      avgScore: Math.round(avg * 100) / 100,
      avgGap: Math.round((5 - avg) * 100) / 100,
    };
  });

  const gapFrequency = {};
  for (const r of results) {
    for (const g of r.result?.topGaps || []) {
      gapFrequency[g.category] = (gapFrequency[g.category] || 0) + 1;
    }
  }
  const topGapsAggregate = Object.entries(gapFrequency)
    .map(([category, count]) => ({ category, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 8);

  const recentLeads = [...leads]
    .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt))
    .slice(0, 50)
    .map(({ id, name, email, company, message, source, createdAt }) => ({
      id,
      name,
      email,
      company,
      message,
      source,
      createdAt,
    }));

  res.json({
    ok: true,
    generatedAt: new Date().toISOString(),
    totals: {
      leads: leads.length,
      sessions: sessions.length,
      assessments: results.length,
      completionRate: sessions.length
        ? Math.round((results.length / sessions.length) * 1000) / 10
        : 0,
      avgOverallScore,
    },
    timeSeries: {
      days,
      leads: countByDay(leads, days),
      assessments: countByDay(results, days),
    },
    leadsByApproach: countBy(leads, (l) => l.source),
    maturityLevelDistribution,
    categoryAverages,
    topGapsAggregate,
    recentLeads,
  });
});

module.exports = router;
