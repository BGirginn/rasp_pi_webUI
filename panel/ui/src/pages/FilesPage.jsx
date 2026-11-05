import { useCallback, useEffect, useRef, useState } from 'react';
import {
    ArrowUp,
    CheckCircle2,
    ChevronRight,
    Copy,
    Download,
    File,
    Folder,
    FolderPlus,
    HardDrive,
    Move,
    Pencil,
    Plus,
    RefreshCw,
    Search,
    Trash2,
    Upload,
    X,
} from 'lucide-react';
import { api } from '../services/api';
import { useAuth } from '../hooks/useAuth';
import { formatBytes } from '../utils/format';

const messageFor = (error) =>
    typeof error.response?.data?.detail === 'string' ? error.response.data.detail : error.message;
const within = (path, root) => path === root || path.startsWith(`${root}/`);
const join = (parent, name) => `${parent.replace(/\/$/, '')}/${name}`;

export default function FilesPage() {
    const { isAdmin, isOperator } = useAuth();
    const [roots, setRoots] = useState([]);
    const [currentPath, setCurrentPath] = useState('');
    const [files, setFiles] = useState([]);
    const [loading, setLoading] = useState(true);
    const [busy, setBusy] = useState('');
    const [search, setSearch] = useState('');
    const [showHidden, setShowHidden] = useState(false);
    const [sortBy, setSortBy] = useState('name');
    const [selected, setSelected] = useState(null);
    const [form, setForm] = useState(null);
    const [formValue, setFormValue] = useState('');
    const [rootName, setRootName] = useState('');
    const [formError, setFormError] = useState('');
    const [error, setError] = useState('');
    const [notice, setNotice] = useState('');
    const pathRef = useRef('');
    const requestId = useRef(0);
    const rootRequestId = useRef(0);
    const uploadInput = useRef(null);

    const loadFiles = useCallback(async (path) => {
        const request = ++requestId.current;
        if (pathRef.current !== path) {
            setFiles([]);
            setSearch('');
        }
        pathRef.current = path;
        setCurrentPath(path);
        setSelected(null);
        setLoading(true);
        setError('');
        try {
            const response = await api.get(`/files/list?path=${encodeURIComponent(path)}`, { cache: false });
            if (!Array.isArray(response.data)) throw new Error('Unexpected directory response');
            if (request === requestId.current) setFiles(response.data);
        } catch (failure) {
            if (request === requestId.current) setError(messageFor(failure));
        } finally {
            if (request === requestId.current) setLoading(false);
        }
    }, []);

    const loadRoots = useCallback(
        async (preferred) => {
            const request = ++rootRequestId.current;
            try {
                const response = await api.get('/files/roots', { cache: false });
                if (request !== rootRequestId.current) return;
                const available = response.data.roots || [];
                setRoots(available);
                const candidate = preferred || pathRef.current;
                if (available.length)
                    await loadFiles(available.some((root) => within(candidate, root)) ? candidate : available[0]);
                else {
                    setCurrentPath('');
                    pathRef.current = '';
                    setFiles([]);
                    setLoading(false);
                }
            } catch (failure) {
                if (request === rootRequestId.current) {
                    setError(messageFor(failure));
                    setLoading(false);
                }
            }
        },
        [loadFiles]
    );

    useEffect(() => {
        if (isOperator) loadRoots();
        else setLoading(false);
        return () => {
            requestId.current += 1;
            rootRequestId.current += 1;
        };
    }, [isOperator, loadRoots]);

    const root = [...roots].sort((a, b) => b.length - a.length).find((item) => within(currentPath, item)) || '';
    const parts = root ? currentPath.slice(root.length).split('/').filter(Boolean) : [];
    const visible = files
        .filter((item) => (showHidden || !item.is_hidden) && item.name.toLowerCase().includes(search.toLowerCase()))
        .sort(
            (a, b) =>
                Number(b.type === 'directory') - Number(a.type === 'directory') ||
                (sortBy === 'size'
                    ? b.size - a.size
                    : sortBy === 'modified'
                      ? new Date(b.modified) - new Date(a.modified)
                      : a.name.localeCompare(b.name))
        );

    const openForm = (action) => {
        setForm({ action, file: selected });
        setFormError('');
        setFormValue(
            action === 'rename'
                ? selected.name
                : ['copy', 'move'].includes(action)
                  ? join(currentPath, selected.name)
                  : ''
        );
        setRootName('');
    };

    const submitOperation = async (event) => {
        event.preventDefault();
        const value = formValue.trim();
        if (
            ['mkdir', 'rename'].includes(form.action) &&
            (!value || value === '.' || value === '..' || value.includes('/'))
        ) {
            setFormError('Enter a folder or file name without path separators.');
            return;
        }
        if (form.action === 'delete' && value !== form.file.name) {
            setFormError('Type the exact name to confirm deletion.');
            return;
        }
        setBusy('Applying operation…');
        setFormError('');
        setError('');
        setNotice('');
        try {
            if (form.action === 'root') {
                await api.post('/projects', { name: rootName.trim(), root_path: value, project_type: 'directory' });
                await loadRoots(value);
            } else {
                const payload = { action: form.action, path: form.file?.path || currentPath };
                if (form.action === 'mkdir') payload.path = join(currentPath, value);
                if (form.action === 'rename') payload.new_name = value;
                if (['copy', 'move'].includes(form.action)) payload.destination = value;
                await api.post('/files/action', payload);
                await loadFiles(currentPath);
            }
            setNotice(
                `${form.action === 'root' ? 'Folder registration' : form.action.charAt(0).toUpperCase() + form.action.slice(1)} completed.`
            );
            setForm(null);
        } catch (failure) {
            setFormError(messageFor(failure));
        } finally {
            setBusy('');
        }
    };

    const upload = async (event) => {
        const items = [...(event.target.files || [])];
        if (!items.length || !currentPath) return;
        const failures = [];
        let completed = 0;
        setNotice('');
        setError('');
        try {
            for (const [index, file] of items.entries()) {
                setBusy(`Uploading ${index + 1} of ${items.length}: ${file.name}`);
                const body = new FormData();
                body.append('path', currentPath);
                body.append('files', file);
                try {
                    await api.post('/files/upload', body);
                    completed += 1;
                } catch (failure) {
                    failures.push(`${file.name}: ${messageFor(failure)}`);
                }
            }
            await loadFiles(currentPath);
            if (completed) setNotice(`${completed} ${completed === 1 ? 'file' : 'files'} uploaded.`);
            if (failures.length) setError(failures.join(' · '));
        } finally {
            setBusy('');
            if (uploadInput.current) uploadInput.current.value = '';
        }
    };

    const download = async () => {
        setBusy('Preparing download…');
        setError('');
        try {
            const response = await api.get(`/files/download?path=${encodeURIComponent(selected.path)}`, {
                responseType: 'blob',
            });
            const url = URL.createObjectURL(response.data);
            const link = document.createElement('a');
            link.href = url;
            link.download = selected.name;
            document.body.appendChild(link);
            link.click();
            link.remove();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
        } catch (failure) {
            setError(messageFor(failure));
        } finally {
            setBusy('');
        }
    };

    if (!isOperator)
        return (
            <div className="workspace-empty">
                <Folder size={30} />
                <h2>File access requires an operator or administrator</h2>
            </div>
        );

    return (
        <div className="management-page" aria-label="Files workspace">
            <div className="operations-overview">
                <div>
                    <span className="eyebrow">FILE WORKSPACE</span>
                    <h2>Your files. Within reach.</h2>
                    <p>Browse registered folders and manage files without leaving the panel.</p>
                </div>
                <div className="toolbar-actions">
                    {isAdmin && (
                        <button className="control-button" disabled={Boolean(busy)} onClick={() => openForm('root')}>
                            <Plus size={16} />
                            Register folder
                        </button>
                    )}
                    <button
                        className="control-button icon-only"
                        aria-label="Refresh files"
                        disabled={Boolean(busy) || loading}
                        onClick={() => (currentPath ? loadFiles(currentPath) : loadRoots())}
                    >
                        <RefreshCw size={16} />
                    </button>
                </div>
            </div>
            {error && (
                <p role="alert" className="operation-notice is-error">
                    {error}
                </p>
            )}
            {notice && (
                <p role="status" className="operation-notice is-success">
                    <CheckCircle2 size={16} />
                    {notice}
                </p>
            )}
            {busy && (
                <p role="status" className="operation-notice">
                    <RefreshCw className="animate-spin" size={15} />
                    {busy}
                </p>
            )}
            {form && (
                <section
                    className={`workspace-panel operation-form ${form.action === 'delete' ? 'danger-panel' : ''}`}
                    aria-label={`${form.action} operation`}
                >
                    <div>
                        <span className="eyebrow">
                            {form.action === 'delete' ? 'PERMANENT OPERATION' : 'FILE OPERATION'}
                        </span>
                        <h3>
                            {form.action === 'root'
                                ? 'Register an existing folder'
                                : `${form.action.charAt(0).toUpperCase() + form.action.slice(1)} ${form.file?.name || 'folder'}`}
                        </h3>
                        <p>
                            {form.action === 'root'
                                ? 'The server only accepts paths inside its configured allowed parents.'
                                : form.action === 'delete'
                                  ? 'This permanently deletes the selected item. Type its exact name to confirm.'
                                  : ['copy', 'move'].includes(form.action)
                                    ? 'Enter the complete destination path, including the new name. Existing items will not be overwritten.'
                                    : 'Use a name within the current folder.'}
                        </p>
                    </div>
                    <form onSubmit={submitOperation}>
                        {form.action === 'root' && (
                            <label>
                                Folder label
                                <input
                                    aria-label="Folder label"
                                    required
                                    value={rootName}
                                    onChange={(event) => setRootName(event.target.value)}
                                    disabled={Boolean(busy)}
                                />
                            </label>
                        )}
                        <label>
                            {form.action === 'root'
                                ? 'Folder path'
                                : form.action === 'delete'
                                  ? 'Confirm name'
                                  : ['copy', 'move'].includes(form.action)
                                    ? 'Destination path'
                                    : 'New name'}
                            <input
                                aria-label={
                                    form.action === 'root'
                                        ? 'Folder path'
                                        : form.action === 'delete'
                                          ? 'Confirm name'
                                          : ['copy', 'move'].includes(form.action)
                                            ? 'Destination path'
                                            : 'New name'
                                }
                                required
                                value={formValue}
                                onChange={(event) => setFormValue(event.target.value)}
                                disabled={Boolean(busy)}
                                autoFocus
                            />
                        </label>
                        {formError && (
                            <p role="alert" className="form-error">
                                {formError}
                            </p>
                        )}
                        <div className="toolbar-actions">
                            <button
                                type="button"
                                className="control-button"
                                onClick={() => setForm(null)}
                                disabled={Boolean(busy)}
                            >
                                Cancel
                            </button>
                            <button
                                type="submit"
                                className={`control-button ${form.action === 'delete' ? 'is-danger' : 'is-primary'}`}
                                disabled={Boolean(busy) || (form.action === 'delete' && formValue !== form.file.name)}
                            >
                                Confirm {form.action === 'root' ? 'registration' : form.action}
                            </button>
                        </div>
                    </form>
                </section>
            )}
            {!roots.length && !loading ? (
                <section className="workspace-panel workspace-empty">
                    <HardDrive size={32} />
                    <h3>No file roots configured</h3>
                    <p>
                        {isAdmin
                            ? 'Register an existing folder to begin. Access stays within the server’s allowed paths.'
                            : 'Ask an administrator to register a folder for file access.'}
                    </p>
                </section>
            ) : (
                <div className={`workspace-grid ${selected ? 'has-inspector' : ''}`}>
                    <section className="workspace-panel">
                        <div className="workspace-toolbar">
                            <label className="root-selector">
                                <HardDrive size={17} />
                                <select
                                    aria-label="File root"
                                    value={root}
                                    disabled={Boolean(busy) || loading}
                                    onChange={(event) => {
                                        setForm(null);
                                        loadFiles(event.target.value);
                                    }}
                                >
                                    {roots.map((item) => (
                                        <option key={item} value={item}>
                                            {item}
                                        </option>
                                    ))}
                                </select>
                            </label>
                            <div className="toolbar-actions">
                                <button
                                    className="control-button"
                                    disabled={!currentPath || Boolean(busy)}
                                    onClick={() => openForm('mkdir')}
                                >
                                    <FolderPlus size={16} />
                                    <span>New folder</span>
                                </button>
                                <button
                                    className="control-button is-primary"
                                    disabled={!currentPath || Boolean(busy)}
                                    onClick={() => uploadInput.current.click()}
                                >
                                    <Upload size={16} />
                                    Upload files
                                </button>
                                <input
                                    aria-label="Upload files"
                                    ref={uploadInput}
                                    type="file"
                                    multiple
                                    hidden
                                    onChange={upload}
                                />
                            </div>
                        </div>
                        <div className="path-toolbar">
                            <button
                                className="control-button icon-only"
                                aria-label="Parent folder"
                                disabled={!root || currentPath === root || Boolean(busy) || loading}
                                onClick={() => {
                                    setForm(null);
                                    loadFiles(currentPath.slice(0, currentPath.lastIndexOf('/')) || root);
                                }}
                            >
                                <ArrowUp size={16} />
                            </button>
                            <nav aria-label="Folder breadcrumbs">
                                <button
                                    disabled={Boolean(busy)}
                                    onClick={() => {
                                        setForm(null);
                                        loadFiles(root);
                                    }}
                                >
                                    {root || 'Loading roots…'}
                                </button>
                                {parts.map((name, index) => (
                                    <span key={index}>
                                        <ChevronRight size={13} />
                                        <button
                                            disabled={Boolean(busy)}
                                            onClick={() => {
                                                setForm(null);
                                                loadFiles(join(root, parts.slice(0, index + 1).join('/')));
                                            }}
                                        >
                                            {name}
                                        </button>
                                    </span>
                                ))}
                            </nav>
                        </div>
                        <div className="workspace-toolbar file-filters">
                            <label className="search-field">
                                <Search size={16} />
                                <input
                                    aria-label="Search files"
                                    placeholder="Search this folder…"
                                    value={search}
                                    onChange={(event) => setSearch(event.target.value)}
                                />
                            </label>
                            <label className="checkbox-label">
                                <input
                                    type="checkbox"
                                    checked={showHidden}
                                    onChange={(event) => setShowHidden(event.target.checked)}
                                />
                                Hidden files
                            </label>
                            <select
                                aria-label="Sort files"
                                value={sortBy}
                                onChange={(event) => setSortBy(event.target.value)}
                            >
                                <option value="name">Name</option>
                                <option value="modified">Last modified</option>
                                <option value="size">Size</option>
                            </select>
                        </div>
                        <div className="table-scroll">
                            <table className="operations-table file-table">
                                <thead>
                                    <tr>
                                        <th>Name</th>
                                        <th>Size</th>
                                        <th>Modified</th>
                                        <th>Permissions</th>
                                        <th />
                                    </tr>
                                </thead>
                                <tbody>
                                    {visible.map((item) => (
                                        <tr
                                            key={item.path}
                                            className={selected?.path === item.path ? 'is-selected' : ''}
                                        >
                                            <td>
                                                <button
                                                    className="entity-button"
                                                    disabled={Boolean(busy)}
                                                    onClick={() => {
                                                        if (item.type === 'directory') {
                                                            setForm(null);
                                                            loadFiles(item.path);
                                                        } else setSelected(item);
                                                    }}
                                                >
                                                    <span
                                                        className={`entity-icon ${item.type === 'directory' ? 'is-folder' : ''}`}
                                                    >
                                                        {item.type === 'directory' ? (
                                                            <Folder size={18} />
                                                        ) : (
                                                            <File size={18} />
                                                        )}
                                                    </span>
                                                    <strong>{item.name}</strong>
                                                </button>
                                            </td>
                                            <td className="numeric-cell">
                                                {item.type === 'directory' ? 'Folder' : formatBytes(item.size)}
                                            </td>
                                            <td className="muted-text">
                                                {new Date(item.modified).toLocaleString('tr-TR', {
                                                    dateStyle: 'short',
                                                    timeStyle: 'short',
                                                })}
                                            </td>
                                            <td>
                                                <code>{item.permissions}</code>
                                            </td>
                                            <td>
                                                <button
                                                    className="control-button icon-only"
                                                    disabled={Boolean(busy)}
                                                    aria-label={`Inspect ${item.name}`}
                                                    onClick={() => setSelected(item)}
                                                >
                                                    <ChevronRight size={16} />
                                                </button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                        {!visible.length && (
                            <div className="workspace-empty">
                                <Folder size={30} />
                                <h3>
                                    {loading
                                        ? 'Reading folder…'
                                        : files.length
                                          ? 'No matching files'
                                          : 'Empty directory'}
                                </h3>
                                <p>
                                    {loading
                                        ? 'Waiting for the host filesystem.'
                                        : 'Upload files or create a folder to get started.'}
                                </p>
                            </div>
                        )}
                        <footer className="table-footer">
                            <span>
                                {visible.length} of {files.length} items
                            </span>
                            <span>Registered roots only</span>
                        </footer>
                    </section>
                    {selected && (
                        <aside className="workspace-panel inspector">
                            <header>
                                <div>
                                    <span className="eyebrow">FILE INSPECTOR</span>
                                    <h2>{selected.name}</h2>
                                </div>
                                <button
                                    className="control-button icon-only"
                                    aria-label="Close file details"
                                    onClick={() => setSelected(null)}
                                >
                                    <X size={17} />
                                </button>
                            </header>
                            <div className="file-preview-icon">
                                {selected.type === 'directory' ? <Folder size={44} /> : <File size={44} />}
                            </div>
                            <dl className="file-properties">
                                <dt>Location</dt>
                                <dd>{selected.path}</dd>
                                <dt>Type</dt>
                                <dd>{selected.type}</dd>
                                <dt>Size</dt>
                                <dd>{selected.type === 'directory' ? 'Not calculated' : formatBytes(selected.size)}</dd>
                                <dt>Permissions</dt>
                                <dd>
                                    <code>{selected.permissions}</code>
                                </dd>
                                <dt>Modified</dt>
                                <dd>{new Date(selected.modified).toLocaleString()}</dd>
                            </dl>
                            <div className="inspector-actions">
                                {selected.type !== 'directory' && (
                                    <button className="control-button" disabled={Boolean(busy)} onClick={download}>
                                        <Download size={16} />
                                        Download
                                    </button>
                                )}
                                <button
                                    className="control-button"
                                    disabled={Boolean(busy)}
                                    onClick={() => openForm('rename')}
                                >
                                    <Pencil size={16} />
                                    Rename
                                </button>
                                <button
                                    className="control-button"
                                    disabled={Boolean(busy)}
                                    onClick={() => openForm('copy')}
                                >
                                    <Copy size={16} />
                                    Copy
                                </button>
                                <button
                                    className="control-button"
                                    disabled={Boolean(busy)}
                                    onClick={() => openForm('move')}
                                >
                                    <Move size={16} />
                                    Move
                                </button>
                                <button
                                    className="control-button is-danger"
                                    disabled={Boolean(busy)}
                                    onClick={() => openForm('delete')}
                                >
                                    <Trash2 size={16} />
                                    Delete
                                </button>
                            </div>
                        </aside>
                    )}
                </div>
            )}
        </div>
    );
}
