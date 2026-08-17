var FileSharingHelper = {
    DEVICE_COLORS: ['#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981', '#ef4444', '#06b6d4', '#f97316'],
    getDeviceColor: function(deviceId) {
        var hash = 0;
        for (var i = 0; i < deviceId.length; i++) hash = deviceId.charCodeAt(i) + ((hash << 5) - hash);
        return this.DEVICE_COLORS[Math.abs(hash) % this.DEVICE_COLORS.length];
    },
    renderTreeNode: function(node, level, onFolderSelect) {
        var depth = level || 0;
        if (!node) return null;
        var isDir = node.type === 'directory';
        var padStyle = {paddingLeft: (depth * 16) + 'px'};
        var self = this;
        return (
            <div key={node.path} style={padStyle}>
                <div className="flex items-center gap-2 py-1 px-2 rounded hover:bg-white/5 cursor-pointer text-xs group" onClick={function() { if (isDir) onFolderSelect(node.path); }}>
                    <i className={'fas ' + (isDir ? 'fa-folder text-yellow-400' : 'fa-file text-gray-400')}></i>
                    <span className="text-gray-300 truncate flex-1">{node.name}</span>
                    {node.size !== undefined && <span className="text-gray-500 text-[10px]">{(node.size / 1024).toFixed(1)}KB</span>}
                    {node.devices && node.devices.map(function(dev, i) {
                        return <span key={i} className="w-2 h-2 rounded-full" style={{backgroundColor: self.getDeviceColor(dev)}} title={dev}></span>;
                    })}
                </div>
                {isDir && node.children && node.children.map(function(child) { return self.renderTreeNode(child, depth + 1, onFolderSelect); })}
            </div>
        );
    }
};

var FileSharingView = React.memo(function(props) {
    var backend = props.backend;
    var flatGoals = props.flatGoals;
    var settings = props.settings;

    var _folders = React.useState([]);
    var folders = _folders[0];
    var setFolders = _folders[1];
    var _networkNodes = React.useState([]);
    var networkNodes = _networkNodes[0];
    var setNetworkNodes = _networkNodes[1];
    var _selectedFolder = React.useState(null);
    var selectedFolder = _selectedFolder[0];
    var setSelectedFolder = _selectedFolder[1];
    var _folderTree = React.useState(null);
    var folderTree = _folderTree[0];
    var setFolderTree = _folderTree[1];
    var _changelog = React.useState([]);
    var changelog = _changelog[0];
    var setChangelog = _changelog[1];
    var _retentionDays = React.useState(30);
    var retentionDays = _retentionDays[0];
    var setRetentionDays = _retentionDays[1];
    var _retentionChanges = React.useState(100);
    var retentionChanges = _retentionChanges[0];
    var setRetentionChanges = _retentionChanges[1];
    var _goalBindings = React.useState({});
    var goalBindings = _goalBindings[0];
    var setGoalBindings = _goalBindings[1];
    var _newFolderPath = React.useState('');
    var newFolderPath = _newFolderPath[0];
    var setNewFolderPath = _newFolderPath[1];
    var _loading = React.useState(false);
    var loading = _loading[0];
    var setLoading = _loading[1];

    function refreshFolders() {
        backend.request(JSON.stringify({action: 'get_mapped_folders'})).then(function(res) {
            var data = JSON.parse(res);
            setFolders(data.folders || []);
            setNetworkNodes(data.network_folders || []);
        });
    }

    function refreshFileTree(folderPath) {
        backend.request(JSON.stringify({action: 'get_folder_hierarchy', path: folderPath})).then(function(res) {
            var data = JSON.parse(res);
            setFolderTree(data.tree || null);
        });
    }

    function refreshChangelog(folderPath) {
        backend.request(JSON.stringify({action: 'get_folder_changelog', path: folderPath, days: retentionDays, max_changes: retentionChanges})).then(function(res) {
            var data = JSON.parse(res);
            setChangelog(data.changelog || []);
        });
    }

    function loadGoalBindings() {
        backend.request(JSON.stringify({action: 'get_goal_folder_bindings'})).then(function(res) {
            var data = JSON.parse(res);
            setGoalBindings(data.bindings || {});
        });
    }

    React.useEffect(function() {
        refreshFolders();
        loadGoalBindings();
    }, []);

    function handleSelectFolder(path) {
        setSelectedFolder(path);
        setLoading(true);
        refreshFileTree(path);
        refreshChangelog(path);
        setLoading(false);
    }

    function handleMapFolder() {
        if (!newFolderPath) return;
        backend.request(JSON.stringify({action: 'map_folder', path: newFolderPath})).then(function() {
            setNewFolderPath('');
            refreshFolders();
        });
    }

    function handleUnmapFolder(path) {
        backend.request(JSON.stringify({action: 'unmap_folder', path: path})).then(refreshFolders);
    }

    function handleOpenFolder(path) {
        backend.request(JSON.stringify({action: 'open_network_folder', path: path}));
    }

    function handleBindGoal(folderPath, goalUuid) {
        backend.request(JSON.stringify({action: 'bind_folder_goal', folder: folderPath, goal_uuid: goalUuid})).then(function() {
            loadGoalBindings();
        });
    }

    function handleApplyRetention() {
        backend.request(JSON.stringify({action: 'apply_retention_policy', days: retentionDays, max_changes: retentionChanges})).then(function(res) {
            var data = JSON.parse(res);
            alert(data.message || 'Retention policy applied');
        });
    }

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
                <div className="glass-panel p-4 overflow-y-auto custom-scrollbar">
                    <div className="text-blue-400 font-bold uppercase tracking-widest text-xs border-b border-white/10 pb-2 mb-3">Mapped Folders</div>
                    <div className="flex gap-2 mb-3">
                        <input type="text" value={newFolderPath} onChange={function(e) { setNewFolderPath(e.target.value); }} placeholder="C:/Users/..." className="glass-input p-2 rounded text-xs flex-grow" />
                        <button onClick={handleMapFolder} className="glass-button px-3 py-2 rounded text-xs font-bold text-green-300 border border-green-500/30 hover:bg-green-900/30">
                            <i className="fas fa-plus"></i>
                        </button>
                    </div>
                    <div className="space-y-2 mb-4">
                        {folders.length > 0 ? folders.map(function(path, i) {
                            return (
                                <div key={i} className={'flex items-center gap-2 p-2 rounded-lg cursor-pointer transition-all ' + (selectedFolder === path ? 'bg-blue-900/30 border border-blue-500/50' : 'bg-white/5 border border-white/5 hover:bg-white/10')} onClick={function() { handleSelectFolder(path); }}>
                                    <i className="fas fa-folder text-yellow-400"></i>
                                    <span className="text-xs text-gray-300 truncate flex-1 font-mono">{path}</span>
                                    <button onClick={function(e) { e.stopPropagation(); handleOpenFolder(path); }} className="text-blue-400 hover:text-blue-300"><i className="fas fa-external-link-alt text-[10px]"></i></button>
                                    <button onClick={function(e) { e.stopPropagation(); handleUnmapFolder(path); }} className="text-red-400 hover:text-red-300"><i className="fas fa-times text-[10px]"></i></button>
                                </div>
                            );
                        }) : <div className="text-xs text-gray-500 italic text-center py-4">No folders mapped</div>}
                    </div>

                    <div className="text-blue-400 font-bold uppercase tracking-widest text-xs border-b border-white/10 pb-2 mb-3">Network Nodes</div>
                    <div className="space-y-2">
                        {networkNodes.map(function(node, i) {
                            return (
                                <div key={i} className="flex items-center gap-3 p-2 bg-white/5 rounded-lg border border-white/5">
                                    <div className="w-3 h-3 rounded-full" style={{backgroundColor: FileSharingHelper.getDeviceColor(node.device_id)}}></div>
                                    <div className="flex-1 min-w-0">
                                        <div className="text-xs font-bold text-white truncate">{node.device_id.substring(0, 12)} {node.is_local ? '(This PC)' : ''}</div>
                                        <div className="text-[10px] text-gray-400">{node.file_count} files - {node.last_update}</div>
                                    </div>
                                    {!node.is_local && <button onClick={function() { if(confirm('Clone data from ' + node.device_id.substring(0,8) + '?')) backend.request(JSON.stringify({action: 'hard_clone_remote', target_device: node.device_id})); }} className="text-yellow-400 hover:text-yellow-300 text-[10px]"><i className="fas fa-download"></i></button>}
                                </div>
                            );
                        })}
                    </div>

                    <div className="text-blue-400 font-bold uppercase tracking-widest text-xs border-b border-white/10 pb-2 mb-3 mt-4">Retention Policy</div>
                    <div className="space-y-2">
                        <div className="flex items-center gap-2">
                            <label className="text-[10px] text-gray-400 w-20">Days:</label>
                            <input type="number" value={retentionDays} onChange={function(e) { setRetentionDays(parseInt(e.target.value)); }} className="glass-input p-1.5 rounded text-xs w-20" />
                        </div>
                        <div className="flex items-center gap-2">
                            <label className="text-[10px] text-gray-400 w-20">Max Changes:</label>
                            <input type="number" value={retentionChanges} onChange={function(e) { setRetentionChanges(parseInt(e.target.value)); }} className="glass-input p-1.5 rounded text-xs w-20" />
                        </div>
                    </div>
                </div>

                <div className="glass-panel p-4 overflow-y-auto custom-scrollbar">
                    <div className="text-blue-400 font-bold uppercase tracking-widest text-xs border-b border-white/10 pb-2 mb-3">
                        <i className="fas fa-sitemap mr-2"></i>File Hierarchy
                    </div>
                    {selectedFolder ? (
                        <div>
                            <div className="text-xs text-gray-400 mb-2 font-mono truncate">{selectedFolder}</div>
                            {folderTree ? (
                                <div className="space-y-0.5">{FileSharingHelper.renderTreeNode(folderTree, 0, handleSelectFolder)}</div>
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

                    {selectedFolder && (
                        <div className="mt-4 border-t border-white/10 pt-3">
                            <div className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-2">Assign to Goal</div>
                            <select value={goalBindings[selectedFolder] || ''} onChange={function(e) { handleBindGoal(selectedFolder, e.target.value); }} className="glass-input p-2 rounded text-xs w-full">
                                <option value="">-- No goal --</option>
                                {flatGoals && flatGoals.map(function(g, i) {
                                    return <option key={i} value={g.uuid}>{g.path || g.title || g.name}</option>;
                                })}
                            </select>
                        </div>
                    )}
                </div>

                <div className="glass-panel p-4 overflow-y-auto custom-scrollbar">
                    <div className="text-blue-400 font-bold uppercase tracking-widest text-xs border-b border-white/10 pb-2 mb-3">
                        <i className="fas fa-history mr-2"></i>Changelog
                    </div>
                    {selectedFolder ? (
                        changelog.length > 0 ? (
                            <div className="space-y-2">
                                {changelog.map(function(entry, i) {
                                    return (
                                        <div key={i} className="p-2 bg-white/5 rounded-lg border border-white/5 text-xs">
                                            <div className="flex items-center gap-2 mb-1">
                                                <div className="w-2 h-2 rounded-full" style={{backgroundColor: FileSharingHelper.getDeviceColor(entry.device_id || '')}}></div>
                                                <span className="text-gray-400 text-[10px]">{entry.timestamp}</span>
                                                <span className={'text-[10px] px-1.5 py-0.5 rounded ' + (entry.action === 'added' ? 'bg-green-900/30 text-green-400' : entry.action === 'modified' ? 'bg-yellow-900/30 text-yellow-400' : 'bg-red-900/30 text-red-400')}>
                                                    {entry.action}
                                                </span>
                                            </div>
                                            <div className="text-gray-300 font-mono truncate">{entry.file_path}</div>
                                            <div className="text-[10px] text-gray-500 mt-1">by {entry.device_id ? entry.device_id.substring(0, 8) : 'Unknown'}</div>
                                        </div>
                                    );
                                })}
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

            <div className="glass-panel p-3 mt-4 flex items-center justify-between shrink-0">
                <div className="flex items-center gap-4">
                    <div className={'w-3 h-3 rounded-full ' + (settings.git_status === 'connected' ? 'bg-green-500 animate-pulse' : settings.git_status === 'error' ? 'bg-red-500' : 'bg-gray-500')}></div>
                    <span className="text-xs font-medium text-gray-300">{settings.git_status === 'connected' ? 'Connected' : settings.git_status === 'syncing' ? 'Syncing...' : 'Disconnected'}</span>
                    <span className="text-[10px] text-gray-500 font-mono">Device: {settings.device_id ? settings.device_id.substring(0, 12) : 'Loading...'}</span>
                </div>
                <div className="flex gap-3">
                    <button onClick={function() { backend.request(JSON.stringify({action: 'get_sync_status'})); }} className="glass-button px-3 py-1.5 rounded text-[10px] font-bold text-blue-300 border border-blue-500/30 hover:bg-blue-900/30">
                        <i className="fas fa-satellite-dish mr-1"></i>Verify
                    </button>
                    <button onClick={function() { backend.request(JSON.stringify({action: 'sync_now'})); }} className="glass-button px-3 py-1.5 rounded text-[10px] font-bold text-green-300 border border-green-500/30 hover:bg-green-900/30">
                        <i className="fas fa-sync-alt mr-1"></i>Sync Now
                    </button>
                </div>
            </div>
        </div>
    );
});
