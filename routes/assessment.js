// routes/assessment.js
// Powers the "Start Assessment" flow end to end:
//   1. POST /api/assessment/start   -> creates a session, returns the question set
//   2. POST /api/assessment/submit  -> scores answers, stores + returns full results
//   3. GET  /api/assessment/:id     -> retrieve a previously computed result

const express = require('express');
const { nanoid } = require('nanoid');
const db = require('../db');
const { getCategories, scoreAssessment } = require('../questions');

const router = express.Router();

// POST /api/assessment/start — begin a new assessment session
router.post('/start', async (req, res) => {
  const session = {
    id: nanoid(12),
    approach: (req.body && req.body.approach) || 'self-assessment',
    status: 'in_progress',
    createdAt: new Date().toISOString(),
  };

  await db.insert('sessions', session);

  res.status(201).json({
    ok: true,
    sessionId: session.id,
    categories: getCategories(),
  });
});

// POST /api/assessment/submit — submit answers for scoring
router.post('/submit', async (req, res) => {
  const { sessionId, answers } = req.body || {};

  if (!sessionId) {
    return res.status(400).json({ ok: false, errors: ['sessionId is required.'] });
  }
  if (!answers || typeof answers !== 'object') {
    return res.status(400).json({ ok: false, errors: ['answers object is required.'] });
  }

  const session = await db.findById('sessions', sessionId);
  if (!session) {
    return res.status(404).json({ ok: false, errors: ['Session not found. Please start a new assessment.'] });
  }

  const categories = getCategories();
  const missing = categories
    .map((c) => c.id)
    .filter((id) => !(id in answers));

  if (missing.length) {
    return res.status(400).json({
      ok: false,
      errors: [`Missing answers for: ${missing.join(', ')}`],
    });
  }

  const result = scoreAssessment(answers);

  const record = {
    id: nanoid(12),
    sessionId,
    approach: session.approach,
    answers,
    result,
    createdAt: new Date().toISOString(),
  };

  await db.insert('results', record);
  await db.updateById('sessions', sessionId, { status: 'completed' });

  res.status(201).json({ ok: true, resultId: record.id, result });
});

// GET /api/assessment/:id — retrieve a stored result by its id
router.get('/:id', async (req, res) => {
  const record = await db.findById('results', req.params.id);
  if (!record) {
    return res.status(404).json({ ok: false, errors: ['Result not found.'] });
  }
  res.json({ ok: true, ...record });
});

module.exports = router;
