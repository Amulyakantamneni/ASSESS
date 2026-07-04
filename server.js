// server.js
require('dotenv').config();

const path = require('path');
const express = require('express');
const cors = require('cors');
const rateLimit = require('express-rate-limit');

const leadsRouter = require('./routes/leads');
const assessmentRouter = require('./routes/assessment');

const app = express();
const PORT = process.env.PORT || 3000;

// --- Core middleware ---------------------------------------------------
app.use(cors());
app.use(express.json({ limit: '100kb' }));

// Basic abuse protection on the write-heavy API routes.
const apiLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100, // 100 requests per IP per window
  standardHeaders: true,
  legacyHeaders: false,
});
app.use('/api', apiLimiter);

// --- API routes ----------------------------------------------------------
app.use('/api/leads', leadsRouter);
app.use('/api/assessment', assessmentRouter);

app.get('/api/health', (req, res) => {
  res.json({ ok: true, status: 'healthy', timestamp: new Date().toISOString() });
});

// --- Static frontend -----------------------------------------------------
app.use(express.static(path.join(__dirname, 'public')));

// Fallback to index.html for any non-API route (simple SPA-style routing).
app.get('*', (req, res, next) => {
  if (req.path.startsWith('/api')) return next();
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// --- Error handling --------------------------------------------------------
app.use((req, res) => {
  res.status(404).json({ ok: false, errors: ['Not found.'] });
});

app.use((err, req, res, next) => {
  console.error(err);
  res.status(500).json({ ok: false, errors: ['Internal server error.'] });
});

app.listen(PORT, () => {
  console.log(`MaturityAssess backend running on http://localhost:${PORT}`);
});
