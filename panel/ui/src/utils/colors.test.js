import { describe, it, expect } from 'vitest';
import { hexToRgb, rgbToHex, rgbToHsv, hsvToRgb, clamp255 } from './colors';

describe('hexToRgb', () => {
    it('should convert hex to RGB', () => {
        expect(hexToRgb('#ff0000')).toEqual({ red: 255, green: 0, blue: 0 });
        expect(hexToRgb('#00ff00')).toEqual({ red: 0, green: 255, blue: 0 });
        expect(hexToRgb('#0000ff')).toEqual({ red: 0, green: 0, blue: 255 });
        expect(hexToRgb('#ffffff')).toEqual({ red: 255, green: 255, blue: 255 });
        expect(hexToRgb('#000000')).toEqual({ red: 0, green: 0, blue: 0 });
    });

    it('should handle hex without #', () => {
        expect(hexToRgb('ff0000')).toEqual({ red: 255, green: 0, blue: 0 });
    });
});

describe('rgbToHex', () => {
    it('should convert RGB to hex', () => {
        expect(rgbToHex(255, 0, 0)).toBe('#ff0000');
        expect(rgbToHex(0, 255, 0)).toBe('#00ff00');
        expect(rgbToHex(0, 0, 255)).toBe('#0000ff');
    });
});

describe('clamp255', () => {
    it('should clamp values to 0-255', () => {
        expect(clamp255(-10)).toBe(0);
        expect(clamp255(0)).toBe(0);
        expect(clamp255(128)).toBe(128);
        expect(clamp255(255)).toBe(255);
        expect(clamp255(300)).toBe(255);
    });
});

describe('rgbToHsv and hsvToRgb roundtrip', () => {
    it('should roundtrip RGB -> HSV -> RGB for red', () => {
        const hsv = rgbToHsv(255, 0, 0);
        const rgb = hsvToRgb(hsv.h, hsv.s, hsv.v);
        expect(rgb.r).toBe(255);
        expect(rgb.g).toBe(0);
        expect(rgb.b).toBe(0);
    });

    it('should roundtrip RGB -> HSV -> RGB for green', () => {
        const hsv = rgbToHsv(0, 255, 0);
        const rgb = hsvToRgb(hsv.h, hsv.s, hsv.v);
        expect(rgb.r).toBe(0);
        expect(rgb.g).toBe(255);
        expect(rgb.b).toBe(0);
    });

    it('should roundtrip RGB -> HSV -> RGB for arbitrary color', () => {
        const hsv = rgbToHsv(100, 150, 200);
        const rgb = hsvToRgb(hsv.h, hsv.s, hsv.v);
        expect(rgb.r).toBeCloseTo(100, 0);
        expect(rgb.g).toBeCloseTo(150, 0);
        expect(rgb.b).toBeCloseTo(200, 0);
    });

    it('should handle black', () => {
        const hsv = rgbToHsv(0, 0, 0);
        expect(hsv.v).toBe(0);
        const rgb = hsvToRgb(0, 0, 0);
        expect(rgb.r).toBe(0);
        expect(rgb.g).toBe(0);
        expect(rgb.b).toBe(0);
    });

    it('should handle white', () => {
        const hsv = rgbToHsv(255, 255, 255);
        expect(hsv.s).toBe(0);
        const rgb = hsvToRgb(0, 0, 1);
        expect(rgb.r).toBe(255);
        expect(rgb.g).toBe(255);
        expect(rgb.b).toBe(255);
    });
});
