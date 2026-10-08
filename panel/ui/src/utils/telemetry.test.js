import { describe, expect, it } from 'vitest';
import { breakTelemetryGaps, formatObservedState, getPowerRails } from './telemetry';

describe('observed host telemetry', () => {
  it('shows unknown when the Pi cannot be observed', () => {
    expect(formatObservedState(1)).toBe('On');
    expect(formatObservedState(0)).toBe('Off');
    expect(formatObservedState(undefined)).toBe('Unknown');
    expect(formatObservedState(1, true)).toBe('Unknown');
  });

  it('keeps missing samples as gaps instead of inventing an off state', () => {
    const rows = [{ ts: 100, powerOn: 1 }, { ts: 105, powerOn: 1 }, { ts: 200, powerOn: 1 }];
    expect(breakTelemetryGaps(rows, 5)).toEqual([rows[0], rows[1], { ts: 110, time: '' }, rows[2]]);
  });

  it('preserves numeric zero and omits unavailable rail measurements', () => {
    expect(getPowerRails({
      'host.power.pmic.vdd_core.voltage_v': 0.75,
      'host.power.pmic.vdd_core.current_a': 0,
      'host.power.pmic.available': 1,
      'host.power.input_voltage_v': 5,
      'host.power.pmic.bad.current_a': NaN,
    })).toEqual([{ name: 'vdd_core', voltage_v: 0.75, current_a: 0 }]);
  });
});
