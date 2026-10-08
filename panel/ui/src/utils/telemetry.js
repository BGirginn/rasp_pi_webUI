export function formatObservedState(value, stale = false) {
  if (stale || value == null) return 'Unknown';
  return value === 1 ? 'On' : 'Off';
}

export function breakTelemetryGaps(rows, step) {
  return rows.flatMap((row, index) => {
    if (index > 0 && row.ts - rows[index - 1].ts > step * 3) {
      return [{ ts: rows[index - 1].ts + step, time: '' }, row];
    }
    return [row];
  });
}

export function getPowerRails(metrics) {
  const rails = new Map();
  Object.entries(metrics || {}).forEach(([key, value]) => {
    const match = key.match(/^host\.power\.pmic\.([a-z0-9_]+)\.(voltage_v|current_a)$/);
    if (!match || !Number.isFinite(value)) return;
    const [, name, measurement] = match;
    if (!rails.has(name)) rails.set(name, { name });
    rails.get(name)[measurement] = value;
  });
  return Array.from(rails.values()).sort((left, right) => left.name.localeCompare(right.name));
}
