/**
 * ErrorAlert Component
 * Enhanced error display with color-coded severity and actionable messages.
 */

import React from 'react';

export default function ErrorAlert({ error, onDismiss }) {
    if (!error) return null;

    const severityColors = {
        error: 'bg-red-50 border-red-400 text-red-800',
        warning: 'bg-yellow-50 border-yellow-400 text-yellow-800',
        info: 'bg-blue-50 border-blue-400 text-blue-800'
    };

    const severityIcons = {
        error: '⚠️',
        warning: '⚠️',
        info: 'ℹ️'
    };

    const colorClass = severityColors[error.severity || 'error'];
    const icon = severityIcons[error.severity || 'error'];

    return (
        <div className={`border-l-4 p-4 ${colorClass} rounded mb-4`} role="alert">
            <div className="flex justify-between items-start">
                <div className="flex-1">
                    <div className="flex items-center mb-1">
                        <span className="mr-2 text-xl">{icon}</span>
                        <h3 className="font-bold">{error.title || 'Error'}</h3>
                    </div>

                    <p className="text-sm mb-2">{error.message}</p>

                    {error.action && (
                        <p className="text-sm italic">
                            <strong>What to do:</strong> {error.action}
                        </p>
                    )}

                    {error.details && (
                        <div className="mt-2 text-xs font-mono bg-white bg-opacity-50 p-2 rounded">
                            {JSON.stringify(error.details, null, 2)}
                        </div>
                    )}
                </div>

                {onDismiss && (
                    <button
                        onClick={onDismiss}
                        className="ml-4 text-gray-500 hover:text-gray-700"
                        aria-label="Dismiss"
                    >
                        ✕
                    </button>
                )}
            </div>
        </div>
    );
}
