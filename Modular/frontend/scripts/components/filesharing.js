const FileSharingView = React.memo(({ backend, flatGoals, settings }) => {
    const [folders, setFolders] = React.useState([]);
    const [networkNodes, setNetworkNodes] = React.useState([]);
    const [selectedFolder, setSelectedFolder] = React.useState(null);
    const [folderTree, setFolderTree] = React.useState(null);
    const [changelog, setChangelog] = React.useState([]);
    const [retentionDays, setRetentionDays] = React.useState(30);
    const [retentionChanges, setRetentionChanges] = React.useState(100);
    const [goalBindings, setGoalBindings] = React.useState({});
    const [newFolderPath, setNewFolderPath] = React.useState('');
    const [loading, setLoading] = React.useState(false);

    const DEVICE_COLORS = ['#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981', '#ef4444', '#06b6d4', '#f97316'];

    const getDeviceColor = (deviceId) => {
        let hash = 0;
        for (let i = 0; i < deviceId.length; i++) hash = deviceId.charCodeAt(i) + ((hash << 5) - hash);
        return DEVICE_COLORS[Math.abs(hash) % DEVICE_COLORS.length];
    };

    const refreshFolders = () => {
        backend.request(JSON.stringify({action: 'get_mapped_folders'})).then(res => {
            const data = JSON.parse(res);
            setFolders(data.folders || []);
            setNetworkNodes(data.network_folders || []);
        });
    };

    const refreshFileTree = (folderPath) => {
        backend.request(JSON.stringify({action: 'get_folder_hierarchy', path: folderPath})).then(res => {
            const data = JSON.parse(res);
            setFolderTree(data.tree || null);
        });
    };

    const refreshChangelog = (folderPath) => {
        backend.request(JSON.stringify({action: 'get_folder_changelog', path: folderPath, days: retentionDays, max_changes: retentionChanges})).then(res => {
            const data = JSON.parse(res);
            setChangelog(data.changelog || []);
        });
    };

    const loadGoalBindings = () => {
        backend.request(JSON.stringify({action: 'get_goal_folder_bindings'})).then(res => {
            const data = JSON.parse(res);
            setGoalBindings(data.bindings || {});
        });
    };

    React.useEffect(() => {
        refreshFolders();
        loadGoalBindings();
    }, []);

    const handleSelectFolder = (path) => {
        setSelectedFolder(path);
        setLoading(true);
        refreshFileTree(path);
        refreshChangelog(path);
        setLoading(false);
    };

    const handleMapFolder = () => {
        if (!newFolderPath) return;
        backend.request(JSON.stringify({action: 'map_folder', path: newFolderPath})).then(() => {
            setNewFolderPath('');
            refreshFolders();
        });
    };

    const handleUnmapFolder = (path) => {
        backend.request(JSON.stringify({action: 'unmap_folder', path})).then(refreshFolders);
    };

    const handleOpenFolder = (path) => {
        backend.request(JSON.stringify({action: 'open_network_folder', path}));
    };

    const handleBindGoal = (folderPath, goalUuid) => {
        backend.request(JSON.stringify({action: 'bind_folder_goal', folder: folderPath, goal_uuid: goalUuid})).then(() => {
            loadGoalBindings();
        });
    };

    const handleApplyRetention = () => {
        backend.request(JSON.stringify({action: 'apply_retention_policy', days: retentionDays, max_changes: retentionChanges})).then(res => {
            const data = JSON.parse(res);
            alert(data.message || 'Retention policy applied');
        });
    };

    const renderTreeNode = (node, depth = 0) => {
        if (!node) return null;
        const isDir = node.type === 'directory';
        return (
            <div key={node.path} style={{paddingLeft: `${depth * 16}px`}}>
                <div className="flex items-center gap-2 py-1 px-2 rounded hover:bg-white/5 cursor-pointer text-xs group" onClick={() => isDir && handleSelectFolder(node.path)}>
                    <i className={`fas ${isDir ? 'fa-folder text-yellow-400' : 'fa-file text-gray-400'}`}></i>
                    <span className="text-gray-300 truncate flex-1">{node.name}</span>
                    {node.size !== undefined && <span className="text-gray-500 text-[10px]">{(node.size / 1024).toFixed(1)}KB</span>}
                    {node.devices && node.devices.map((dev, i) => (
                        <span key={i} className="w-2 h-2 rounded-full" style={{backgroundColor: getDeviceColor(dev)}} title={dev}></span>
                    ))}
                </div>
                {isDir && node.children && node.children.map(child => renderTreeNode(child, depth + 1))}
            </div>
        );
    };

    return (
        <div className="flex flex-col h-full fade-in">
            <div className="flex justify-between items-center mb-6 shrink-0">
                <h2 className="text-2xl font-serif font-bold text-white tracking-widest uppercase drop-shadow-md">
                    <i className="fas fa-share-alt mr-3 text-blue-400"></i>File Sharing
                </h2>
                <div className="flex gap-3">
                    <button onClick={handleApplyRetention} className="glass-button px-4 py-2 rounded text-xs font-bold text-yellow-300 uppercase border border-yellow-500/30 hover:bg-yellow-900/30">
                        <i className="fas fa-broom mr-2"></i>Apply Retention
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-grow overflow-hidden">
                {/* Left: Mapped Folders & Network Nodes */}
                <div className="glass-panel p-4 overflow-y-auto custom-scrollbar">
                    <div className="text-blue-400 font-bold uppercase tracking-widest text-xs border-b border-white/10 pb-2 mb-3">Mapped Folders</div>
                    <div className="flex gap-2 mb-3">
                        <input type="text" value={newFolderPath} onChange={e => setNewFolderPath(e.target.value)} placeholder="C:/Users/..." className="glass-input p-2 rounded text-xs flex-grow" />
                        <button onClick={handleMapFolder} className="glass-button px-3 py-2 rounded text-xs font-bold text-green-300 border border-green-500/30 hover:bg-green-900/30">
                            <i className="fas fa-plus"></i>
                        </button>
                    </div>
                    <div className="space-y-2 mb-4">
                        {folders.length > 0 ? folders.map((path, i) => (
                            <div key={i} className={`flex items-center gap-2 p-2 rounded-lg cursor-pointer transition-all ${selectedFolder === path ? 'bg-blue-900/30 border border-blue-500/50' : 'bg-white/5 border border-white/5 hover:bg-white/10'}`} onClick={() => handleSelectFolder(path)}>
                                <i className="fas fa-folder text-yellow-400"></i>
                                <span className="text-xs text-gray-300 truncate flex-1 font-mono">{path}</span>
                                <button onClick={(e) => { e.stopPropagation(); handleOpenFolder(path); }} className="text-blue-400 hover:text-blue-300 opacity-0 group-hover:opacity-100"><i className="fas fa-external-link-alt text-[10px]"></i></button>
                                <button onClick={(e) => { e.stopPropagation(); handleUnmapFolder(path); }} className="text-red-400 hover:text-red-300 opacity-0 group-hover:opacity-100"><i className="fas fa-times text-[10px]"></i></button>
                            </div>
                        )) : <div className="text-xs text-gray-500 italic text-center py-4">No folders mapped</div>}
                    </div>

                    <div className="text-blue-400 font-bold uppercase tracking-widest text-xs border-b border-white/10 pb-2 mb-3">Network Nodes</div>
                    <div className="space-y-2">
                        {networkNodes.map((node, i) => (
                            <div key={i} className="flex items-center gap-3 p-2 bg-white/5 rounded-lg border border-white/5">
                                <div className="w-3 h-3 rounded-full" style={{backgroundColor: getDeviceColor(node.device_id)}}></div>
                                <div className="flex-1 min-w-0">
                                    <div className="text-xs font-bold text-white truncate">{node.device_id.substring(0, 12)} {node.is_local ? '(This PC)' : ''}</div>
                                    <div className="text-[10px] text-gray-400">{node.file_count} files - {node.last_update}</div>
                                </div>
                                {!node.is_local && <button onClick={() => { if(confirm(`Clone data from ${node.device_id.substring(0,8)}?`)) backend.request(JSON.stringify({action: 'hard_clone_remote', target_device: node.device_id})); }} className="text-yellow-400 hover:text-yellow-300 text-[10px]"><i className="fas fa-download"></i></button>}
                            </div>
                        ))}
                    </div>

                    <div className="text-blue-400 font-bold uppercase tracking-widest text-xs border-b border-white/10 pb-2 mb-3 mt-4">Retention Policy</div>
                    <div className="space-y-2">
                        <div className="flex items-center gap-2">
                            <label className="text-[10px] text-gray-400 w-20">Days:</label>
                            <input type="number" value={retentionDays} onChange={e => setRetentionDays(parseInt(e.target.value))} className="glass-input p-1.5 rounded text-xs w-20" />
                        </div>
                        <div className="flex items-center gap-2">
                            <label className="text-[10px] text-gray-400 w-20">Max Changes:</label>
                            <input type="number" value={retentionChanges} onChange={e => setRetentionChanges(parseInt(e.target.value))} className="glass-input p-1.5 rounded text-xs w-20" />
                        </div>
                    </div>
                </div>

                {/* Center: File Hierarchy Tree */}
                <div className="glass-panel p-4 overflow-y-auto custom-scrollbar">
                    <div className="text-blue-400 font-bold uppercase tracking-widest text-xs border-b border-white/10 pb-2 mb-3">
                        <i className="fas fa-sitemap mr-2"></i>File Hierarchy
                    </div>
                    {selectedFolder ? (
                        <div>
                            <div className="text-xs text-gray-400 mb-2 font-mono truncate">{selectedFolder}</div>
                            {folderTree ? (
                                <div className="space-y-0.5">{renderTreeNode(folderTree)}</div>
                            ) : (
                                <div className="text-center py-8"><i className="fas fa-spinner fa-spin text-blue-400"></i></div>
                            )}
                        </div>
                    ) : (
                        <div className="text-center py-12 text-gray-500">
                            <i className="fas fa-folder-open text-3xl mb-3 opacity-30"></i>
                            <p className="text-xs">Select a folder to view hierarchy</p>
                        </div>
                    )}

                    {/* Goal Binding */}
                    {selectedFolder && (
                        <div className="mt-4 border-t border-white/10 pt-3">
                            <div className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-2">Assign to Goal</div>
                            <select value={goalBindings[selectedFolder] || ''} onChange={e => handleBindGoal(selectedFolder, e.target.value)} className="glass-input p-2 rounded text-xs w-full">
                                <option value="">-- No goal --</option>
                                {flatGoals && flatGoals.map((g, i) => (
                                    <option key={i} value={g.uuid}>{g.path || g.title || g.name}</option>
                                ))}
                            </select>
                        </div>
                    )}
                </div>

                {/* Right: Changelog */}
                <div className="glass-panel p-4 overflow-y-auto custom-scrollbar">
                    <div className="text-blue-400 font-bold uppercase tracking-widest text-xs border-b border-white/10 pb-2 mb-3">
                        <i className="fas fa-history mr-2"></i>Changelog
                    </div>
                    {selectedFolder ? (
                        changelog.length > 0 ? (
                            <div className="space-y-2">
                                {changelog.map((entry, i) => (
                                    <div key={i} className="p-2 bg-white/5 rounded-lg border border-white/5 text-xs">
                                        <div className="flex items-center gap-2 mb-1">
                                            <div className="w-2 h-2 rounded-full" style={{backgroundColor: getDeviceColor(entry.device_id || '')}}></div>
                                            <span className="text-gray-400 text-[10px]">{entry.timestamp}</span>
                                            <span className={`text-[10px] px-1.5 py-0.5 rounded ${entry.action === 'added' ? 'bg-green-900/30 text-green-400' : entry.action === 'modified' ? 'bg-yellow-900/30 text-yellow-400' : 'bg-red-900/30 text-red-400'}`}>
                                                {entry.action}
                                            </span>
                                        </div>
                                        <div className="text-gray-300 font-mono truncate">{entry.file_path}</div>
                                        <div className="text-[10px] text-gray-500 mt-1">by {entry.device_id ? entry.device_id.substring(0, 8) : 'Unknown'}</div>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="text-center py-8 text-gray-500 text-xs">No changes recorded</div>
                        )
                    ) : (
                        <div className="text-center py-12 text-gray-500">
                            <i className="fas fa-clock text-3xl mb-3 opacity-30"></i>
                            <p className="text-xs">Select a folder to view changelog</p>
                        </div>
                    )}
                </div>
            </div>

            {/* Sync Status Bar */}
            <div className="glass-panel p-3 mt-4 flex items-center justify-between shrink-0">
                <div className="flex items-center gap-4">
                    <div className={`w-3 h-3 rounded-full ${settings.git_status === 'connected' ? 'bg-green-500 animate-pulse' : settings.git_status === 'error' ? 'bg-red-500' : 'bg-gray-500'}`}></div>
                    <span className="text-xs font-medium text-gray-300">{settings.git_status === 'connected' ? 'Connected' : settings.git_status === 'syncing' ? 'Syncing...' : 'Disconnected'}</span>
                    <span className="text-[10px] text-gray-500 font-mono">Device: {settings.device_id ? settings.device_id.substring(0, 12) : 'Loading...'}</span>
                </div>
                <div className="flex gap-3">
                    <button onClick={() => backend.request(JSON.stringify({action: 'get_sync_status'}))} className="glass-button px-3 py-1.5 rounded text-[10px] font-bold text-blue-300 border border-blue-500/30 hover:bg-blue-900/30">
                        <i className="fas fa-satellite-dish mr-1"></i>Verify
                    </button>
                    <button onClick={() => backend.request(JSON.stringify({action: 'sync_now'}))} className="glass-button px-3 py-1.5 rounded text-[10px] font-bold text-green-300 border border-green-500/30 hover:bg-green-900/30">
                        <i className="fas fa-sync-alt mr-1"></i>Sync Now
                    </button>
                </div>
            </div>
        </div>
    );
});
