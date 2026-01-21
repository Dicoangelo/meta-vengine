/**
 * Centralized pricing configuration for Node.js scripts.
 *
 * Usage:
 *   const { PRICING, getModelCost, getCostPerMessage } = require('~/.claude/config/pricing.js');
 */

const fs = require('fs');
const path = require('path');

const PRICING_FILE = path.join(__dirname, 'pricing.json');

let _config;
try {
    _config = JSON.parse(fs.readFileSync(PRICING_FILE, 'utf8'));
} catch (e) {
    // Fallback defaults (Opus 4.5 Jan 2026)
    _config = {
        models: {
            opus: { input: 5, output: 25, cache_read: 0.5 },
            sonnet: { input: 3, output: 15, cache_read: 0.3 },
            haiku: { input: 0.80, output: 4, cache_read: 0.08 }
        },
        estimates: { opus: 0.027, sonnet: 0.017, haiku: 0.004 },
        subscription: { monthly_rate: 280, currency: 'CAD' },
        _meta: { version: 'fallback' }
    };
}

const PRICING = _config.models;
const ESTIMATES = _config.estimates;
const SUBSCRIPTION = _config.subscription;
const VERSION = _config._meta.version;

function normalizeModel(model) {
    const m = model.toLowerCase();
    if (m.includes('opus')) return 'opus';
    if (m.includes('sonnet')) return 'sonnet';
    if (m.includes('haiku')) return 'haiku';
    return 'sonnet'; // Default
}

function getModelCost(model, inputTokens, outputTokens, cacheReads = 0) {
    const key = normalizeModel(model);
    const p = PRICING[key];
    if (!p) return 0;

    let cost = (inputTokens / 1_000_000) * p.input;
    cost += (outputTokens / 1_000_000) * p.output;
    cost += (cacheReads / 1_000_000) * p.cache_read;
    return cost;
}

function getCostPerMessage(model) {
    return ESTIMATES[normalizeModel(model)] || ESTIMATES.sonnet;
}

function getInputRate(model) {
    return PRICING[normalizeModel(model)]?.input || PRICING.sonnet.input;
}

function getOutputRate(model) {
    return PRICING[normalizeModel(model)]?.output || PRICING.sonnet.output;
}

module.exports = {
    PRICING,
    ESTIMATES,
    SUBSCRIPTION,
    VERSION,
    getModelCost,
    getCostPerMessage,
    getInputRate,
    getOutputRate,
    normalizeModel
};
