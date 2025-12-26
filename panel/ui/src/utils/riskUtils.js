/**
 * Risk Level Utilities
 * Helper functions for handling action risk levels and safety indicators.
 */

export const RISK_LEVELS = {
    LOW: 'low',
    MEDIUM: 'medium',
    HIGH: 'high'
};

export const RISK_COLORS = {
    [RISK_LEVELS.LOW]: {
        bg: 'bg-green-100',
        text: 'text-green-800',
        border: 'border-green-300',
        icon: 'ℹ️'
    },
    [RISK_LEVELS.MEDIUM]: {
        bg: 'bg-yellow-100',
        text: 'text-yellow-800',
        border: 'border-yellow-300',
        icon: '⚠️'
    },
    [RISK_LEVELS.HIGH]: {
        bg: 'bg-red-100',
        text: 'text-red-800',
        border: 'border-red-300',
        icon: '🛑'
    }
};

/**
 * Get color classes for a risk level
 */
export function getRiskColors(riskLevel) {
    return RISK_COLORS[riskLevel] || RISK_COLORS[RISK_LEVELS.LOW];
}

/**
 * Check if action requires confirmation based on risk
 */
export function requiresConfirmation(action) {
    return action.requires_confirmation === true || action.risk === RISK_LEVELS.HIGH;
}

/**
 * Check if action has cooldown
 */
export function hasCooldown(action) {
    return action.cooldown_seconds > 0;
}

/**
 * Format cooldown remaining time
 */
export function formatCooldownTime(seconds) {
    if (seconds < 60) {
        return `${seconds}s`;
    }

    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;

    if (remainingSeconds === 0) {
        return `${minutes}m`;
    }

    return `${minutes}m ${remainingSeconds}s`;
}

/**
 * Calculate time remaining for rollback job
 */
export function getRollbackTimeRemaining(job) {
    if (!job || job.status !== 'pending' || !job.due_at) {
        return null;
    }

    const now = Math.floor(Date.now() / 1000);
    const remaining = job.due_at - now;

    return Math.max(0, remaining);
}

/**
 * Get status color for job
 */
export function getJobStatusColor(status) {
    const colors = {
        pending: 'text-yellow-600 bg-yellow-100',
        running: 'text-blue-600 bg-blue-100',
        confirmed: 'text-green-600 bg-green-100',
        rolled_back: 'text-orange-600 bg-orange-100',
        failed: 'text-red-600 bg-red-100',
        expired: 'text-gray-600 bg-gray-100'
    };

    return colors[status] || colors.pending;
}

/**
 * Get status icon for job
 */
export function getJobStatusIcon(status) {
    const icons = {
        pending: '⏱️',
        running: '▶️',
        confirmed: '✓',
        rolled_back: '↩️',
        failed: '✗',
        expired: '⏹️'
    };

    return icons[status] || '•';
}
