/**
 * US-101: Learnable Weight Schema — Unified Parameter Registry (JS Loader)
 *
 * Loads config/learnable-params.json and validates all group constraints.
 * Provides getParam(), getGroup(), and getAllParams() for downstream consumers.
 */

'use strict';

const fs = require('fs');
const path = require('path');

const REGISTRY_PATH = path.join(__dirname, '..', 'config', 'learnable-params.json');

class ParamRegistry {
  constructor(registryPath) {
    this.registryPath = registryPath || REGISTRY_PATH;
    this.params = new Map();
    this.groups = {};
    this.banditEnabled = false;
    this._load();
  }

  _load() {
    let raw;
    try {
      raw = fs.readFileSync(this.registryPath, 'utf8');
    } catch (err) {
      throw new Error(`ParamRegistry: cannot read ${this.registryPath}: ${err.message}`);
    }

    let data;
    try {
      data = JSON.parse(raw);
    } catch (err) {
      throw new Error(`ParamRegistry: malformed JSON in ${this.registryPath}: ${err.message}`);
    }

    if (!Array.isArray(data.parameters)) {
      throw new Error('ParamRegistry: missing "parameters" array');
    }
    if (!data.groups || typeof data.groups !== 'object') {
      throw new Error('ParamRegistry: missing "groups" object');
    }

    this.banditEnabled = data.banditEnabled === true;
    this.groups = data.groups;

    for (const p of data.parameters) {
      this._validateParam(p);
      this.params.set(p.id, { ...p });
    }

    this._validateConstraints();
  }

  _validateParam(p) {
    const required = ['id', 'configFile', 'jsonPath', 'value', 'min', 'max', 'learnRate', 'group'];
    for (const field of required) {
      if (p[field] === undefined || p[field] === null) {
        throw new Error(`ParamRegistry: parameter missing required field "${field}": ${JSON.stringify(p)}`);
      }
    }
    if (typeof p.value !== 'number' || typeof p.min !== 'number' || typeof p.max !== 'number') {
      throw new Error(`ParamRegistry: value/min/max must be numbers for "${p.id}"`);
    }
    if (p.value < p.min || p.value > p.max) {
      throw new Error(`ParamRegistry: value ${p.value} out of bounds [${p.min}, ${p.max}] for "${p.id}"`);
    }
    // Integer constraint validation
    if (p.integerOnly && !Number.isInteger(p.value)) {
      throw new Error(`ParamRegistry: value ${p.value} must be integer for "${p.id}"`);
    }
    if (p.learnRate <= 0 || p.learnRate > 1) {
      throw new Error(`ParamRegistry: learnRate must be in (0, 1] for "${p.id}"`);
    }
    if (!this.groups && !p.group) {
      throw new Error(`ParamRegistry: parameter "${p.id}" has no group`);
    }
  }

  _validateConstraints() {
    for (const [groupName, groupDef] of Object.entries(this.groups)) {
      const members = this.getGroup(groupName);

      if (groupDef.constraint === 'sumMustEqual') {
        const sum = members.reduce((acc, p) => acc + p.value, 0);
        const target = groupDef.target;
        if (Math.abs(sum - target) > 0.01) {
          throw new Error(
            `ParamRegistry: group "${groupName}" sum constraint violated: ` +
            `sum=${sum.toFixed(4)}, target=${target}`
          );
        }
      }

      if (groupDef.constraint === 'monotonic') {
        const values = members
          .sort((a, b) => a.value - b.value)
          .map(p => p.value);
        for (let i = 1; i < values.length; i++) {
          if (groupDef.direction === 'ascending' && values[i] < values[i - 1]) {
            throw new Error(
              `ParamRegistry: group "${groupName}" monotonic ascending constraint violated`
            );
          }
        }
      }
    }
  }

  getParam(id) {
    const p = this.params.get(id);
    if (!p) {
      throw new Error(`ParamRegistry: unknown parameter "${id}"`);
    }
    return { ...p };
  }

  getGroup(groupName) {
    return Array.from(this.params.values())
      .filter(p => p.group === groupName)
      .map(p => ({ ...p }));
  }

  getAllParams() {
    return Array.from(this.params.values()).map(p => ({ ...p }));
  }

  getGroupNames() {
    return Object.keys(this.groups);
  }

  getGroupConstraint(groupName) {
    return this.groups[groupName] || null;
  }

  isBanditEnabled() {
    return this.banditEnabled;
  }

  toWeightMap(groupName) {
    const members = this.getGroup(groupName);
    const map = {};
    for (const p of members) {
      const key = p.id.replace(`${groupName}_`, '').replace(`${groupName.split('_')[0]}_`, '');
      map[key] = p.value;
    }
    return map;
  }
}

let _instance = null;

function getRegistry(registryPath) {
  if (!_instance) {
    _instance = new ParamRegistry(registryPath);
  }
  return _instance;
}

function resetRegistry() {
  _instance = null;
}

module.exports = { ParamRegistry, getRegistry, resetRegistry };
