import { useState, useEffect } from 'react'
import { api } from '../services/api'
import { useAuth } from '../hooks/useAuth'

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
function JobCard({ job, onAction }) {
    const [expanded, setExpanded] = useState(false)
    const [logs, setLogs] = useState([])
    const [logsLoading, setLogsLoading] = useState(false)

    const typeIcons = {
        backup: '💾',
        restore: '📥',
        update: '🔄',
        cleanup: '🧹',
        healthcheck: '🩺',
    }

    useEffect(() => {
        let eventSource

        async function loadLogs() {
            setLogsLoading(true)
            try {
                const response = await api.get(`/jobs/${job.id}/logs`)
                setLogs(response.data)
            } catch (err) {
                console.error('Failed to load job logs:', err)
            } finally {
                setLogsLoading(false)
            }
        }

        if (expanded) {
            loadLogs()
            const token = localStorage.getItem('access_token')
            const url = `/api/jobs/${job.id}/stream${token ? `?token=${token}` : ''}`
            eventSource = new EventSource(url, { withCredentials: true })

            eventSource.addEventListener('job_update', (event) => {
                try {
                    const data = JSON.parse(event.data)
                    if (data.logs) {
                        setLogs(data.logs)
                    }
                } catch (e) {
                    console.error('Failed to parse job stream data:', e)
                }
            })

            eventSource.onerror = () => {
                if (eventSource) eventSource.close()
            }
        }

        return () => {
            if (eventSource) eventSource.close()
        }
    }, [expanded, job.id])

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

            {/* Actions */}
            <div className="flex gap-2">
                {job.state === 'pending' && (
                    <button
                        onClick={() => onAction(job.id, 'run')}
                        className="btn btn-primary text-sm py-1 px-3"
                    >
                        ▶️ Run Now
                    </button>
                )}
                {job.state === 'running' && (
                    <button
                        onClick={() => onAction(job.id, 'cancel')}
                        className="btn btn-danger text-sm py-1 px-3"
                    >
                        ⏹️ Cancel
                    </button>
                )}
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
                    <div className="mt-3">
                        <p className="text-xs text-gray-500 mb-1">Logs</p>
                        {logsLoading ? (
                            <div className="text-xs text-gray-400">Loading logs...</div>
                        ) : logs.length > 0 ? (
                            <div className="max-h-48 overflow-auto text-xs text-gray-300 bg-gray-900/40 rounded p-2">
                                {logs.map((entry, index) => (
                                    <div key={`${entry.created_at}-${index}`} className="mb-1">
                                        <span className="text-gray-500 mr-2">[{entry.level}]</span>
                                        <span>{entry.message}</span>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="text-xs text-gray-400">No logs yet.</div>
                        )}
                    </div>
                </div>
            )}
        </div>
    )
}

// Create job modal
function CreateJobModal({ types, onClose, onCreate }) {
    const [name, setName] = useState('')
    const [type, setType] = useState('')
    const [config, setConfig] = useState({})

    const handleSubmit = (e) => {
        e.preventDefault()
        onCreate({ name, type, config })
    }

    const selectedType = types[type]

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="glass-card rounded-2xl p-6 w-full max-w-md animate-slide-in">
                <h2 className="text-xl font-semibold text-gray-100 mb-4">Create Job</h2>

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-gray-400 mb-1">
                            Job Name
                        </label>
                        <input
                            type="text"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            className="input"
                            placeholder="e.g., Daily Backup"
                            required
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-400 mb-1">
                            Job Type
                        </label>
                        <select
                            value={type}
                            onChange={(e) => setType(e.target.value)}
                            className="input"
                            required
                        >
                            <option value="">Select type...</option>
                            {Object.entries(types).map(([key, value]) => (
                                <option key={key} value={key}>
                                    {value.name}
                                </option>
                            ))}
                        </select>
                    </div>

                    {selectedType && (
                        <div className="p-3 bg-gray-800/50 rounded-lg">
                            <p className="text-sm text-gray-400 mb-2">{selectedType.description}</p>
                            {Object.entries(selectedType.config_schema || {}).map(([key, schema]) => (
                                <div key={key} className="mb-2">
                                    <label className="flex items-center gap-2 text-sm text-gray-300">
                                        {schema.type === 'boolean' ? (
                                            <input
                                                type="checkbox"
                                                checked={config[key] ?? schema.default}
                                                onChange={(e) => setConfig({ ...config, [key]: e.target.checked })}
                                                className="rounded"
                                            />
                                        ) : (
                                            <input
                                                type={schema.type === 'integer' ? 'number' : 'text'}
                                                value={config[key] ?? schema.default ?? ''}
                                                onChange={(e) => setConfig({ ...config, [key]: e.target.value })}
                                                className="input w-32"
                                            />
                                        )}
                                        {key.replace(/_/g, ' ')}
                                    </label>
                                </div>
                            ))}
                        </div>
                    )}

                    <div className="flex gap-3">
                        <button type="submit" className="btn btn-primary flex-1">
                            Create Job
                        </button>
                        <button type="button" onClick={onClose} className="btn btn-secondary">
                            Cancel
                        </button>
                    </div>
                </form>
            </div>
        </div>
    )
}

export default function Jobs() {
    const { isOperator } = useAuth()
    const [jobs, setJobs] = useState([])
    const [jobTypes, setJobTypes] = useState({})
    const [loading, setLoading] = useState(true)
    const [filter, setFilter] = useState('all')
    const [showCreate, setShowCreate] = useState(false)

    useEffect(() => {
        loadJobs()
        loadJobTypes()

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

    async function loadJobTypes() {
        try {
            const response = await api.get('/jobs/types')
            setJobTypes(response.data)
        } catch (err) {
            console.error('Failed to load job types:', err)
        }
    }

    async function handleAction(jobId, action) {
        try {
            await api.post(`/jobs/${jobId}/${action}`)
            await loadJobs()
        } catch (err) {
            console.error(`Failed to ${action} job:`, err)
            alert(`Failed to ${action} job: ${err.message}`)
        }
    }

    async function handleCreate(jobData) {
        try {
            await api.post('/jobs', jobData)
            setShowCreate(false)
            await loadJobs()
        } catch (err) {
            console.error('Failed to create job:', err)
            alert(`Failed to create job: ${err.message}`)
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
                    {isOperator && (
                        <button onClick={() => setShowCreate(true)} className="btn btn-primary">
                            ➕ Create Job
                        </button>
                    )}
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
                        <JobCard key={job.id} job={job} onAction={handleAction} />
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

            {/* Create Job Modal */}
            {showCreate && (
                <CreateJobModal
                    types={jobTypes}
                    onClose={() => setShowCreate(false)}
                    onCreate={handleCreate}
                />
            )}
        </div>
    )
}
