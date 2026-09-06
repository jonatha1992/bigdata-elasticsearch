const { test } = require('node:test');
const assert = require('node:assert/strict');
const { summarize, filterEvents, createDemoEvents } = require('./model.js');

const events = [
  { event_id: '1', '@timestamp': '2026-09-01T10:00:00Z', event_type: 'view', category: 'Audio' },
  { event_id: '2', '@timestamp': '2026-09-01T11:00:00Z', event_type: 'purchase', category: 'Audio', product_name: 'Headphones', amount: 12000 },
  { event_id: '3', '@timestamp': '2026-09-02T10:00:00Z', event_type: 'purchase', category: 'Desk', product_name: 'Lamp', amount: 5000 },
  { event_id: '4', '@timestamp': '2026-09-02T11:00:00Z', event_type: 'error', category: 'Audio' },
  { event_id: '5', '@timestamp': '2026-09-03T10:00:00Z', event_type: 'search' },
];

test('metrics reconcile counts, purchase amounts and error denominator', () => {
  const result = summarize(events);
  assert.equal(result.total, 5);
  assert.equal(result.purchases, 2);
  assert.equal(result.revenueCents, 17000);
  assert.equal(result.errorRate, 20);
  assert.deepEqual(result.types, { search: 1, view: 1, purchase: 2, error: 1 });
  assert.deepEqual(result.days.map(d => d.count), [2, 2, 1]);
  assert.deepEqual(result.products, [
    { name: 'Headphones', revenueCents: 12000, purchases: 1 },
    { name: 'Lamp', revenueCents: 5000, purchases: 1 },
  ]);
});

test('inclusive UTC date and category filters combine without changing source', () => {
  const before = JSON.stringify(events);
  assert.deepEqual(filterEvents(events, { start: '2026-09-02', end: '2026-09-02', category: 'Audio' }).map(e => e.event_id), ['4']);
  assert.equal(JSON.stringify(events), before);
  assert.equal(filterEvents(events, { start: '2026-09-01', end: '2026-09-03', category: 'all' }).length, 5);
});

test('empty results produce zero metrics and no undefined rates', () => {
  const result = summarize(filterEvents(events, { category: 'Missing' }));
  assert.equal(result.total, 0);
  assert.equal(result.errorRate, 0);
  assert.equal(result.revenueCents, 0);
  assert.deepEqual(result.products, []);
  assert.deepEqual(result.days, []);
});

test('invalid or reversed date ranges fail with useful errors', () => {
  assert.throws(() => filterEvents(events, { start: '2026-09-03', end: '2026-09-01' }), /Start date/);
  assert.throws(() => filterEvents(events, { start: '2026-02-30' }), /valid date/);
});

test('demo fixture is stable, has unique IDs and all four event types', () => {
  const data = createDemoEvents();
  assert.deepEqual(data, createDemoEvents());
  assert.ok(data.length >= 100);
  assert.equal(new Set(data.map(e => e.event_id)).size, data.length);
  assert.deepEqual([...new Set(data.map(e => e.event_type))].sort(), ['error', 'purchase', 'search', 'view']);
  for (const event of data.filter(e => e.event_type === 'purchase')) {
    assert.equal(event.amount, event.unit_price * event.quantity);
    assert.ok(Number.isSafeInteger(event.amount));
  }
});
