import { AnimatePresence, motion } from 'motion/react';
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Archive,
  Check,
  CheckCircle2,
  ChevronDown,
  CircleDot,
  Clock3,
  HeartPulse,
  ListTodo,
  LoaderCircle,
  Play,
  Plus,
  RefreshCw,
  RotateCw,
  Square,
  TerminalSquare,
  Trash2,
  X,
  XCircle,
} from 'lucide-react';
import { api } from '../services/api';
import { useAuth } from '../hooks/useAuth';

const typeMeta = {
  backup: { label: 'Backup', icon: Archive },
  restore: { label: 'Restore', icon: RotateCw },
  update: { label: 'Update', icon: RefreshCw },
  cleanup: { label: 'Cleanup', icon: Trash2 },
  healthcheck: { label: 'Health check', icon: HeartPulse },
};

const stateMeta = {
  pending: { label: 'Pending', icon: Clock3 },
  running: { label: 'Running', icon: LoaderCircle },
  completed: { label: 'Completed', icon: CheckCircle2 },
  failed: { label: 'Failed', icon: XCircle },
  cancelled: { label: 'Cancelled', icon: CircleDot },
};

function formatDate(value) {
  if (!value) return 'Not started';
  return new Date(value).toLocaleString('tr-TR', {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
}

function JobStatus({ state }) {
  const meta = stateMeta[state] || stateMeta.pending;
  const Icon = meta.icon;
  return (
    <span className={`job-status status-${state || 'pending'}`}>
      <Icon size={14} className={state === 'running' ? 'animate-spin' : ''} />
      {meta.label}
    </span>
  );
}

function JsonBlock({ label, value }) {
  if (!value || (typeof value === 'object' && Object.keys(value).length === 0)) return null;
  return (
    <div className="job-data-block">
      <span>{label}</span>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </div>
  );
}

function JobRow({ job, onAction, actionBusy }) {
  const [expanded, setExpanded] = useState(false);
  const [logs, setLogs] = useState([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const meta = typeMeta[job.type] || { label: job.type, icon: ListTodo };
  const TypeIcon = meta.icon;

  useEffect(() => {
    let eventSource;

    async function loadLogs() {
      setLogsLoading(true);
      try {
        const response = await api.get(`/jobs/${job.id}/logs`);
        setLogs(response.data || []);
      } catch (error) {
        console.error('Failed to load job logs:', error);
      } finally {
        setLogsLoading(false);
      }
    }

    if (expanded) {
      loadLogs();
      const token = localStorage.getItem('access_token');
      const url = `/api/jobs/${job.id}/stream${token ? `?token=${token}` : ''}`;
      eventSource = new EventSource(url, { withCredentials: true });
      eventSource.addEventListener('job_update', (event) => {
        try {
          const update = JSON.parse(event.data);
          if (update.logs) setLogs(update.logs);
        } catch (error) {
          console.error('Failed to parse job stream data:', error);
        }
      });
      eventSource.onerror = () => eventSource?.close();
    }

    return () => eventSource?.close();
  }, [expanded, job.id]);

  const timestamp = job.completed_at || job.started_at || job.created_at;
  const canCancel = job.state === 'running' && (job.cancellable ?? true);

  return (
    <motion.article layout className={`job-row ${expanded ? 'is-expanded' : ''}`}>
      <div className="job-row-main">
        <div className="job-type-icon"><TypeIcon size={19} /></div>
        <div className="job-identity">
          <strong>{job.name}</strong>
          <span>{meta.label} · {job.phase || 'Queued operation'}</span>
        </div>
        <JobStatus state={job.state} />
        <div className="job-progress-cell">
          <div>
            <span>{job.state === 'running' ? 'Progress' : 'Last update'}</span>
            <strong>{job.state === 'running' ? `${job.progress || 0}%` : formatDate(timestamp)}</strong>
          </div>
          {job.state === 'running' && (
            <div className="job-progress-track">
              <motion.i
                initial={{ width: 0 }}
                animate={{ width: `${job.progress || 0}%` }}
                transition={{ duration: 0.35 }}
              />
            </div>
          )}
        </div>
        <div className="job-row-actions">
          {job.state === 'pending' && (
            <button
              type="button"
              className="job-action is-primary"
              disabled={actionBusy}
              onClick={() => onAction(job.id, 'run')}
              title="Run now"
            >
              <Play size={16} /> <span>Run</span>
            </button>
          )}
          {canCancel && (
            <button
              type="button"
              className="job-action is-danger"
              disabled={actionBusy}
              onClick={() => onAction(job.id, 'cancel')}
              title="Cancel job"
            >
              <Square size={15} /> <span>Cancel</span>
            </button>
          )}
          <button
            type="button"
            className="job-expand"
            onClick={() => setExpanded((value) => !value)}
            aria-expanded={expanded}
            title="Toggle details"
          >
            <ChevronDown size={18} />
          </button>
        </div>
      </div>

      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="job-details"
          >
            <div className="job-details-grid">
              <div className="job-detail-summary">
                <dl>
                  <div><dt>Job ID</dt><dd>{job.id}</dd></div>
                  <div><dt>Created</dt><dd>{formatDate(job.created_at)}</dd></div>
                  <div><dt>Started</dt><dd>{formatDate(job.started_at)}</dd></div>
                  <div><dt>Completed</dt><dd>{job.completed_at ? formatDate(job.completed_at) : '—'}</dd></div>
                </dl>
                {job.error && <div className="job-error"><XCircle size={16} />{job.error}</div>}
                <JsonBlock label="Configuration" value={job.config} />
                <JsonBlock label="Result" value={job.result} />
              </div>
              <div className="job-log-panel">
                <div className="job-log-heading">
                  <span><TerminalSquare size={15} /> Execution log</span>
                  <span>{logs.length} entries</span>
                </div>
                <div className="job-log-content">
                  {logsLoading ? (
                    <div className="job-log-empty"><LoaderCircle size={17} className="animate-spin" /> Loading log</div>
                  ) : logs.length ? (
                    logs.map((entry, index) => (
                      <div className={`log-line level-${entry.level}`} key={`${entry.created_at}-${index}`}>
                        <time>{entry.created_at ? new Date(entry.created_at).toLocaleTimeString('tr-TR') : '--:--'}</time>
                        <span>{entry.message}</span>
                      </div>
                    ))
                  ) : (
                    <div className="job-log-empty">No output has been recorded yet.</div>
                  )}
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.article>
  );
}

function normalizeConfigValue(schema, value) {
  if (schema.type === 'integer') return Number(value);
  if (schema.type === 'array') {
    if (Array.isArray(value)) return value;
    return String(value || '').split(',').map((item) => item.trim()).filter(Boolean);
  }
  return value;
}

function CreateJobModal({ types, onClose, onCreate }) {
  const [name, setName] = useState('');
  const [type, setType] = useState('');
  const [config, setConfig] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const selectedType = types[type];

  function selectType(nextType) {
    const schema = types[nextType]?.config_schema || {};
    setType(nextType);
    setConfig(Object.fromEntries(
      Object.entries(schema).map(([key, value]) => [key, value.default ?? ''])
    ));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    try {
      const schema = selectedType?.config_schema || {};
      const normalized = Object.fromEntries(
        Object.entries(config).map(([key, value]) => [
          key,
          normalizeConfigValue(schema[key] || {}, value),
        ])
      );
      await onCreate({ name, type, config: normalized });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <motion.div className="job-modal-backdrop" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      <motion.div
        className="job-modal"
        initial={{ opacity: 0, y: 18, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
      >
        <div className="job-modal-header">
          <div>
            <span>New operation</span>
            <h2>Create a job</h2>
          </div>
          <button type="button" onClick={onClose}><X size={19} /></button>
        </div>

        <form onSubmit={handleSubmit}>
          <label className="job-field">
            <span>Name</span>
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="e.g. Weekly system backup"
              required
              autoFocus
            />
          </label>

          <div className="job-field">
            <span>Operation type</span>
            <div className="job-type-picker">
              {Object.entries(types).map(([key, value]) => {
                const meta = typeMeta[key] || { icon: ListTodo };
                const Icon = meta.icon;
                return (
                  <button
                    key={key}
                    type="button"
                    className={type === key ? 'is-selected' : ''}
                    onClick={() => selectType(key)}
                  >
                    <Icon size={18} />
                    <span>{value.name}</span>
                    {type === key && <Check size={16} />}
                  </button>
                );
              })}
            </div>
          </div>

          {selectedType && (
            <div className="job-config-panel">
              <p>{selectedType.description}</p>
              {Object.entries(selectedType.config_schema || {}).map(([key, schema]) => (
                <label className={`job-field ${schema.type === 'boolean' ? 'is-toggle' : ''}`} key={key}>
                  <span>{key.replaceAll('_', ' ')}</span>
                  {schema.type === 'boolean' ? (
                    <input
                      type="checkbox"
                      checked={Boolean(config[key])}
                      onChange={(event) => setConfig((current) => ({ ...current, [key]: event.target.checked }))}
                    />
                  ) : schema.enum ? (
                    <select
                      value={config[key] ?? ''}
                      onChange={(event) => setConfig((current) => ({ ...current, [key]: event.target.value }))}
                    >
                      {schema.enum.map((value) => <option value={value} key={value}>{value}</option>)}
                    </select>
                  ) : (
                    <input
                      type={schema.type === 'integer' ? 'number' : 'text'}
                      value={Array.isArray(config[key]) ? config[key].join(', ') : (config[key] ?? '')}
                      onChange={(event) => setConfig((current) => ({ ...current, [key]: event.target.value }))}
                      required={schema.required}
                      placeholder={schema.type === 'array' ? 'Comma-separated values' : ''}
                    />
                  )}
                </label>
              ))}
            </div>
          )}

          <div className="job-modal-actions">
            <button type="button" className="button-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="button-primary" disabled={!name || !type || submitting}>
              {submitting ? <LoaderCircle size={17} className="animate-spin" /> : <Plus size={17} />}
              Create job
            </button>
          </div>
        </form>
      </motion.div>
    </motion.div>
  );
}

export default function Jobs() {
  const { isOperator } = useAuth();
  const [jobs, setJobs] = useState([]);
  const [jobTypes, setJobTypes] = useState({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState('all');
  const [showCreate, setShowCreate] = useState(false);
  const [error, setError] = useState('');
  const [actionBusy, setActionBusy] = useState('');
  const jobsHashRef = useRef('');

  const loadJobs = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setRefreshing(true);
    try {
      const response = await api.get('/jobs?limit=100');
      const nextJobs = response.data || [];
      const nextHash = JSON.stringify(nextJobs);
      if (nextHash !== jobsHashRef.current) {
        jobsHashRef.current = nextHash;
        setJobs(nextJobs);
      }
      setError('');
    } catch (requestError) {
      console.error('Failed to load jobs:', requestError);
      setError('Jobs could not be loaded. Check the API connection and try again.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  const loadJobTypes = useCallback(async () => {
    try {
      const response = await api.get('/jobs/types');
      setJobTypes(response.data || {});
    } catch (requestError) {
      console.error('Failed to load job types:', requestError);
    }
  }, []);

  useEffect(() => {
    loadJobs();
    loadJobTypes();
    const interval = setInterval(() => {
      if (!document.hidden) loadJobs({ silent: true });
    }, 5000);
    return () => clearInterval(interval);
  }, [loadJobs, loadJobTypes]);

  async function handleAction(jobId, action) {
    setActionBusy(jobId);
    try {
      await api.post(`/jobs/${jobId}/${action}`);
      await loadJobs({ silent: true });
    } catch (requestError) {
      setError(`Job action failed: ${requestError.message}`);
    } finally {
      setActionBusy('');
    }
  }

  async function handleCreate(jobData) {
    try {
      await api.post('/jobs', jobData);
      setShowCreate(false);
      await loadJobs({ silent: true });
    } catch (requestError) {
      setError(`Job could not be created: ${requestError.message}`);
      throw requestError;
    }
  }

  const counts = {
    all: jobs.length,
    running: jobs.filter((job) => job.state === 'running').length,
    pending: jobs.filter((job) => job.state === 'pending').length,
    completed: jobs.filter((job) => job.state === 'completed').length,
    failed: jobs.filter((job) => job.state === 'failed').length,
  };
  const filteredJobs = filter === 'all' ? jobs : jobs.filter((job) => job.state === filter);

  if (loading) {
    return <div className="jobs-loading"><LoaderCircle size={24} className="animate-spin" /> Loading operations</div>;
  }

  return (
    <div className="jobs-page">
      <div className="jobs-toolbar">
        <div className="jobs-summary" aria-label="Job summary">
          <div><span>Running</span><strong>{counts.running}</strong></div>
          <div><span>Waiting</span><strong>{counts.pending}</strong></div>
          <div><span>Completed</span><strong>{counts.completed}</strong></div>
          <div className={counts.failed ? 'has-failures' : ''}><span>Failed</span><strong>{counts.failed}</strong></div>
        </div>
        <div className="jobs-toolbar-actions">
          <button
            type="button"
            className="button-secondary"
            onClick={() => loadJobs()}
            disabled={refreshing}
          >
            <RefreshCw size={17} className={refreshing ? 'animate-spin' : ''} />
            Refresh
          </button>
          {isOperator && (
            <button type="button" className="button-primary" onClick={() => setShowCreate(true)}>
              <Plus size={17} /> New job
            </button>
          )}
        </div>
      </div>

      {error && <div className="jobs-error"><XCircle size={17} />{error}<button onClick={() => setError('')}><X size={15} /></button></div>}

      <div className="jobs-panel">
        <div className="jobs-panel-header">
          <div>
            <h2>Operation history</h2>
            <p>Live status and execution output from the privileged agent.</p>
          </div>
          <div className="jobs-filters">
            {Object.entries(counts).map(([key, count]) => (
              <button
                type="button"
                key={key}
                className={filter === key ? 'is-active' : ''}
                onClick={() => setFilter(key)}
              >
                {key === 'all' ? 'All' : stateMeta[key]?.label || key}
                <span>{count}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="jobs-list-heading" aria-hidden="true">
          <span>Operation</span><span>Status</span><span>Activity</span><span>Actions</span>
        </div>

        <div className="jobs-list">
          <AnimatePresence initial={false}>
            {filteredJobs.map((job) => (
              <JobRow
                key={job.id}
                job={job}
                onAction={handleAction}
                actionBusy={actionBusy === job.id}
              />
            ))}
          </AnimatePresence>
          {!filteredJobs.length && (
            <div className="jobs-empty">
              <ListTodo size={28} />
              <h3>No matching jobs</h3>
              <p>{filter === 'all' ? 'Create a job to start a maintenance operation.' : `There are no ${filter} jobs.`}</p>
            </div>
          )}
        </div>
      </div>

      <AnimatePresence>
        {showCreate && (
          <CreateJobModal
            types={jobTypes}
            onClose={() => setShowCreate(false)}
            onCreate={handleCreate}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
