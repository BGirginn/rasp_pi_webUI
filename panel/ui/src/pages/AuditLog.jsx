/**
 * Audit Log Page
 * View and filter audit log entries.
 */

import React, { useState, useEffect } from 'react';
import ErrorAlert from '../components/ErrorAlert';

export default function AuditLog() {
    const [audits, setAudits] = useState([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(0);
    const [limit] = useState(50);
    const [filters, setFilters] = useState({
        action_id: '',
        username: '',
        status: ''
    });
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        fetchAudits();
    }, [page, filters]);

    const fetchAudits = async () => {
        setLoading(true);
        setError(null);

        try {
            const params = new URLSearchParams({
                skip: page * limit,
                limit,
                ...Object.fromEntries(Object.entries(filters).filter(([_, v]) => v))
            });

            const response = await fetch(`/api/audit?${params}`, {
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('token')}`
                }
            });

            if (!response.ok) {
                throw new Error('Failed to fetch audits');
            }

            const data = await response.json();
            setAudits(data.entries);
            setTotal(data.total);
        } catch (err) {
            setError({
                title: 'Failed to Load Audits',
                message: err.message,
                severity: 'error'
            });
        } finally {
            setLoading(false);
        }
    };

    const formatDuration = (ms) => {
        if (ms < 1000) return `${ms}ms`;
        return `${(ms / 1000).toFixed(1)}s`;
    };

    const formatTimestamp = (timestamp) => {
        return new Date(timestamp).toLocaleString();
    };

    return (
        <div className="p-6">
            <h1 className="text-2xl font-bold mb-6">Audit Log</h1>

            <ErrorAlert error={error} onDismiss={() => setError(null)} />

            {/* Filters */}
            <div className="bg-white rounded-lg shadow p-4 mb-6">
                <div className="grid grid-cols-3 gap-4">
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                            Action
                        </label>
                        <input
                            type="text"
                            value={filters.action_id}
                            onChange={(e) => setFilters({ ...filters, action_id: e.target.value })}
                            placeholder="Filter by action ID..."
                            className="w-full px-3 py-2 border border-gray-300 rounded"
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                            User
                        </label>
                        <input
                            type="text"
                            value={filters.username}
                            onChange={(e) => setFilters({ ...filters, username: e.target.value })}
                            placeholder="Filter by username..."
                            className="w-full px-3 py-2 border border-gray-300 rounded"
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                            Status
                        </label>
                        <select
                            value={filters.status}
                            onChange={(e) => setFilters({ ...filters, status: e.target.value })}
                            className="w-full px-3 py-2 border border-gray-300 rounded"
                        >
                            <option value="">All</option>
                            <option value="success">Success</option>
                            <option value="fail">Failed</option>
                        </select>
                    </div>
                </div>
            </div>

            {/* Table */}
            <div className="bg-white rounded-lg shadow overflow-hidden">
                <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                        <tr>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                Time
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                User
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                Action
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                Status
                            </th>
                            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                Duration
                            </th>
                        </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                        {loading ? (
                            <tr>
                                <td colSpan="5" className="px-6 py-4 text-center text-gray-500">
                                    Loading...
                                </td>
                            </tr>
                        ) : audits.length === 0 ? (
                            <tr>
                                <td colSpan="5" className="px-6 py-4 text-center text-gray-500">
                                    No audit entries found
                                </td>
                            </tr>
                        ) : (
                            audits.map((audit) => (
                                <tr key={audit.id} className="hover:bg-gray-50">
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                        {formatTimestamp(audit.created_at)}
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                                        <div className="font-medium text-gray-900">{audit.username}</div>
                                        <div className="text-gray-500">{audit.role}</div>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                                        <div className="font-medium text-gray-900">{audit.action_title}</div>
                                        <div className="text-gray-500 text-xs font-mono">{audit.action_id}</div>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap">
                                        {audit.status === 'success' ? (
                                            <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">
                                                ✓ Success
                                            </span>
                                        ) : (
                                            <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-red-100 text-red-800">
                                                ✗ Failed
                                            </span>
                                        )}
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                        {formatDuration(audit.duration_ms)}
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>

            {/* Pagination */}
            <div className="mt-4 flex justify-between items-center">
                <div className="text-sm text-gray-700">
                    Showing {page * limit + 1} to {Math.min((page + 1) * limit, total)} of {total} entries
                </div>
                <div className="flex gap-2">
                    <button
                        onClick={() => setPage(p => Math.max(0, p - 1))}
                        disabled={page === 0}
                        className="px-4 py-2 border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        ← Previous
                    </button>
                    <button
                        onClick={() => setPage(p => p + 1)}
                        disabled={(page + 1) * limit >= total}
                        className="px-4 py-2 border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        Next →
                    </button>
                </div>
            </div>
        </div>
    );
}
