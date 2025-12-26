/**
 * RiskBadge Component
 * Displays action risk level with color coding and icons.
 */

import React from 'react';
import { getRiskColors, RISK_LEVELS } from '../utils/riskUtils';

export default function RiskBadge({ risk }) {
    const colors = getRiskColors(risk);

    return (
        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${colors.bg} ${colors.text} ${colors.border} border`}>
            <span className="mr-1">{colors.icon}</span>
            {risk.toUpperCase()}
        </span>
    );
}
