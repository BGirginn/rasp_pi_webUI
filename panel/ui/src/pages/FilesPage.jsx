import { useState, useEffect, useRef } from 'react';
import {
    Folder, File, Download, Upload, Trash2,
    MoreVertical, Copy, Move, ArrowUp, Home,
    FileText, Image as ImageIcon, Music, Video, Code,
    RefreshCw, ChevronRight, CornerDownRight, FolderPlus, Edit2, Lock, Unlock
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { api } from '../services/api';
import { useTheme, getThemeColors } from '../contexts/ThemeContext';
import { useAuth } from '../hooks/useAuth';

export default function FilesPage() {
    const { theme, isDarkMode } = useTheme();
    const themeColors = getThemeColors(theme);
    const { user } = useAuth();

    // Default to /home as requested by user
    const defaultPath = '/home';
    const [currentPath, setCurrentPath] = useState(defaultPath);
    const [files, setFiles] = useState([]);
    const [loading, setLoading] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [error, setError] = useState(null);
    const [selectedFile, setSelectedFile] = useState(null);
    const [contextMenu, setContextMenu] = useState(null);
    const [isDragging, setIsDragging] = useState(false);

    const fileInputRef = useRef(null);
    const dragCounter = useRef(0);

    const formatError = (err) => {
        const detail = err.response?.data?.detail;
        if (typeof detail === 'string') return detail;
        if (Array.isArray(detail)) {
            return detail.map(e => e.msg || JSON.stringify(e)).join(', ');
        }
        if (typeof detail === 'object' && detail !== null) {
            return JSON.stringify(detail);
        }
        return err.message || "An error occurred";
    };

    const fetchFiles = async (path) => {
        setLoading(true);
        setError(null);
        try {
            const res = await api.get(`/files/list?path=${encodeURIComponent(path)}`);
            setFiles(res.data);
        } catch (err) {
            setError(formatError(err));
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchFiles(currentPath);
    }, [currentPath]);

    const handleNavigate = (path) => {
        setCurrentPath(path);
    };

    const handleUp = () => {
        if (currentPath === '/') return;
        const parent = currentPath.split('/').slice(0, -1).join('/') || '/';
        setCurrentPath(parent);
    };

    const formatSize = (bytes) => {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    };

    const getFileIcon = (file) => {
        if (file.type === 'directory') return <Folder className="text-yellow-400" size={24} />;

        // Simple extension check
        const ext = file.name.split('.').pop().toLowerCase();
        if (['jpg', 'jpeg', 'png', 'gif', 'svg'].includes(ext)) return <ImageIcon className="text-purple-400" size={24} />;
        if (['mp4', 'mkv', 'mov'].includes(ext)) return <Video className="text-red-400" size={24} />;
        if (['mp3', 'wav'].includes(ext)) return <Music className="text-green-400" size={24} />;
        if (['js', 'jsx', 'py', 'html', 'css', 'json'].includes(ext)) return <Code className="text-blue-400" size={24} />;
        return <FileText className="text-gray-400" size={24} />;
    };

    const handleDownload = async (file) => {
        try {
            const res = await api.get(`/files/download?path=${encodeURIComponent(file.path)}`, {
                responseType: 'blob'
            });
            const url = window.URL.createObjectURL(new Blob([res.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', file.name);
            document.body.appendChild(link);
            link.click();
            link.remove();
        } catch (err) {
            console.error("Download failed", err);
        }
    };

    const handleDelete = async (file) => {
        if (!confirm(`Are you sure you want to delete ${file.name}?`)) return;
        try {
            await api.post('/files/action', {
                action: 'delete',
                path: file.path
            });
            fetchFiles(currentPath);
            fetchFiles(currentPath);
        } catch (err) {
            alert(formatError(err));
        }
    };

    const handleCreateFolder = async () => {
        const name = prompt("Enter folder name:");
        if (!name) return;
        try {
            await api.post('/files/action', {
                action: 'mkdir',
                path: `${currentPath === '/' ? '' : currentPath}/${name}`
            });
            fetchFiles(currentPath);
            fetchFiles(currentPath);
        } catch (err) {
            alert(formatError(err));
        }
    };

    const handleRename = async (file) => {
        const newName = prompt("Enter new name:", file.name);
        if (!newName || newName === file.name) return;
        try {
            await api.post('/files/action', {
                action: 'rename',
                path: file.path,
                new_name: newName
            });
            fetchFiles(currentPath);
            fetchFiles(currentPath);
        } catch (err) {
            alert(formatError(err));
        }
    };

    const handleUpload = async (e) => {
        const files = e.target.files;
        if (!files || files.length === 0) return;

        setUploading(true);
        const formData = new FormData();
        formData.append('path', currentPath);
        for (let i = 0; i < files.length; i++) {
            formData.append('files', files[i]);
        }

        try {
            await api.post('/files/upload', formData);
            await fetchFiles(currentPath);
        } catch (err) {
            alert(formatError(err));
        } finally {
            setUploading(false);
            if (fileInputRef.current) fileInputRef.current.value = '';
        }
    };

    /* Lock/Unlock Logic */
    const [isLocked, setIsLocked] = useState(true);
    const [showUnlockModal, setShowUnlockModal] = useState(false);
    const [unlockPassword, setUnlockPassword] = useState('');
    const [unlockError, setUnlockError] = useState(null);

    const handleUnlock = async (e) => {
        e.preventDefault();
        setUnlockError(null);
        try {
            await api.post('/auth/verify-system-password', { password: unlockPassword });
            setIsLocked(false);
            setShowUnlockModal(false);
            setUnlockPassword('');
        } catch (err) {
            setUnlockError("Incorrect password");
        }
    };

    const handleLock = () => {
        setIsLocked(true);
    };

    const handleUploadClick = () => {
        if (isLocked) {
            alert("Please unlock file system first.");
            return;
        }
        fileInputRef.current?.click();
    };

    /* Drag & Drop Handlers */
    const onDragEnter = (e) => {
        e.preventDefault();
        e.stopPropagation();
        dragCounter.current += 1;
        if (e.dataTransfer.items && e.dataTransfer.items.length > 0) {
            setIsDragging(true);
        }
    };

    const onDragLeave = (e) => {
        e.preventDefault();
        e.stopPropagation();
        dragCounter.current -= 1;
        if (dragCounter.current === 0) {
            setIsDragging(false);
        }
    };

    const onDragOver = (e) => {
        e.preventDefault();
        e.stopPropagation();
        e.dataTransfer.dropEffect = 'copy';
    };

    const onDrop = async (e) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(false);
        dragCounter.current = 0;

        if (user.role === 'viewer') return;
        if (isLocked) {
            alert("File system is locked. Please click the lock icon to enable uploads.");
            return;
        }

        const files = e.dataTransfer.files;
        if (!files || files.length === 0) return;

        setUploading(true);
        const formData = new FormData();
        formData.append('path', currentPath);
        for (let i = 0; i < files.length; i++) {
            formData.append('files', files[i]);
        }

        try {
            await api.post('/files/upload', formData);
            await fetchFiles(currentPath);
        } catch (err) {
            alert(formatError(err));
        } finally {
            setUploading(false);
        }
    };

    return (
        <div
            className={`h-full flex flex-col relative ${isDarkMode ? 'text-white' : 'text-gray-800'}`}
            onDragEnter={onDragEnter}
            onDragLeave={onDragLeave}
            onDragOver={onDragOver}
            onDrop={onDrop}
        >
            {/* Unlock Modal */}
            <AnimatePresence>
                {showUnlockModal && (
                    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
                        <motion.div
                            initial={{ opacity: 0, scale: 0.9 }}
                            animate={{ opacity: 1, scale: 1 }}
                            exit={{ opacity: 0, scale: 0.9 }}
                            className={`w-full max-w-sm p-6 rounded-2xl shadow-xl border ${isDarkMode ? 'bg-[#1a1b26] border-white/10' : 'bg-white border-gray-200'}`}
                        >
                            <h3 className="text-xl font-bold mb-4">Unlock File System (v2.1)</h3>
                            <p className={`text-sm mb-4 ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>
                                Enter the <b>System (Sudo) Password</b> to enable write access.
                            </p>

                            <form onSubmit={handleUnlock}>
                                <div className="mb-4">
                                    <input
                                        type="password"
                                        value={unlockPassword}
                                        onChange={(e) => setUnlockPassword(e.target.value)}
                                        placeholder="System Root/Sudo Password"
                                        className={`w-full px-4 py-2 rounded-lg border focus:ring-2 focus:target-ring focus:outline-none transition-all ${isDarkMode
                                            ? 'bg-black/20 border-white/10 focus:border-purple-500 focus:ring-purple-500/20'
                                            : 'bg-white border-gray-300 focus:border-purple-500 focus:ring-purple-200'
                                            }`}
                                        autoFocus
                                    />
                                    {unlockError && <p className="text-red-500 text-xs mt-1">{unlockError}</p>}
                                </div>

                                <div className="flex justify-end gap-2">
                                    <button
                                        type="button"
                                        onClick={() => setShowUnlockModal(false)}
                                        className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${isDarkMode ? 'hover:bg-white/5 text-gray-400' : 'hover:bg-gray-100 text-gray-600'
                                            }`}
                                    >
                                        Cancel
                                    </button>
                                    <button
                                        type="submit"
                                        className={`px-4 py-2 rounded-lg text-sm font-medium bg-${themeColors.accent} text-white hover:bg-opacity-90`}
                                    >
                                        Unlock
                                    </button>
                                </div>
                            </form>
                        </motion.div>
                    </div>
                )}
            </AnimatePresence>

            {uploading && (
                <div className="absolute inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center">
                    <div className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-2xl flex flex-col items-center">
                        <RefreshCw className="animate-spin text-purple-500 mb-4" size={32} />
                        <p className="font-medium">Uploading files...</p>
                    </div>
                </div>
            )}

            {/* Drop Zone Overlay */}
            <AnimatePresence>
                {isDragging && !isLocked && user.role !== 'viewer' && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="absolute inset-0 z-40 bg-purple-500/20 backdrop-blur-sm border-4 border-purple-500 border-dashed m-4 rounded-2xl flex items-center justify-center"
                    >
                        <div className="bg-white dark:bg-gray-800 p-8 rounded-2xl shadow-2xl flex flex-col items-center transform scale-110">
                            <Upload className="text-purple-500 mb-4 animate-bounce" size={48} />
                            <h3 className="text-2xl font-bold mb-2">Drop files to upload</h3>
                            <p className="text-gray-500">Release to start uploading to {currentPath === '/' ? 'Root' : currentPath}</p>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Toolbar */}
            <div className={`flex items-center justify-between p-4 border-b ${isDarkMode ? 'border-white/10' : 'border-gray-200'} bg-opacity-50 backdrop-blur-md`}>
                <div className="flex items-center gap-2 overflow-hidden">
                    <button onClick={() => handleNavigate('/')} className="p-2 hover:bg-white/10 rounded-lg">
                        <Home size={18} />
                    </button>

                    <div className="flex items-center text-sm font-mono overflow-x-auto no-scrollbar">
                        {currentPath.split('/').map((part, i, arr) => {
                            if (!part && i > 0) return null; // Skip empty parts except root
                            const path = arr.slice(0, i + 1).join('/') || '/';
                            return (
                                <div key={i} className="flex items-center">
                                    {i > 0 && <ChevronRight size={14} className="mx-1 text-gray-500" />}
                                    <button
                                        onClick={() => handleNavigate(path)}
                                        className={`px-2 py-1 rounded hover:bg-white/10 ${i === arr.length - 1 ? 'font-bold' : ''}`}
                                    >
                                        {part || '/'}
                                    </button>
                                </div>
                            );
                        })}
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    {user.role !== 'viewer' && (
                        <>
                            {/* Lock Toggle */}
                            <button
                                onClick={() => isLocked ? setShowUnlockModal(true) : handleLock()}
                                className={`p-2 rounded-lg transition-colors ${isLocked
                                    ? 'bg-red-500/10 text-red-500 hover:bg-red-500/20'
                                    : 'bg-green-500/10 text-green-500 hover:bg-green-500/20'
                                    }`}
                                title={isLocked ? "System Locked (Read-Only)" : "System Unlocked (Read-Write)"}
                            >
                                {isLocked ? <Lock size={18} /> : <Unlock size={18} />}
                            </button>

                            {!isLocked && (
                                <>
                                    <button
                                        onClick={handleCreateFolder}
                                        className={`p-2 rounded-lg transition-colors ${isDarkMode ? 'hover:bg-white/10' : 'hover:bg-gray-100'}`}
                                        title="Create Folder"
                                    >
                                        <FolderPlus size={18} />
                                    </button>
                                    <input
                                        type="file"
                                        multiple
                                        className="hidden"
                                        ref={fileInputRef}
                                        onChange={handleUpload}
                                    />
                                    <button
                                        onClick={handleUploadClick}
                                        disabled={uploading}
                                        className={`flex items-center gap-2 px-4 py-2 rounded-lg bg-${themeColors.accent} text-white hover:bg-opacity-90 transition-colors`}
                                    >
                                        {uploading ? <RefreshCw className="animate-spin" size={18} /> : <Upload size={18} />}
                                        <span className="hidden sm:inline">Upload</span>
                                    </button>
                                </>
                            )}
                        </>
                    )}
                    <button
                        onClick={() => fetchFiles(currentPath)}
                        className="p-2 hover:bg-white/10 rounded-lg"
                    >
                        <RefreshCw size={18} className={loading ? "animate-spin" : ""} />
                    </button>
                </div>
            </div>

            {/* File List */}
            <div className="flex-1 overflow-auto p-4">
                {error && (
                    <div className="p-4 mb-4 bg-red-500/20 text-red-500 rounded-lg border border-red-500/50">
                        {error}
                    </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                    {/* Parent Directory */}
                    {currentPath !== '/' && (
                        <div
                            onClick={handleUp}
                            className={`flex items-center gap-3 p-4 rounded-xl cursor-pointer transition-colors ${isDarkMode ? 'bg-white/5 hover:bg-white/10 border-white/5' : 'bg-white hover:bg-gray-50 border-gray-100'
                                } border`}
                        >
                            <CornerDownRight className="text-gray-400 rotate-180" size={24} />
                            <span className="font-medium">..</span>
                        </div>
                    )}

                    {files.map((file) => (
                        <motion.div
                            key={file.path}
                            initial={{ opacity: 0, scale: 0.95 }}
                            animate={{ opacity: 1, scale: 1 }}
                            whileHover={{ scale: 1.02 }}
                            onClick={() => file.type === 'directory' ? handleNavigate(file.path) : null}
                            className={`relative group flex items-start gap-3 p-4 rounded-xl cursor-pointer transition-all border ${isDarkMode
                                ? 'bg-white/5 hover:bg-white/10 border-white/5'
                                : 'bg-white hover:bg-gray-50 border-gray-100 shadow-sm'
                                }`}
                        >
                            <div className="mt-1">{getFileIcon(file)}</div>

                            <div className="flex-1 min-w-0 pr-28">
                                <h4 className="font-medium truncate" title={file.name}>
                                    {file.name}
                                </h4>
                                <div className="flex items-center justify-between text-xs text-gray-500 mt-1">
                                    <span>{file.type === 'file' ? formatSize(file.size) : 'Folder'}</span>
                                    <span>{new Date(file.modified).toLocaleDateString()}</span>
                                </div>
                            </div>

                            {/* Actions */}
                            <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity flex gap-1">
                                {file.type === 'file' && (
                                    <button
                                        onClick={(e) => { e.stopPropagation(); handleDownload(file); }}
                                        className="p-1.5 rounded-md hover:bg-purple-500 text-gray-400 hover:text-white transition-colors"
                                        title="Download"
                                    >
                                        <Download size={14} />
                                    </button>
                                )}
                                {user.role !== 'viewer' && !isLocked && (
                                    <>
                                        <button
                                            onClick={(e) => { e.stopPropagation(); handleRename(file); }}
                                            className="p-1.5 rounded-md hover:bg-blue-500 text-gray-400 hover:text-white transition-colors"
                                            title="Rename"
                                        >
                                            <Edit2 size={14} />
                                        </button>
                                        <button
                                            onClick={(e) => { e.stopPropagation(); handleDelete(file); }}
                                            className="p-1.5 rounded-md hover:bg-red-500 text-gray-400 hover:text-white transition-colors"
                                            title="Delete"
                                        >
                                            <Trash2 size={14} />
                                        </button>
                                    </>
                                )}
                            </div>
                        </motion.div>
                    ))}
                </div>

                {!loading && files.length === 0 && (
                    <div className="flex flex-col items-center justify-center h-64 text-gray-500">
                        <Folder size={48} className="mb-4 opacity-50" />
                        <p>Empty directory</p>
                    </div>
                )}
            </div>
        </div>
    );
}
