import { describe, it, expect } from 'vitest';
import { formatBytes, formatSpeed, formatUptime, formatPercentage } from './format';

describe('formatBytes', () => {
    it('should return "0 B" for zero', () => {
        expect(formatBytes(0)).toBe('0 B');
    });

    it('should return "0 B" for null/undefined', () => {
        expect(formatBytes(null)).toBe('0 B');
        expect(formatBytes(undefined)).toBe('0 B');
    });

    it('should format bytes correctly', () => {
        expect(formatBytes(500)).toBe('500.0 B');
        expect(formatBytes(1024)).toBe('1.0 KB');
        expect(formatBytes(1048576)).toBe('1.0 MB');
        expect(formatBytes(1073741824)).toBe('1.0 GB');
    });

    it('should respect decimals parameter', () => {
        expect(formatBytes(1536, 2)).toBe('1.50 KB');
        expect(formatBytes(1536, 0)).toBe('2 KB');
    });
});

describe('formatSpeed', () => {
    it('should append /s to formatted bytes', () => {
        expect(formatSpeed(0)).toBe('0 B/s');
        expect(formatSpeed(1024)).toBe('1.0 KB/s');
        expect(formatSpeed(1048576)).toBe('1.0 MB/s');
    });
});

describe('formatUptime', () => {
    it('should return "< 1m" for short durations', () => {
        expect(formatUptime(0)).toBe('< 1m');
        expect(formatUptime(30)).toBe('< 1m');
        expect(formatUptime(null)).toBe('< 1m');
    });

    it('should format minutes', () => {
        expect(formatUptime(60)).toBe('1m');
        expect(formatUptime(300)).toBe('5m');
    });

    it('should format hours and minutes', () => {
        expect(formatUptime(3600)).toBe('1h');
        expect(formatUptime(3660)).toBe('1h 1m');
    });

    it('should format days, hours, and minutes', () => {
        expect(formatUptime(86400)).toBe('1d');
        expect(formatUptime(90061)).toBe('1d 1h 1m');
    });
});

describe('formatPercentage', () => {
    it('should format with default 1 decimal', () => {
        expect(formatPercentage(45.678)).toBe('45.7%');
    });

    it('should format with custom decimals', () => {
        expect(formatPercentage(45.678, 2)).toBe('45.68%');
        expect(formatPercentage(45.678, 0)).toBe('46%');
    });
});
