/**
 * Centralized color conversion utilities.
 * Extracted from IoTDeviceDetail.jsx.
 */

export function hexToRgb(hex) {
    const normalized = hex.replace('#', '');
    return {
        red: parseInt(normalized.substring(0, 2), 16),
        green: parseInt(normalized.substring(2, 4), 16),
        blue: parseInt(normalized.substring(4, 6), 16),
    };
}

export function clamp255(n) {
    return Math.max(0, Math.min(255, n));
}

export function rgbToHex(r, g, b) {
    const toHex = (v) => clamp255(v).toString(16).padStart(2, '0');
    return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}

export function rgbToHsv(r, g, b) {
    const rr = r / 255, gg = g / 255, bb = b / 255;
    const max = Math.max(rr, gg, bb);
    const min = Math.min(rr, gg, bb);
    const d = max - min;

    let h = 0;
    if (d !== 0) {
        if (max === rr) h = ((gg - bb) / d) % 6;
        else if (max === gg) h = (bb - rr) / d + 2;
        else h = (rr - gg) / d + 4;
        h *= 60;
        if (h < 0) h += 360;
    }

    const s = max === 0 ? 0 : d / max;
    const v = max;
    return { h, s, v };
}

export function hsvToRgb(h, s, v) {
    const c = v * s;
    const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
    const m = v - c;
    let rr = 0, gg = 0, bb = 0;
    if (h >= 0 && h < 60) { rr = c; gg = x; bb = 0; }
    else if (h >= 60 && h < 120) { rr = x; gg = c; bb = 0; }
    else if (h >= 120 && h < 180) { rr = 0; gg = c; bb = x; }
    else if (h >= 180 && h < 240) { rr = 0; gg = x; bb = c; }
    else if (h >= 240 && h < 300) { rr = x; gg = 0; bb = c; }
    else { rr = c; gg = 0; bb = x; }
    return {
        r: Math.round((rr + m) * 255),
        g: Math.round((gg + m) * 255),
        b: Math.round((bb + m) * 255),
    };
}
