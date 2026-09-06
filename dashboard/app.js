'use strict';

const allEvents = LabModel.createDemoEvents();
const filters = document.querySelector('#filters');
const number = new Intl.NumberFormat('en-US');
const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 });
const labels = { search: 'Search', view: 'View', purchase: 'Purchase', error: 'Error' };

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function render() {
  const error = document.querySelector('#filter-error');
  let selected;
  try {
    selected = LabModel.filterEvents(allEvents, {
      start: filters.elements.start.value,
      end: filters.elements.end.value,
      category: filters.elements.category.value,
    });
  } catch (reason) {
    error.textContent = `${reason.message} Panels still show the last valid selection.`;
    error.hidden = false;
    return;
  }
  error.hidden = true;
  const summary = LabModel.summarize(selected);
  document.querySelector('#total').textContent = number.format(summary.total);
  document.querySelector('#purchases').textContent = number.format(summary.purchases);
  document.querySelector('#revenue').textContent = money.format(summary.revenueCents / 100);
  document.querySelector('#error-rate').textContent = summary.total ? `${summary.errorRate.toFixed(1)}%` : 'N/A';
  document.querySelector('#empty').hidden = summary.total !== 0;
  document.querySelector('#result-status').textContent = `${number.format(summary.total)} example events · ${filters.elements.start.value} to ${filters.elements.end.value} UTC · ${filters.elements.category.selectedOptions[0].textContent}`;

  const timeline = document.querySelector('#timeline');
  timeline.replaceChildren();
  const peak = Math.max(1, ...summary.days.map(day => day.count));
  for (const day of summary.days) {
    const column = element('div', 'day');
    column.setAttribute('aria-label', `${day.date}: ${day.count} events`);
    const count = element('span', 'day-count', number.format(day.count));
    const bar = element('div', 'bar');
    bar.style.height = `${day.count / peak * 145}px`;
    bar.setAttribute('aria-hidden', 'true');
    column.append(count, bar, element('span', 'day-label', `Sep ${Number(day.date.slice(-2))}`));
    timeline.append(column);
  }
  if (!summary.total) timeline.append(element('p', 'quiet', 'No activity to display.'));

  const types = document.querySelector('#types');
  types.replaceChildren();
  for (const [type, count] of Object.entries(summary.types)) {
    const share = summary.total ? count / summary.total * 100 : 0;
    const row = element('div', `type-${type}`);
    const heading = element('div', 'type-heading');
    heading.append(element('span', '', labels[type]), element('strong', '', `${number.format(count)} / ${share.toFixed(1)}%`));
    const track = element('div', 'track');
    track.setAttribute('aria-hidden', 'true');
    const fill = element('div', 'fill');
    fill.style.width = `${share}%`;
    track.append(fill);
    row.append(heading, track);
    types.append(row);
  }

  const products = document.querySelector('#products');
  products.replaceChildren();
  for (const product of summary.products) {
    const row = element('tr');
    row.append(element('td', '', product.name), element('td', '', number.format(product.purchases)), element('td', '', money.format(product.revenueCents / 100)));
    products.append(row);
  }
  if (!summary.products.length) {
    const cell = element('td', '', 'No purchase events in this selection.');
    cell.colSpan = 3;
    const row = element('tr');
    row.append(cell);
    products.append(row);
  }
}

filters.addEventListener('submit', event => {
  event.preventDefault();
  render();
});
filters.addEventListener('reset', () => setTimeout(render, 0));
render();
