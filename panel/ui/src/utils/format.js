/**
 * Centralized formatting utilities.
 * Replaces duplicate implementations across components.
 */

export function formatBytes(bytes, decimals = 1) {
    if (bytes === 0 || bytes == null) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(Math.abs(bytes)) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(decimals)} ${sizes[i]}`;
}

export function formatSpeed(bytesPerSecond, decimals = 1) {
    return `${formatBytes(bytesPerSecond, decimals)}/s`;
}

export function formatUptime(seconds) {
    if (!seconds || seconds < 60) return '< 1m';
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const parts = [];
    if (days > 0) parts.push(`${days}d`);
    if (hours > 0) parts.push(`${hours}h`);
    if (minutes > 0) parts.push(`${minutes}m`);
    return parts.join(' ') || '< 1m';
}

export function formatPercentage(value, decimals = 1) {
    return `${Number(value).toFixed(decimals)}%`;
}
