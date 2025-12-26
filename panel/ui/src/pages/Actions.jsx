import { useEffect, useMemo, useState } from 'react'
import { api } from '../services/api'

const riskStyles = {
    low: 'bg-green-500/10 text-green-400 border-green-500/20',
    medium: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
    high: 'bg-red-500/10 text-red-400 border-red-500/20',
}

function buildDefaultParams(schema) {
    const params = {}
    if (!schema) return params
    Object.entries(schema).forEach(([key, def]) => {
        if (def && Object.prototype.hasOwnProperty.call(def, 'default')) {
            params[key] = def.default
        }
    })
    return params
}

function ActionRunModal({ action, onClose, onRun }) {
    const [confirm, setConfirm] = useState(false)
    const [paramsText, setParamsText] = useState(() => {
        const defaults = buildDefaultParams(action.params_schema)
        return JSON.stringify(defaults, null, 2)
    })
    const [error, setError] = useState(null)

    const handleSubmit = () => {
        setError(null)
        let params = {}
        if (action.params_schema && Object.keys(action.params_schema).length > 0) {
            try {
                params = paramsText ? JSON.parse(paramsText) : {}
            } catch (err) {
                setError('Params must be valid JSON')
                return
            }
        }
        onRun({ actionId: action.id, params, confirm })
    }

    return (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
            <div className="glass-card rounded-2xl p-6 w-full max-w-lg animate-slide-in">
                <div className="flex items-start justify-between mb-4">
                    <div>
                        <p className="text-xs text-gray-500">{action.category}</p>
                        <h2 className="text-xl font-semibold text-gray-100">{action.title}</h2>
                        <p className="text-xs text-gray-500 mt-1">{action.id}</p>
                    </div>
                    <span className={`px-2 py-1 rounded-full text-xs border ${riskStyles[action.risk] || 'border-gray-700 text-gray-400'}`}>
                        {action.risk}
                    </span>
                </div>

                {action.params_schema && Object.keys(action.params_schema).length > 0 && (
                    <div className="mb-4">
                        <label className="text-sm text-gray-400 block mb-2">Params (JSON)</label>
                        <textarea
                            value={paramsText}
                            onChange={(e) => setParamsText(e.target.value)}
                            className="input font-mono text-xs h-32"
                        />
                    </div>
                )}

                {action.requires_confirmation && (
                    <div className="flex items-center gap-2 mb-4">
                        <input
                            type="checkbox"
                            checked={confirm}
                            onChange={(e) => setConfirm(e.target.checked)}
                        />
                        <span className="text-sm text-yellow-400">Confirmation required</span>
                    </div>
                )}

                {error && (
                    <div className="p-2 mb-4 rounded bg-red-500/20 border border-red-500/30 text-red-400 text-sm">
                        {error}
                    </div>
                )}

                <div className="flex gap-3">
                    <button onClick={handleSubmit} className="btn btn-primary flex-1">Run Action</button>
                    <button onClick={onClose} className="btn btn-secondary">Cancel</button>
                </div>
            </div>
        </div>
    )
}

export default function Actions() {
    const [actions, setActions] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)
    const [activeAction, setActiveAction] = useState(null)
    const [rollbackInfo, setRollbackInfo] = useState(null)

    useEffect(() => {
        loadActions()
    }, [])

    async function loadActions() {
        try {
            setLoading(true)
            const response = await api.get('/actions')
            setActions(response.data)
        } catch (err) {
            setError('Failed to load actions')
        } finally {
            setLoading(false)
        }
    }

    const grouped = useMemo(() => {
        const byCategory = {}
        actions.forEach((action) => {
            const key = action.category || 'misc'
            if (!byCategory[key]) byCategory[key] = []
            byCategory[key].push(action)
        })
        return byCategory
    }, [actions])

    async function runAction({ actionId, params, confirm }) {
        try {
            const response = await api.post('/actions/execute', {
                action_id: actionId,
                params,
                confirm,
            })
            if (response.data.rollback) {
                setRollbackInfo(response.data.rollback)
            } else {
                setRollbackInfo(null)
            }
        } catch (err) {
            alert(err.message)
        } finally {
            setActiveAction(null)
        }
    }

    async function confirmRollback() {
        if (!rollbackInfo?.job_id) return
        try {
            await api.post('/actions/confirm', { rollback_job_id: rollbackInfo.job_id })
            setRollbackInfo(null)
        } catch (err) {
            alert(err.message)
        }
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary-500"></div>
            </div>
        )
    }

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-white">Actions</h1>
                <p className="text-sm text-gray-500">Execute registry actions by category.</p>
            </div>

            {rollbackInfo && (
                <div className="p-4 rounded-xl border border-yellow-500/30 bg-yellow-500/10 text-yellow-300">
                    <p className="text-sm">This change will rollback in {rollbackInfo.due_in_seconds}s if not confirmed.</p>
                    <button onClick={confirmRollback} className="btn btn-secondary mt-3">Confirm Change</button>
                </div>
            )}

            {error && (
                <div className="p-3 rounded bg-red-500/20 border border-red-500/30 text-red-400 text-sm">
                    {error}
                </div>
            )}

            {Object.entries(grouped).map(([category, items]) => (
                <div key={category} className="space-y-3">
                    <h2 className="text-sm uppercase tracking-wider text-gray-500">{category}</h2>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {items.map((action) => (
                            <div key={action.id} className="glass-card rounded-xl p-5">
                                <div className="flex items-start justify-between">
                                    <div>
                                        <h3 className="font-semibold text-gray-100">{action.title}</h3>
                                        <p className="text-xs text-gray-500 mt-1">{action.id}</p>
                                    </div>
                                    <span className={`px-2 py-1 rounded-full text-xs border ${riskStyles[action.risk] || 'border-gray-700 text-gray-400'}`}>
                                        {action.risk}
                                    </span>
                                </div>
                                <div className="mt-4 flex items-center justify-between">
                                    <span className="text-xs text-gray-500">
                                        {action.requires_confirmation ? 'Confirmation required' : 'No confirmation'}
                                    </span>
                                    <button
                                        onClick={() => setActiveAction(action)}
                                        className="btn btn-primary text-sm"
                                    >
                                        Run
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            ))}

            {activeAction && (
                <ActionRunModal
                    action={activeAction}
                    onClose={() => setActiveAction(null)}
                    onRun={runAction}
                />
            )}
        </div>
    )
}
