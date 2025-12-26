/**
 * Jobs Lifecycle Page
 * Unified view of action and rollback jobs.
 */

import React, { useState, useEffect } from 'react';
import { getJobStatusColor, getJobStatusIcon, getRollbackTimeRemaining } from '../utils/riskUtils';
import ErrorAlert from '../components/ErrorAlert';

export default function JobsLifecycle() {
    const [jobs, setJobs] = useState([]);
    const [total, setTotal] = useState(0);
    const [filter, setFilter] = useState('all'); // 'all', 'action', 'rollback'
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [refreshInterval, setRefreshInterval] = useState(null);

    useEffect(() => {
        fetchJobs();

        // Auto-refresh every 5 seconds for pending jobs
        const interval = setInterval(() => {
            if (jobs.some(j => j.status === 'pending')) {
                fetchJobs();
            }
        }, 5000);

        setRefreshInterval(interval);
        return () => clearInterval(interval);
    }, [filter]);

    const fetchJobs = async () => {
        setLoading(true);
        setError(null);

        try {
            const params = new URLSearchParams({
                limit: 100
            });

            if (filter !== 'all') {
                params.append('job_type', filter);
            }

            const response = await fetch(`/api/jobs?${params}`, {
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('token')}`
                }
            });

            if (!response.ok) {
                throw new Error('Failed to fetch jobs');
            }

            const data = await response.json();
            setJobs(data.jobs);
            setTotal(data.total);
        } catch (err) {
            setError({
                title: 'Failed to Load Jobs',
                message: err.message,
                severity: 'error'
            });
        } finally {
            setLoading(false);
        }
    };

    const handleConfirmRollback = async (jobId) => {
        try {
            const response = await fetch('/api/actions/confirm', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('token')}`
                },
                body: JSON.stringify({ rollback_job_id: jobId })
            });

            if (!response.ok) {
                throw new Error('Failed to confirm rollback');
            }

            // Refresh jobs after confirmation
            await fetchJobs();
        } catch (err) {
            setError({
                title: 'Confirmation Failed',
                message: err.message,
                action: 'Try again or contact support',
                severity: 'error'
            });
        }
    };

    const formatTimestamp = (timestamp) => {
        if (!timestamp) return '-';
        return new Date(timestamp).toLocaleString();
    };

    const renderTimeRemaining = (job) => {
        if (job.type !== 'rollback' || job.status !== 'pending' || !job.time_remaining) {
            return '-';
        }

        return (
            <div className="flex items-center">
                <span className="text-yellow-600 mr-2">⏱️</span>
                <span className="font-medium">{job.time_remaining}s</span>
            </div>
        );
    };

    const renderActions = (job) => {
        if (job.type === 'rollback' && job.status === 'pending') {
            return (
                <button
                    onClick={() => handleConfirmRollback(job.id)}
                    className="px-3 py-1 bg-green-600 text-white text-sm rounded hover:bg-green-700"
                >
                    Confirm
                </button>
            );
        }
        return '-';
    };

    return (
        <div className="p-6">
            <h1 className="text-2xl font-bold mb-6">Jobs</h1>

            <ErrorAlert error={error} onDismiss={() => setError(null)} />

            {/* Filter tabs */}
            <div className="bg-white rounded-lg shadow mb-6">
                <div className="border-b border-gray-200">
                    <nav className="flex -mb-px">
                        <button
                            onClick={() => setFilter('all')}
                            className={`px-6 py-3 border-b-2 font-medium text-sm ${filter === 'all'
                                    ? 'border-blue-500 text-blue-600'
                                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                                }`}
                        >
                            All Jobs
                        </button>
                        <button
                            onClick={() => setFilter('action')}
                            className={`px-6 py-3 border-b-2 font-medium text-sm ${filter === 'action'
                                    ? 'border-blue-500 text-blue-600'
                                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                                }`}
                        >
                            Action Jobs
                        </button>
                        <button
                            onClick={() => setFilter('rollback')}
                            className={`px-6 py-3 border-b-2 font-medium text-sm ${filter === 'rollback'
                                    ? 'border-blue-500 text-blue-600'
                                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                                }`}
                        >
                            Rollback Jobs
                        </button>
                    </nav>
                </div>
            </div>

            {/* Jobs table */}
            <div className="bg-white rounded-lg shadow overflow-hidden">
                <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                        <tr>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                Type
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                Action
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                Status
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                Created By
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                Time Remaining
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                Actions
                            </th>
                        </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                        {loading ? (
                            <tr>
                                <td colSpan="6" className="px-6 py-4 text-center text-gray-500">
                                    Loading...
                                </td>
                            </tr>
                        ) : jobs.length === 0 ? (
                            <tr>
                                <td colSpan="6" className="px-6 py-4 text-center text-gray-500">
                                    No jobs found
                                </td>
                            </tr>
                        ) : (
                            jobs.map((job) => (
                                <tr key={job.id} className="hover:bg-gray-50">
                                    <td className="px-6 py-4 whitespace-nowrap">
                                        <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-gray-100 text-gray-800">
                                            {job.type}
                                        </span>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                                        <div className="font-medium text-gray-900">{job.action_title}</div>
                                        <div className="text-gray-500 text-xs font-mono">{job.action_id}</div>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap">
                                        <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${getJobStatusColor(job.status)}`}>
                                            {getJobStatusIcon(job.status)} {job.status}
                                        </span>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                        {job.created_by_username}
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                        {renderTimeRemaining(job)}
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                                        {renderActions(job)}
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>

            {/* Info */}
            {jobs.some(j => j.type === 'rollback' && j.status === 'pending') && (
                <div className="mt-4 bg-yellow-50 border-l-4 border-yellow-400 p-4">
                    <div className="flex">
                        <div className="flex-shrink-0">
                            <span className="text-yellow-400">⚠️</span>
                        </div>
                        <div className="ml-3">
                            <p className="text-sm text-yellow-700">
                                <strong>Pending rollback jobs require confirmation.</strong> If not confirmed before the deadline, changes will be automatically rolled back.
                            </p>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
