(function (root) {
  'use strict';

  function createDemoEvents() {
    const products = [
      ['Studio headphones', 'Audio', 12900], ['Portable speaker', 'Audio', 7900],
      ['Task lamp', 'Desk', 4900], ['Mechanical keyboard', 'Desk', 9900],
      ['Trail backpack', 'Outdoor', 8900], ['Steel bottle', 'Outdoor', 2900],
    ];
    const events = [];
    for (let day = 0; day < 7; day++) {
      const count = [96, 124, 108, 156, 132, 180, 144][day];
      for (let i = 0; i < count; i++) {
        const [product_name, category, unit_price] = products[(i * 5 + day) % products.length];
        const slot = (i * 7 + day * 3) % 20;
        const event_type = slot < 6 ? 'search' : slot < 16 ? 'view' : slot < 19 ? 'purchase' : 'error';
        const event = {
          event_id: `demo-${day}-${i}`,
          '@timestamp': new Date(Date.UTC(2026, 8, day + 1, 0, Math.floor(i * 1440 / count))).toISOString(),
          event_type, category, product_name,
        };
        if (event_type === 'purchase') {
          event.unit_price = unit_price;
          event.quantity = 1 + i % 3;
          event.amount = unit_price * event.quantity;
        }
        events.push(event);
      }
    }
    return events;
  }

  function filterEvents(events, { start = '', end = '', category = 'all' } = {}) {
    for (const date of [start, end].filter(Boolean)) {
      const parsed = new Date(`${date}T00:00:00Z`);
      if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || !Number.isFinite(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== date) {
        throw new Error('Choose a valid date.');
      }
    }
    if (start && end && start > end) throw new Error('Start date must be on or before end date.');
    return events.filter(event => {
      const date = event['@timestamp'].slice(0, 10);
      return (!start || date >= start) && (!end || date <= end) && (category === 'all' || event.category === category);
    });
  }

  function summarize(events) {
    const types = { search: 0, view: 0, purchase: 0, error: 0 };
    const days = new Map();
    const products = new Map();
    let revenueCents = 0;
    for (const event of events) {
      types[event.event_type]++;
      const date = event['@timestamp'].slice(0, 10);
      days.set(date, (days.get(date) || 0) + 1);
      if (event.event_type === 'purchase') {
        revenueCents += event.amount;
        const product = products.get(event.product_name) || { name: event.product_name, revenueCents: 0, purchases: 0 };
        product.revenueCents += event.amount;
        product.purchases++;
        products.set(event.product_name, product);
      }
    }
    return {
      total: events.length, purchases: types.purchase, revenueCents,
      errorRate: events.length ? types.error / events.length * 100 : 0, types,
      days: [...days].sort(([a], [b]) => a.localeCompare(b)).map(([date, count]) => ({ date, count })),
      products: [...products.values()].sort((a, b) => b.revenueCents - a.revenueCents || a.name.localeCompare(b.name)),
    };
  }

  const api = { createDemoEvents, filterEvents, summarize };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.LabModel = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
