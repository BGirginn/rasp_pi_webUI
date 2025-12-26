import { useState, useEffect } from 'react'
import { api } from '../services/api'

// Job status badge
function JobStatusBadge({ state }) {
    const styles = {
        pending: 'bg-yellow-500/20 text-yellow-400',
        running: 'bg-blue-500/20 text-blue-400',
        completed: 'bg-green-500/20 text-green-400',
        failed: 'bg-red-500/20 text-red-400',
        cancelled: 'bg-gray-500/20 text-gray-400',
    }

    const icons = {
        pending: '⏳',
        running: '▶️',
        completed: '✅',
        failed: '❌',
        cancelled: '🚫',
    }

    return (
        <span className={`px-2 py-1 rounded-full text-xs font-medium ${styles[state]}`}>
            {icons[state]} {state}
        </span>
    )
}

// Job card component
function JobCard({ job }) {
    const [expanded, setExpanded] = useState(false)

    const typeIcons = {
        backup: '💾',
        restore: '📥',
        update: '🔄',
        cleanup: '🧹',
        healthcheck: '🩺',
    }

    return (
        <div className="glass-card rounded-xl p-5 animate-slide-in">
            <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                    <span className="text-2xl">{typeIcons[job.type] || '📋'}</span>
                    <div>
                        <h3 className="font-semibold text-gray-100">{job.name}</h3>
                        <p className="text-sm text-gray-500">{job.type}</p>
                    </div>
                </div>
                <JobStatusBadge state={job.state} />
            </div>

            {/* Progress bar for running jobs */}
            {job.state === 'running' && (
                <div className="mb-3">
                    <div className="flex justify-between text-sm mb-1">
                        <span className="text-gray-400">Progress</span>
                        <span className="text-gray-100">{job.progress || 0}%</span>
                    </div>
                    <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                        <div
                            className="h-full bg-primary-500 rounded-full transition-all animate-pulse"
                            style={{ width: `${job.progress || 0}%` }}
                        />
                    </div>
                </div>
            )}

            {/* Timestamps */}
            <div className="flex gap-4 text-xs text-gray-500 mb-3">
                {job.started_at && (
                    <span>Started: {new Date(job.started_at).toLocaleString()}</span>
                )}
                {job.completed_at && (
                    <span>Completed: {new Date(job.completed_at).toLocaleString()}</span>
                )}
            </div>

            <div className="flex gap-2">
                <button
                    onClick={() => setExpanded(!expanded)}
                    className="btn btn-ghost text-sm py-1 px-3"
                >
                    {expanded ? 'Hide Details' : 'Show Details'}
                </button>
            </div>

            {/* Expanded config/result */}
            {expanded && (
                <div className="mt-4 p-3 bg-gray-800/50 rounded-lg animate-fade-in">
                    {job.config && (
                        <div className="mb-3">
                            <p className="text-xs text-gray-500 mb-1">Configuration</p>
                            <pre className="text-xs text-gray-300 overflow-auto">
                                {JSON.stringify(job.config, null, 2)}
                            </pre>
                        </div>
                    )}
                    {job.result && (
                        <div className="mb-3">
                            <p className="text-xs text-gray-500 mb-1">Result</p>
                            <pre className="text-xs text-gray-300 overflow-auto">
                                {JSON.stringify(job.result, null, 2)}
                            </pre>
                        </div>
                    )}
                    {job.error && (
                        <div className="p-2 bg-red-500/10 border border-red-500/30 rounded text-red-400 text-sm">
                            {job.error}
                        </div>
                    )}
                </div>
            )}
        </div>
    )
}

export default function Jobs() {
    const [jobs, setJobs] = useState([])
    const [loading, setLoading] = useState(true)
    const [filter, setFilter] = useState('all')

    useEffect(() => {
        loadJobs()
        // Refresh running jobs
        const interval = setInterval(loadJobs, 5000)
        return () => clearInterval(interval)
    }, [])

    async function loadJobs() {
        try {
            const response = await api.get('/jobs?limit=100')
            setJobs(response.data)
        } catch (err) {
            console.error('Failed to load jobs:', err)
        } finally {
            setLoading(false)
        }
    }

    // Filter jobs
    const filteredJobs = filter === 'all'
        ? jobs
        : jobs.filter((j) => j.state === filter)

    // Job counts
    const counts = {
        all: jobs.length,
        pending: jobs.filter((j) => j.state === 'pending').length,
        running: jobs.filter((j) => j.state === 'running').length,
        completed: jobs.filter((j) => j.state === 'completed').length,
        failed: jobs.filter((j) => j.state === 'failed').length,
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-500"></div>
            </div>
        )
    }

    return (
        <div className="space-y-6 animate-fade-in">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <h2 className="text-2xl font-bold text-gray-100">Jobs</h2>
                <div className="flex gap-3">
                    <button onClick={loadJobs} className="btn btn-secondary">
                        🔄 Refresh
                    </button>
                </div>
            </div>

            {/* Filters */}
            <div className="flex gap-2 flex-wrap">
                {Object.entries(counts).map(([key, count]) => (
                    <button
                        key={key}
                        onClick={() => setFilter(key)}
                        className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${filter === key
                                ? 'bg-primary-600 text-white'
                                : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                            }`}
                    >
                        {key.charAt(0).toUpperCase() + key.slice(1)}
                        <span className="ml-2 px-2 py-0.5 rounded-full bg-gray-700 text-xs">
                            {count}
                        </span>
                    </button>
                ))}
            </div>

            {/* Jobs Grid */}
            {filteredJobs.length > 0 ? (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    {filteredJobs.map((job) => (
                        <JobCard key={job.id} job={job} />
                    ))}
                </div>
            ) : (
                <div className="glass-card rounded-xl p-8 text-center">
                    <span className="text-5xl mb-4 block">⏰</span>
                    <h3 className="text-xl font-semibold text-gray-100 mb-2">No jobs found</h3>
                    <p className="text-gray-500">
                        {filter === 'all'
                            ? 'Create a new job to get started'
                            : `No ${filter} jobs`}
                    </p>
                </div>
            )}

        </div>
    )
}
