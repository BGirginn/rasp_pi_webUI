/**
 * CooldownIndicator Component
 * Shows cooldown status and countdown timer.
 */

import React, { useState, useEffect } from 'react';
import { formatCooldownTime } from '../utils/riskUtils';

export default function CooldownIndicator({ lastExecuted, cooldownSeconds }) {
    const [timeRemaining, setTimeRemaining] = useState(0);

    useEffect(() => {
        if (!lastExecuted || !cooldownSeconds) {
            setTimeRemaining(0);
            return;
        }

        const updateRemaining = () => {
            const elapsedMs = Date.now() - new Date(lastExecuted).getTime();
            const elapsedSeconds = Math.floor(elapsedMs / 1000);
            const remaining = Math.max(0, cooldownSeconds - elapsedSeconds);
            setTimeRemaining(remaining);
        };

        updateRemaining();
        const interval = setInterval(updateRemaining, 1000);

        return () => clearInterval(interval);
    }, [lastExecuted, cooldownSeconds]);

    if (!cooldownSeconds || timeRemaining === 0) {
        return null;
    }

    return (
        <div className="flex items-center text-sm text-gray-600 mt-2">
            <span className="mr-2">⏱️</span>
            <span>
                Cooldown active: {formatCooldownTime(timeRemaining)} remaining
            </span>
        </div>
    );
}
