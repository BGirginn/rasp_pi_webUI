/**
 * ConfirmationDialog Component  
 * Two-step confirmation for high-risk actions.
 */

import React, { useState } from 'react';
import RiskBadge from './RiskBadge';

export default function ConfirmationDialog({ action, onConfirm, onCancel, isOpen }) {
    const [step, setStep] = useState(1);
    const [acknowledged, setAcknowledged] = useState(false);

    if (!isOpen) return null;

    const handleContinue = () => {
        if (step === 1) {
            setStep(2);
        } else {
            onConfirm();
            handleClose();
        }
    };

    const handleClose = () => {
        setStep(1);
        setAcknowledged(false);
        onCancel();
    };

    return (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
                {step === 1 ? (
                    <>
                        <div className="mb-4">
                            <h2 className="text-xl font-bold mb-2">Confirm Action</h2>
                            <RiskBadge risk={action.risk} />
                        </div>

                        <div className="mb-6">
                            <p className="font-medium mb-2">{action.title}</p>
                            <p className="text-sm text-gray-600">{action.description || 'This action will make changes to your system.'}</p>
                        </div>

                        <label className="flex items-start mb-6 cursor-pointer">
                            <input
                                type="checkbox"
                                checked={acknowledged}
                                onChange={(e) => setAcknowledged(e.target.checked)}
                                className="mt-1 mr-3"
                            />
                            <span className="text-sm">
                                I understand the risks and want to proceed with this action
                            </span>
                        </label>

                        <div className="flex gap-3">
                            <button
                                onClick={handleClose}
                                className="flex-1 px-4 py-2 border border-gray-300 rounded hover:bg-gray-50"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleContinue}
                                disabled={!acknowledged}
                                className="flex-1 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                Continue →
                            </button>
                        </div>
                    </>
                ) : (
                    <>
                        <div className="mb-4">
                            <h2 className="text-xl font-bold mb-2">Final Confirmation</h2>
                        </div>

                        <div className="mb-6">
                            <p className="mb-2">You are about to:</p>
                            <p className="font-medium text-lg mb-4">{action.title}</p>

                            {action.risk === 'high' && (
                                <div className="bg-red-50 border-l-4 border-red-400 p-3 text-sm text-red-800">
                                    ⚠️ This action cannot be easily undone. Make sure you know what you're doing.
                                </div>
                            )}
                        </div>

                        <div className="flex gap-3">
                            <button
                                onClick={() => setStep(1)}
                                className="flex-1 px-4 py-2 border border-gray-300 rounded hover:bg-gray-50"
                            >
                                ← Go Back
                            </button>
                            <button
                                onClick={handleContinue}
                                className="flex-1 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
                            >
                                Confirm {action.title}
                            </button>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}
