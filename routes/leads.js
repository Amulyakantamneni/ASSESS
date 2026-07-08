// routes/leads.js
// Handles the "Request Assessment" call-to-action: captures a lead
// (name, email, company, message) into the datastore.

const express = require('express');
const { nanoid } = require('nanoid');
const { Resend } = require('resend');
const db = require('../db');

const router = express.Router();

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const resend = process.env.RESEND_API_KEY ? new Resend(process.env.RESEND_API_KEY) : null;

async function notifyNewLead(lead) {
  if (!resend || !process.env.NOTIFY_EMAIL) return;
  try {
    await resend.emails.send({
      from: process.env.NOTIFY_FROM_EMAIL || 'onboarding@resend.dev',
      to: process.env.NOTIFY_EMAIL,
      subject: `New lead: ${lead.name}`,
      text: `Name: ${lead.name}\nEmail: ${lead.email}\nCompany: ${lead.company || '-'}\nMessage: ${lead.message || '-'}\nSource: ${lead.source}`,
    });
  } catch (err) {
    console.error('Failed to send lead notification email:', err);
  }
}

function validateLead(body) {
  const errors = [];
  const name = (body.name || '').trim();
  const email = (body.email || '').trim();
  const company = (body.company || '').trim();
  const message = (body.message || '').trim();

  if (!name) errors.push('Name is required.');
  if (!email) errors.push('Email is required.');
  else if (!EMAIL_RE.test(email)) errors.push('Email is not valid.');
  if (name.length > 200) errors.push('Name is too long.');
  if (company.length > 200) errors.push('Company is too long.');
  if (message.length > 2000) errors.push('Message is too long.');

  return { errors, clean: { name, email, company, message } };
}

// POST /api/leads  — create a new lead (Request Assessment button)
router.post('/', async (req, res) => {
  const { errors, clean } = validateLead(req.body || {});
  if (errors.length) {
    return res.status(400).json({ ok: false, errors });
  }

  const lead = {
    id: nanoid(12),
    ...clean,
    source: (req.body && req.body.source) || 'request-assessment-button',
    createdAt: new Date().toISOString(),
  };

  await db.insert('leads', lead);
  notifyNewLead(lead);

  return res.status(201).json({
    ok: true,
    message: "Thanks! We've received your request and will be in touch shortly.",
    leadId: lead.id,
  });
});

// GET /api/leads — simple listing for an internal admin view (protect this in production!)
router.get('/', async (req, res) => {
  const leads = await db.all('leads');
  const sorted = [...leads].sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
  res.json({ ok: true, count: sorted.length, leads: sorted });
});

module.exports = router;
