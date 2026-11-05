import { useCallback, useEffect, useRef, useState } from 'react';
import {
    Activity,
    ArrowUpRight,
    CheckCircle2,
    FileText,
    GitBranch,
    Play,
    RefreshCw,
    RotateCcw,
    Search,
    Server,
    Shield,
    Square,
    X,
} from 'lucide-react';
import { api } from '../services/api';
import { useAuth } from '../hooks/useAuth';

const messageFor = (error) =>
    typeof error.response?.data?.detail === 'string' ? error.response.data.detail : error.message;
const stateLabels = {
    running: 'Running',
    stopped: 'Stopped',
    failed: 'Failed',
    starting: 'Starting',
    stopping: 'Stopping',
    restarting: 'Restarting',
};

export function ServicesPage() {
    const { isAdmin, isOperator } = useAuth();
    const [services, setServices] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [notice, setNotice] = useState('');
    const [filter, setFilter] = useState('all');
    const [search, setSearch] = useState('');
    const [resourceClass, setResourceClass] = useState('all');
    const [selectedId, setSelectedId] = useState(null);
    const [detailTab, setDetailTab] = useState('logs');
    const [details, setDetails] = useState(null);
    const [detailError, setDetailError] = useState('');
    const [detailRefresh, setDetailRefresh] = useState(0);
    const [pendingAction, setPendingAction] = useState(null);
    const [busyId, setBusyId] = useState('');
    const [updatedAt, setUpdatedAt] = useState(null);
    const requestId = useRef(0);
    const actionBusy = useRef(false);

    const load = useCallback(async () => {
        const request = ++requestId.current;
        try {
            const response = await api.get('/resources', { cache: false });
            if (!Array.isArray(response.data)) throw new Error('Unexpected service response');
            if (request !== requestId.current) return;
            setServices(response.data);
            setUpdatedAt(new Date());
            setError('');
            return response.data;
        } catch (failure) {
            if (request === requestId.current) setError(messageFor(failure));
        } finally {
            if (request === requestId.current) setLoading(false);
        }
    }, []);

    useEffect(() => {
        load();
        const timer = setInterval(() => {
            if (!document.hidden && !actionBusy.current) load();
        }, 10000);
        return () => {
            clearInterval(timer);
            requestId.current += 1;
        };
    }, [load]);

    useEffect(() => {
        if (!selectedId) return;
        let cancelled = false;
        setDetails(null);
        setDetailError('');
        const path =
            detailTab === 'logs'
                ? `/logs/${encodeURIComponent(selectedId)}?tail=120`
                : `/resources/${encodeURIComponent(selectedId)}/dependencies`;
        api.get(path, { cache: false })
            .then((response) => {
                if (!cancelled) setDetails(response.data);
            })
            .catch((failure) => {
                if (!cancelled) setDetailError(messageFor(failure));
            });
        return () => {
            cancelled = true;
        };
    }, [selectedId, detailTab, detailRefresh]);

    const canAct = (service, action) =>
        isOperator &&
        service.resource_class !== 'CORE' &&
        (service.resource_class !== 'SYSTEM' || isAdmin) &&
        (service.allowed_actions || []).includes(action);

    const execute = async (service, action) => {
        setPendingAction(null);
        setBusyId(service.id);
        actionBusy.current = true;
        requestId.current += 1;
        setError('');
        setNotice('');
        try {
            const response = await api.post(`/resources/${encodeURIComponent(service.id)}/action`, { action });
            const confirmed = response.data?.data?.resource || (await load())?.find((item) => item.id === service.id);
            const expected = action === 'stop' ? 'stopped' : 'running';
            if (!confirmed || confirmed.state !== expected)
                throw new Error(`The service has not reached ${expected}; inspect its logs.`);
            setServices((current) => current.map((item) => (item.id === service.id ? confirmed : item)));
            setNotice(
                `${service.name} ${action === 'stop' ? 'stopped' : action === 'start' ? 'started' : 'restarted'} successfully`
            );
            setUpdatedAt(new Date());
            setDetailRefresh((value) => value + 1);
        } catch (failure) {
            setError(messageFor(failure));
        } finally {
            actionBusy.current = false;
            setBusyId('');
        }
    };

    const selected = services.find((service) => service.id === selectedId);
    const visible = services
        .filter(
            (service) =>
                (filter === 'all' || service.state === filter) &&
                (resourceClass === 'all' || service.resource_class === resourceClass) &&
                service.name.toLowerCase().includes(search.toLowerCase())
        )
        .sort((a, b) => Number(b.state === 'failed') - Number(a.state === 'failed') || a.name.localeCompare(b.name));
    const counts = {
        all: services.length,
        running: services.filter((item) => item.state === 'running').length,
        failed: services.filter((item) => item.state === 'failed').length,
        stopped: services.filter((item) => item.state === 'stopped').length,
    };

    return (
        <div className="management-page" aria-label="Services workspace">
            <div className="operations-overview">
                <div>
                    <span className="eyebrow">WORKLOAD INVENTORY</span>
                    <h2>Everything running. One place.</h2>
                    <p>Inspect system services, read their logs and apply verified actions.</p>
                </div>
                <div className="observation">
                    <span className={`status-dot ${error ? 'is-warning' : ''}`} />
                    {updatedAt ? `Observed ${updatedAt.toLocaleTimeString()}` : 'Connecting to host'}
                    <button
                        className="control-button icon-only"
                        aria-label="Refresh services"
                        disabled={Boolean(busyId)}
                        onClick={load}
                    >
                        <RefreshCw size={16} />
                    </button>
                </div>
            </div>
            <div className="metric-strip">
                {[
                    ['all', 'All services'],
                    ['running', 'Running'],
                    ['failed', 'Need attention'],
                    ['stopped', 'Stopped'],
                ].map(([key, label]) => (
                    <button
                        key={key}
                        className={`metric-cell ${filter === key ? 'is-active' : ''}`}
                        onClick={() => setFilter(key)}
                    >
                        <span>{label}</span>
                        <strong className={key === 'failed' && counts[key] ? 'danger-text' : ''}>{counts[key]}</strong>
                        <Activity size={16} />
                    </button>
                ))}
            </div>
            {error && (
                <p role="alert" className="operation-notice is-error">
                    {error} {updatedAt && 'The last successful observation is still shown.'}
                </p>
            )}
            {notice && (
                <p role="status" className="operation-notice is-success">
                    <CheckCircle2 size={16} />
                    {notice}
                </p>
            )}
            {pendingAction && (
                <section className="confirmation-panel" aria-label="Confirm service action">
                    <div>
                        <strong>Stop {pendingAction.name}?</strong>
                        <p>This interrupts the workload until it is started again.</p>
                    </div>
                    <button className="control-button" onClick={() => setPendingAction(null)}>
                        Cancel
                    </button>
                    <button className="control-button is-danger" onClick={() => execute(pendingAction, 'stop')}>
                        Confirm stop
                    </button>
                </section>
            )}
            <div className={`workspace-grid ${selected ? 'has-inspector' : ''}`}>
                <section className="workspace-panel">
                    <div className="workspace-toolbar">
                        <label className="search-field">
                            <Search size={17} />
                            <input
                                aria-label="Search services"
                                placeholder="Find a service…"
                                value={search}
                                onChange={(event) => setSearch(event.target.value)}
                            />
                        </label>
                        <select
                            aria-label="Service class"
                            value={resourceClass}
                            onChange={(event) => setResourceClass(event.target.value)}
                        >
                            <option value="all">Any class</option>
                            <option value="APP">Applications</option>
                            <option value="SYSTEM">System</option>
                            <option value="CORE">Protected core</option>
                        </select>
                        <span className="muted-text">{visible.length} shown</span>
                    </div>
                    <div className="table-scroll">
                        <table className="operations-table">
                            <thead>
                                <tr>
                                    <th>Service</th>
                                    <th>State</th>
                                    <th>Startup</th>
                                    <th>CPU / RAM</th>
                                    <th className="align-right">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {visible.map((service) => (
                                    <tr key={service.id} className={selectedId === service.id ? 'is-selected' : ''}>
                                        <td>
                                            <button
                                                className="entity-button"
                                                aria-label={`Inspect ${service.name}`}
                                                onClick={() => setSelectedId(service.id)}
                                            >
                                                <span className="entity-icon">
                                                    <Server size={17} />
                                                </span>
                                                <span>
                                                    <strong>{service.name}</strong>
                                                    <small>
                                                        {service.provider} <span className="inline-separator">/</span>{' '}
                                                        {service.resource_class.toLowerCase()}
                                                    </small>
                                                </span>
                                                <ArrowUpRight size={14} className="entity-arrow" />
                                            </button>
                                        </td>
                                        <td>
                                            <span className={`state-badge state-${service.state}`}>
                                                <i />
                                                {busyId === service.id
                                                    ? 'Applying action…'
                                                    : stateLabels[service.state] || 'Unknown'}
                                            </span>
                                        </td>
                                        <td>
                                            <span className="subtle-badge">{service.unit_file_state || 'Unknown'}</span>
                                        </td>
                                        <td className="numeric-cell">
                                            {service.cpu_usage == null ? '—' : `${service.cpu_usage.toFixed(1)}%`}
                                            <small>
                                                {service.memory_usage == null
                                                    ? '—'
                                                    : `${service.memory_usage.toFixed(1)}% RAM`}
                                            </small>
                                        </td>
                                        <td>
                                            <div className="row-actions">
                                                {service.resource_class === 'CORE' && (
                                                    <span className="protected-label">
                                                        <Shield size={13} />
                                                        Protected
                                                    </span>
                                                )}
                                                {service.state !== 'running' && canAct(service, 'start') && (
                                                    <button
                                                        className="control-button icon-only"
                                                        aria-label={`Start ${service.name}`}
                                                        title="Start"
                                                        disabled={Boolean(busyId)}
                                                        onClick={() => execute(service, 'start')}
                                                    >
                                                        <Play size={15} />
                                                    </button>
                                                )}
                                                {service.state === 'running' && canAct(service, 'stop') && (
                                                    <button
                                                        className="control-button icon-only"
                                                        aria-label={`Stop ${service.name}`}
                                                        title="Stop"
                                                        disabled={Boolean(busyId)}
                                                        onClick={() => setPendingAction(service)}
                                                    >
                                                        <Square size={14} />
                                                    </button>
                                                )}
                                                {canAct(service, 'restart') && (
                                                    <button
                                                        className="control-button icon-only"
                                                        aria-label={`Restart ${service.name}`}
                                                        title="Restart"
                                                        disabled={Boolean(busyId)}
                                                        onClick={() => execute(service, 'restart')}
                                                    >
                                                        <RotateCcw size={15} />
                                                    </button>
                                                )}
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                    {!visible.length && (
                        <div className="workspace-empty">
                            <Server size={28} />
                            <h3>
                                {loading
                                    ? 'Reading services…'
                                    : services.length
                                      ? 'No matching services'
                                      : 'No services available'}
                            </h3>
                            <p>
                                {error ? 'Retry the host connection.' : 'Change the filters or refresh the inventory.'}
                            </p>
                        </div>
                    )}
                </section>
                {selected && (
                    <aside className="workspace-panel inspector">
                        <header>
                            <div>
                                <span className="eyebrow">SERVICE INSPECTOR</span>
                                <h2>{selected.name}</h2>
                            </div>
                            <button
                                className="control-button icon-only"
                                aria-label="Close service details"
                                onClick={() => setSelectedId(null)}
                            >
                                <X size={17} />
                            </button>
                        </header>
                        <dl className="detail-grid">
                            <div>
                                <dt>State</dt>
                                <dd>{stateLabels[selected.state] || selected.state}</dd>
                            </div>
                            <div>
                                <dt>Protection</dt>
                                <dd>{selected.resource_class}</dd>
                            </div>
                            <div>
                                <dt>Startup</dt>
                                <dd>{selected.unit_file_state || 'Unknown'}</dd>
                            </div>
                            <div>
                                <dt>Source</dt>
                                <dd>{selected.provider}</dd>
                            </div>
                        </dl>
                        <div className="detail-tabs">
                            <button
                                className={detailTab === 'logs' ? 'is-active' : ''}
                                onClick={() => setDetailTab('logs')}
                            >
                                <FileText size={15} />
                                Logs
                            </button>
                            <button
                                className={detailTab === 'dependencies' ? 'is-active' : ''}
                                onClick={() => setDetailTab('dependencies')}
                            >
                                <GitBranch size={15} />
                                Dependencies
                            </button>
                            <button
                                className="detail-refresh"
                                aria-label="Refresh logs"
                                onClick={() => setDetailRefresh((value) => value + 1)}
                            >
                                <RefreshCw size={15} />
                            </button>
                        </div>
                        {detailError ? (
                            <p className="operation-notice is-error" role="alert">
                                {detailError}
                            </p>
                        ) : details === null ? (
                            <p className="inspector-loading">Reading {detailTab}…</p>
                        ) : detailTab === 'logs' ? (
                            <div className="log-view" aria-label="Service logs">
                                {details.lines?.length ? (
                                    details.lines.map((line, index) => (
                                        <div key={index}>
                                            <time>{line.timestamp}</time>
                                            <span className={`log-level level-${line.level?.toLowerCase()}`}>
                                                {line.level}
                                            </span>
                                            <span>{line.message}</span>
                                        </div>
                                    ))
                                ) : (
                                    <p>No log entries were returned.</p>
                                )}
                            </div>
                        ) : (
                            <div className="dependency-view">
                                {['requires', 'wants', 'after', 'before'].map((key) => (
                                    <div key={key}>
                                        <h3>{key}</h3>
                                        {details[key]?.length ? (
                                            <ul>
                                                {details[key].map((name) => (
                                                    <li key={name}>{name}</li>
                                                ))}
                                            </ul>
                                        ) : (
                                            <p>None reported</p>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                    </aside>
                )}
            </div>
        </div>
    );
}
