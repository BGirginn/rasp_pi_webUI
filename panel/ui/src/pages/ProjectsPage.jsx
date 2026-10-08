import { useCallback, useEffect, useState } from 'react';
import { Archive, FolderGit2, Plus, RefreshCw, RotateCcw, Trash2 } from 'lucide-react';
import { api } from '../services/api';
import { useTheme } from '../contexts/ThemeContext';
import { useAuth } from '../hooks/useAuth';

const formatBytes = (value) => {
  if (!value) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const index = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1);
  return `${(value / (1024 ** index)).toFixed(index ? 1 : 0)} ${units[index]}`;
};

export function ProjectsPage() {
  const { isDarkMode } = useTheme();
  const { isAdmin } = useAuth();
  const [projects, setProjects] = useState([]);
  const [snapshots, setSnapshots] = useState({});
  const [form, setForm] = useState({ name: '', root_path: '' });
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setError('');
    try {
      const response = await api.get('/projects', { cache: false });
      setProjects(response.data.filter((project) => project.enabled));
      const entries = await Promise.all(response.data.filter((project) => project.enabled).map(async (project) => {
        const result = await api.get(`/projects/${project.id}/snapshots`, { cache: false });
        return [project.id, result.data];
      }));
      setSnapshots(Object.fromEntries(entries));
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const register = async (event) => {
    event.preventDefault();
    setBusy('register');
    try {
      await api.post('/projects', form);
      setForm({ name: '', root_path: '' });
      await load();
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    } finally { setBusy(''); }
  };

  const createSnapshot = async (project) => {
    setBusy(`snapshot:${project.id}`);
    try { await api.post(`/projects/${project.id}/snapshots`); await load(); }
    catch (err) { setError(err.response?.data?.detail || err.message); }
    finally { setBusy(''); }
  };

  const restore = async (project, snapshot) => {
    const confirmation = window.prompt(`Type ${project.name} to restore this snapshot`);
    if (confirmation === null) return;
    setBusy(`restore:${snapshot.id}`);
    try {
      await api.post(`/projects/${project.id}/snapshots/${snapshot.id}/restore`, { confirmation });
      await load();
    } catch (err) { setError(err.response?.data?.detail || err.message); }
    finally { setBusy(''); }
  };

  const unregister = async (project) => {
    if (!window.confirm(`Remove ${project.name} from the registry? Files are not deleted.`)) return;
    setBusy(`delete:${project.id}`);
    try { await api.delete(`/projects/${project.id}`); await load(); }
    catch (err) { setError(err.response?.data?.detail || err.message); }
    finally { setBusy(''); }
  };

  const panel = isDarkMode ? 'bg-black/40 border-white/10' : 'bg-white border-gray-200';
  const input = isDarkMode ? 'bg-white/5 border-white/10 text-white' : 'bg-gray-50 border-gray-300 text-gray-900';

  return <div className="space-y-6 pb-10">
    <div className="flex items-center justify-between gap-4">
      <div><h1 className="text-3xl font-semibold">Projects</h1><p className="text-sm text-gray-500">Registered roots and verified local snapshots</p></div>
      <button title="Refresh projects" onClick={load} className={`h-10 w-10 grid place-items-center rounded-lg border ${panel}`}><RefreshCw size={18} /></button>
    </div>

    {error && <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-400">{error}</div>}

    {isAdmin && <form onSubmit={register} className={`grid gap-3 rounded-lg border p-4 md:grid-cols-[1fr_2fr_auto] ${panel}`}>
      <input aria-label="Project name" required placeholder="Project name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className={`h-10 rounded-lg border px-3 ${input}`} />
      <input aria-label="Project root" required placeholder="/home/user/project" value={form.root_path} onChange={(e) => setForm({ ...form, root_path: e.target.value })} className={`h-10 rounded-lg border px-3 ${input}`} />
      <button disabled={busy === 'register'} className="h-10 rounded-lg bg-emerald-600 px-4 text-white disabled:opacity-50"><Plus className="inline mr-2" size={17} />Register</button>
    </form>}

    <div className="space-y-4">
      {projects.map((project) => <section key={project.id} className={`rounded-lg border ${panel}`}>
        <header className="flex flex-wrap items-center gap-3 border-b border-white/10 p-4">
          <FolderGit2 size={20} className="text-emerald-500" />
          <div className="min-w-0 flex-1"><h2 className="font-semibold">{project.name}</h2><p className="truncate text-xs text-gray-500">{project.root_path}</p></div>
          <button title="Create snapshot" disabled={busy === `snapshot:${project.id}`} onClick={() => createSnapshot(project)} className="h-9 rounded-lg bg-blue-600 px-3 text-sm text-white disabled:opacity-50"><Archive className="inline mr-2" size={16} />Snapshot</button>
          {isAdmin && <button title="Unregister project" onClick={() => unregister(project)} className="h-9 w-9 rounded-lg border border-red-500/30 text-red-400"><Trash2 className="mx-auto" size={16} /></button>}
        </header>
        <div className="divide-y divide-white/10">
          {(snapshots[project.id] || []).map((snapshot) => <div key={snapshot.id} className="flex flex-wrap items-center gap-3 px-4 py-3 text-sm">
            <div className="min-w-0 flex-1"><p>{new Date(snapshot.created_at).toLocaleString()}</p><p className="truncate text-xs text-gray-500">{snapshot.checksum.slice(0, 16)} · {formatBytes(snapshot.size_bytes)}</p></div>
            {isAdmin && <button title="Restore snapshot" disabled={busy === `restore:${snapshot.id}`} onClick={() => restore(project, snapshot)} className="h-8 rounded-lg border px-3 text-xs"><RotateCcw className="inline mr-2" size={14} />Restore</button>}
          </div>)}
          {!(snapshots[project.id] || []).length && <p className="p-4 text-sm text-gray-500">No snapshots yet.</p>}
        </div>
      </section>)}
      {!projects.length && <div className={`rounded-lg border p-8 text-center text-gray-500 ${panel}`}>No registered projects.</div>}
    </div>
  </div>;
}
