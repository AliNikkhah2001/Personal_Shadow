const SettingsView = React.memo(({ settings, setSettings, backend, networkFolders, setNetworkFolders, activityLogs, syncLogs }) => {
    const handleChange = useCallback((k, v) => {
        setSettings(prev => ({...prev, [k]: v}));
    }, []);

    const saveSettings = useCallback(() => {
        backend.request(JSON.stringify({action: 'save_settings', data: settings}));
    }, [backend, settings]);

    const openFileDialog = useCallback((key) => {
        backend.request(JSON.stringify({action: 'open_file_dialog'})).then(res => {
            const data = JSON.parse(res);
            if(data.path) handleChange(key, data.path);
        });
    }, [backend, handleChange]);

    const [showProcessModal, setShowProcessModal] = useState(false);
    const [confirmReset, setConfirmReset] = useState(false);
    
    const [fAge, setFAge] = useState(settings.health_age || 25);
    const [fHeight, setFHeight] = useState(settings.health_height || 175);
    const [fWeight, setFWeight] = useState(settings.health_weight || 70);
    const [fGender, setFGender] = useState(settings.health_gender || 'Male');
    const [fActivity, setFActivity] = useState(settings.health_activity || 1.2);
    const [fDeficit, setFDeficit] = useState(settings.health_deficit || 500);

    const saveProfile = useCallback(() => {
        const hData = { age: fAge, height: fHeight, weight: fWeight, gender: fGender, activity: fActivity, deficit_goal: fDeficit };
        backend.request(JSON.stringify({action: 'manage_health', sub: 'save_profile', data: hData}));
        handleChange('health_age', fAge);
        handleChange('health_height', fHeight);
        handleChange('health_weight', fWeight);
        handleChange('health_gender', fGender);
        handleChange('health_activity', fActivity);
        handleChange('health_deficit', fDeficit);
    }, [backend, fAge, fHeight, fWeight, fGender, fActivity, fDeficit, handleChange]);

    const handleReset = useCallback(() => {
        backend.request(JSON.stringify({action: 'reset_data'})).then(() => {
            setConfirmReset(false);
        });
    }, [backend]);

    return (
        <div className="flex flex-col h-full fade-in">
            <div className="flex justify-between items-center mb-6 shrink-0">
                <h2 className="text-2xl font-serif font-bold text-white tracking-widest uppercase drop-shadow-md">Settings</h2>
                <div className="flex gap-4 items-center">

                    <button onClick={saveSettings} className="glass-button px-6 py-2 rounded text-xs font-bold text-white uppercase bg-blue-600/30 hover:bg-blue-600 border-blue-500/50 shadow-lg">Apply All Settings</button>
                </div>
            </div>
            <div className="glass-panel p-6 flex-grow overflow-y-auto custom-scrollbar">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-6 max-w-4xl">

                    {/* Health Profile */}
                    <div className="md:col-span-2 text-green-400 font-bold uppercase tracking-widest text-xs border-b border-white/10 pb-1 mt-4">Physiological Profile</div>
                    <div className="md:col-span-2 grid grid-cols-2 gap-4">
                        <div className="flex flex-col gap-1">
                            <label className="text-[10px] text-gray-400 uppercase tracking-widest">Age</label>
                            <input type="number" className="glass-input p-2 rounded text-sm" value={fAge} onChange={e=>setFAge(parseInt(e.target.value))} />
                        </div>
                        <div className="flex flex-col gap-1">
                            <label className="text-[10px] text-gray-400 uppercase tracking-widest">Height (cm)</label>
                            <input type="number" className="glass-input p-2 rounded text-sm" value={fHeight} onChange={e=>setFHeight(parseFloat(e.target.value))} />
                        </div>
                        <div className="flex flex-col gap-1">
                            <label className="text-[10px] text-gray-400 uppercase tracking-widest">Weight (kg)</label>
                            <input type="number" className="glass-input p-2 rounded text-sm" value={fWeight} onChange={e=>setFWeight(parseFloat(e.target.value))} />
                        </div>
                        <div className="flex flex-col gap-1">
                            <label className="text-[10px] text-gray-400 uppercase tracking-widest">Gender</label>
                            <select className="glass-input p-2 rounded text-sm" value={fGender} onChange={e=>setFGender(e.target.value)}><option>Male</option><option>Female</option></select>
                        </div>
                        <div className="flex flex-col gap-1">
                            <label className="text-[10px] text-gray-400 uppercase tracking-widest">Activity Level</label>
                            <select className="glass-input p-2 rounded text-sm" value={fActivity} onChange={e=>setFActivity(parseFloat(e.target.value))}>
                                <option value="1.2">Sedentary (1.2)</option>
                                <option value="1.375">Light (1.375)</option>
                                <option value="1.55">Moderate (1.55)</option>
                                <option value="1.725">Intense (1.725)</option>
                            </select>
                        </div>
                        <div className="flex flex-col gap-1">
                            <label className="text-[10px] text-gray-400 uppercase tracking-widest">Daily Deficit Goal (kcal)</label>
                            <input type="number" className="glass-input p-2 rounded text-sm" value={fDeficit} onChange={e=>setFDeficit(parseFloat(e.target.value))} />
                        </div>
                        <div className="col-span-2 mt-2">
                            <button onClick={saveProfile} className="glass-button w-full py-2 rounded text-[11px] font-bold tracking-widest text-green-300 uppercase shadow-lg border-green-500/30">Save Profile Metadata</button>
                        </div>
                    </div>

                    {/* App Monitoring */}
                    <div className="md:col-span-2 text-blue-400 font-bold uppercase tracking-widest text-xs border-b border-white/10 pb-1 mt-4">App Monitoring</div>
                    <div className="md:col-span-2 flex flex-col gap-3">
                        <div className="flex items-center gap-4">
                            <label className="text-xs font-bold text-gray-400 uppercase tracking-widest">Enable App Monitoring</label>
                            <input type="checkbox" checked={settings.app_monitoring_enabled || false} 
                                   onChange={e => {
                                       const checked = e.target.checked;
                                       handleChange('app_monitoring_enabled', checked);
                                       backend.request(JSON.stringify({action: 'set_app_monitoring', enabled: checked}));
                                   }} 
                                   className="w-5 h-5 rounded bg-black/40 border border-white/20 accent-blue-500" />
                        </div>
                        <div className="flex items-center gap-4">
                            <label className="text-xs font-bold text-gray-400 uppercase tracking-widest">Auto-Block Disallowed Apps</label>
                            <input type="checkbox" checked={settings.auto_block || false} 
                                   onChange={e => {
                                       const checked = e.target.checked;
                                       handleChange('auto_block', checked);
                                       backend.request(JSON.stringify({action: 'set_auto_block', enabled: checked}));
                                   }} 
                                   className="w-5 h-5 rounded bg-black/40 border border-white/20 accent-red-500" />
                        </div>
                        <div className="flex gap-3 mt-2">
                            <button onClick={() => {
                                backend.request(JSON.stringify({action: 'get_processes'})).then(res => {
                                    const data = JSON.parse(res);
                                    if (data.processes && data.processes.length > 0) {
                                        setSettings(prev => ({...prev, process_list: data.processes}));
                                        setShowProcessModal(true);
                                    }
                                });
                            }} className="glass-button px-6 py-2 rounded text-xs font-bold tracking-widest text-white uppercase bg-green-600/30 border-green-500/50 hover:bg-green-600">
                                <i className="fas fa-sync mr-2"></i> Refresh Process List
                            </button>
                            <button onClick={() => {
                                backend.request(JSON.stringify({action: 'check_current_distractions'}));
                            }} className="glass-button px-6 py-2 rounded text-xs font-bold tracking-widest text-white uppercase bg-blue-600/30 border-blue-500/50 hover:bg-blue-600">
                                <i className="fas fa-search mr-2"></i> Check Distractions
                            </button>
                        </div>
                        <div className="flex gap-6 mt-2">
                            <div className="flex-1">
                                <label className="text-[10px] font-bold text-green-400 uppercase tracking-widest">Allowed Apps ({settings.allowed_apps?.length || 0})</label>
                                <div className="flex flex-wrap gap-1 mt-1 max-h-20 overflow-y-auto">
                                    {settings.allowed_apps && settings.allowed_apps.length > 0 ? (
                                        settings.allowed_apps.map((app, i) => (
                                            <span key={i} className="text-xs bg-green-900/30 text-green-400 px-2 py-0.5 rounded border border-green-500/30 flex items-center gap-1">
                                                {app}
                                                <button onClick={() => {
                                                    const newList = settings.allowed_apps.filter((_, idx) => idx !== i);
                                                    handleChange('allowed_apps', newList);
                                                    backend.request(JSON.stringify({action: 'set_allowed_apps', apps: newList}));
                                                }} className="text-red-400 hover:text-red-300">
                                                    <i className="fas fa-times text-[8px]"></i>
                                                </button>
                                            </span>
                                        ))
                                    ) : (
                                        <span className="text-xs text-gray-500 italic">No allowed apps configured</span>
                                    )}
                                </div>
                            </div>
                            <div className="flex-1">
                                <label className="text-[10px] font-bold text-red-400 uppercase tracking-widest">Blocked Apps ({settings.blocked_apps?.length || 0})</label>
                                <div className="flex flex-wrap gap-1 mt-1 max-h-20 overflow-y-auto">
                                    {settings.blocked_apps && settings.blocked_apps.length > 0 ? (
                                        settings.blocked_apps.map((app, i) => (
                                            <span key={i} className="text-xs bg-red-900/30 text-red-400 px-2 py-0.5 rounded border border-red-500/30 flex items-center gap-1">
                                                {app}
                                                <button onClick={() => {
                                                    const newList = settings.blocked_apps.filter((_, idx) => idx !== i);
                                                    handleChange('blocked_apps', newList);
                                                    backend.request(JSON.stringify({action: 'set_blocked_apps', apps: newList}));
                                                }} className="text-red-400 hover:text-red-300">
                                                    <i className="fas fa-times text-[8px]"></i>
                                                </button>
                                            </span>
                                        ))
                                    ) : (
                                        <span className="text-xs text-gray-500 italic">No blocked apps configured</span>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Process Selection Modal */}
                    {showProcessModal && (
                        <div className="fixed inset-0 bg-black/90 z-50 flex items-center justify-center p-4 backdrop-blur-md">
                            <div className="glass-panel p-6 max-w-2xl w-full max-h-[80vh] overflow-y-auto">
                                <div className="flex justify-between items-center mb-4">
                                    <h3 className="text-white font-bold text-xl">📋 Running Applications</h3>
                                    <button onClick={() => setShowProcessModal(false)} className="text-gray-400 hover:text-white">
                                        <i className="fas fa-times text-xl"></i>
                                    </button>
                                </div>
                                <div className="flex gap-3 mb-4">
                                    <button onClick={() => {
                                        const checkedBoxes = document.querySelectorAll('.process-checkbox:checked');
                                        checkedBoxes.forEach(cb => {
                                            const appName = cb.getAttribute('data-app');
                                            const action = document.querySelector(`[data-action="${appName}"]`).value;
                                            if (action === 'allow') {
                                                const current = settings.allowed_apps || [];
                                                if (!current.includes(appName)) {
                                                    handleChange('allowed_apps', [...current, appName]);
                                                    backend.request(JSON.stringify({action: 'set_allowed_apps', apps: [...current, appName]}));
                                                }
                                            } else if (action === 'block') {
                                                const current = settings.blocked_apps || [];
                                                if (!current.includes(appName)) {
                                                    handleChange('blocked_apps', [...current, appName]);
                                                    backend.request(JSON.stringify({action: 'set_blocked_apps', apps: [...current, appName]}));
                                                }
                                            }
                                        });
                                        setShowProcessModal(false);
                                    }} className="glass-button px-4 py-2 rounded text-xs font-bold tracking-widest text-white uppercase bg-blue-600/30 border-blue-500/50 hover:bg-blue-600">
                                        Apply Rules
                                    </button>
                                </div>
                                <div className="flex flex-col gap-1 max-h-60 overflow-y-auto">
                                    {settings.process_list && settings.process_list.map((p, i) => {
                                        const isAllowed = settings.allowed_apps?.includes(p.name);
                                        const isBlocked = settings.blocked_apps?.includes(p.name);
                                        return (
                                            <div key={i} className="flex items-center gap-3 p-2 bg-white/5 rounded border border-white/10 hover:bg-white/10 transition">
                                                <input type="checkbox" className="process-checkbox" data-app={p.name} defaultChecked={isAllowed || isBlocked} />
                                                <span className="text-sm text-gray-300 flex-grow">{p.name}</span>
                                                <span className="text-[10px] text-gray-500">PID: {p.pid}</span>
                                                <select data-action={p.name} className="glass-input text-xs px-2 py-1 rounded w-24" defaultValue={isAllowed ? 'allow' : isBlocked ? 'block' : 'ignore'}>
                                                    <option value="ignore">Ignore</option>
                                                    <option value="allow">✅ Allow</option>
                                                    <option value="block">🚫 Block</option>
                                                </select>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Sync Activity Log */}
                    <div className="md:col-span-2 text-blue-400 font-bold uppercase tracking-widest text-xs border-b border-white/10 pb-1 mt-4">Sync Activity Log</div>
                    <div className="md:col-span-2 bg-[#0c0c0f] border border-white/10 rounded-lg p-3 h-48 overflow-y-auto font-mono text-[10px] leading-relaxed custom-scrollbar shadow-inner relative">
                        <div className="absolute top-2 right-2 text-gray-600 opacity-50"><i className="fas fa-circle text-[6px]"></i></div>
                        {syncLogs.length === 0 ? (
                            <div className="text-gray-500 italic text-center py-4">No sync activity yet.</div>
                        ) : (
                            syncLogs.map((log, i) => (
                                <div key={i} className="border-b border-white/5 py-1 text-gray-300">
                                    {log}
                                </div>
                            ))
                        )}
                    </div>

                    {/* Git Sync Status */}
                    <div className="md:col-span-2 text-blue-400 font-bold uppercase tracking-widest text-xs border-b border-white/10 pb-1 mt-4">Git Sync Status</div>
                    <div className="md:col-span-2 flex flex-col gap-3">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-4">
                                <div className={`w-3 h-3 rounded-full ${settings.git_status === 'connected' ? 'bg-green-500 animate-pulse' : 
                                                      settings.git_status === 'error' ? 'bg-red-500' : 
                                                      settings.git_status === 'syncing' ? 'bg-yellow-500 animate-pulse' : 
                                                      'bg-gray-500'}`}>
                                </div>
                                <span className="text-sm font-medium text-gray-300">
                                    {settings.git_status === 'connected' ? '✅ Connected to GitHub' :
                                     settings.git_status === 'syncing' ? '🔄 Syncing...' :
                                     settings.git_status === 'error' ? '❌ Sync Error' :
                                     '⏸️ Not Connected'}
                                </span>
                            </div>
                            <div className="text-[10px] font-bold text-gray-500 uppercase tracking-widest bg-black/40 px-3 py-1 rounded border border-white/10">
                                <i className="fas fa-clock mr-1"></i> Next Auto-Sync: 
                                <span className="text-blue-400 ml-1">
                                    {settings.sync_enabled && settings.sync_interval ? `~${Math.round(settings.sync_interval / 60)} min` : 'Disabled'}
                                </span>
                            </div>
                        </div>
                        {settings.git_status === 'syncing' && (
                            <div className="w-full bg-black/40 h-2 rounded-full overflow-hidden border border-white/10 my-2">
                                <div className="bg-blue-500 h-full transition-all duration-300 ease-out" style={{ width: `${settings.sync_progress_pct || 100}%` }}></div>
                            </div>
                        )}
                        <div className="flex gap-3">
                            <button onClick={() => {
                                setSettings(prev => ({...prev, git_status: 'syncing', sync_msg: 'Verifying connection...', sync_progress_pct: 10}));
                                backend.request(JSON.stringify({action: 'get_sync_status'})).then(res => {
                                    const data = JSON.parse(res);
                                    setSettings(prev => ({
                                        ...prev, 
                                        git_status: data.enabled ? 'connected' : 'error',
                                        git_last_sync: new Date().toLocaleString(),
                                        sync_msg: data.enabled ? 'Connection verified' : 'Check configuration',
                                        sync_progress_pct: 100
                                    }));
                                }).catch(() => {
                                    setSettings(prev => ({...prev, git_status: 'error', sync_msg: 'Backend connection failed', sync_progress_pct: 0}));
                                });
                            }} className="glass-button px-4 py-2 rounded text-xs font-bold tracking-widest text-white uppercase bg-blue-600/30 border-blue-500/50 hover:bg-blue-600">
                                <i className="fas fa-satellite-dish mr-2"></i> Verify Connection
                            </button>
                            <button onClick={() => {
                                setSettings(prev => ({...prev, git_status: 'syncing', sync_msg: 'Initiating sync process...', sync_progress_pct: 5}));
                                backend.request(JSON.stringify({action: 'sync_now'}));
                            }} className="glass-button px-6 py-2 rounded text-xs font-bold tracking-widest text-white uppercase bg-green-600/30 border-green-500/50 hover:bg-green-600 shadow-[0_0_10px_rgba(34,197,94,0.2)]">
                                <i className="fas fa-sync-alt mr-2"></i> Force Sync Now
                            </button>
                        </div>
                        <div className="flex flex-col mt-2">
                            <label className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-1 flex justify-between">
                                <span>Terminal Output</span>
                                <span><i className="fas fa-terminal mr-1"></i> System Bridge</span>
                            </label>
                            <div className="bg-[#0c0c0f] border border-white/10 rounded-lg p-3 h-32 overflow-y-auto font-mono text-[10px] leading-relaxed custom-scrollbar shadow-inner relative">
                                <div className="absolute top-2 right-2 text-gray-600 opacity-50"><i className="fas fa-circle text-[6px]"></i></div>
                                <div className="text-gray-500 mb-1">$ systemctl status sync_manager</div>
                                <div className="text-gray-300">
                                    <span className="text-blue-400">Device ID:</span> {settings.device_id || 'Not set'}
                                </div>
                                <div className="text-gray-300">
                                    <span className="text-blue-400">Target Repo:</span> {settings.sync_repo_url ? settings.sync_repo_url.split('/').slice(-2).join('/') : 'Not configured'}
                                </div>
                                <div className="text-gray-300 mb-2">
                                    <span className="text-blue-400">Last Sync:</span> {settings.git_last_sync || 'Never'}
                                </div>
                                {settings.sync_msg && (
                                    <div className={`mt-2 p-2 border-l-2 rounded-r-md
                                        ${settings.git_status === 'error' ? 'bg-red-900/20 border-red-500 text-red-400' : 
                                          settings.git_status === 'syncing' ? 'bg-yellow-900/20 border-yellow-500 text-yellow-400' : 
                                          'bg-green-900/20 border-green-500 text-green-400'}`}>
                                        {settings.git_status === 'syncing' && <i className="fas fa-spinner fa-spin mr-2"></i>}
                                        {settings.git_status === 'error' && <i className="fas fa-times-circle mr-2"></i>}
                                        {settings.git_status === 'connected' && <i className="fas fa-check-circle mr-2"></i>}
                                        {settings.sync_msg}
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>

{/* Danger Zone */}
<div className="md:col-span-2 text-red-500 font-bold uppercase tracking-widest text-xs border-b border-red-500/30 pb-1 mt-6">Danger Zone</div>
<div className="md:col-span-2 grid grid-cols-1 md:grid-cols-3 gap-4 p-4 bg-red-900/10 border border-red-500/20 rounded-lg">
    
    {/* 1. Master Overwrite */}
    <div className="flex flex-col gap-3">
        <div className="flex flex-col">
            <span className="text-xs font-bold text-red-400">1. Master Overwrite (Force Push)</span>
            <span className="text-[10px] text-gray-400 leading-relaxed mt-1">Make THIS device the absolute Master. Forces this data to the cloud and deletes conflicting nodes.</span>
        </div>
        <button onClick={() => {
            if(confirm("WARNING: This will make this device the absolute master and wipe conflicting remote data. Continue?")) {
                setSettings(prev => ({...prev, git_status: 'syncing', sync_msg: 'Initiating MASTER OVERWRITE...', sync_progress_pct: 10}));
                backend.request(JSON.stringify({action: 'force_sync_now'}));
            }
        }} className="glass-button px-4 py-3 mt-auto rounded text-xs font-bold tracking-widest text-white uppercase bg-red-600/50 border-red-500/50 hover:bg-red-600 shadow-[0_0_15px_rgba(239,68,68,0.3)] w-full transition-all">
            <i className="fas fa-upload mr-2"></i> Force Push as Master
        </button>
    </div>

    {/* 2. Hard Clone */}
    <div className="flex flex-col gap-3">
        <div className="flex flex-col">
            <span className="text-xs font-bold text-yellow-400">2. Hard Clone (Force Pull)</span>
            <span className="text-[10px] text-gray-400 leading-relaxed mt-1">Wipe THIS device's database completely and clone an exact 1:1 copy of the Master Node.</span>
        </div>
        <button onClick={() => {
            if(confirm("DANGER: This will completely WIPE this PC's local database and download the master copy from Git. Proceed?")) {
                setSettings(prev => ({...prev, git_status: 'syncing', sync_msg: 'Initiating HARD CLONE...', sync_progress_pct: 10}));
                backend.request(JSON.stringify({action: 'hard_clone_remote'}));
            }
        }} className="glass-button px-4 py-3 mt-auto rounded text-xs font-bold tracking-widest text-white uppercase bg-yellow-600/50 border-yellow-500/50 hover:bg-yellow-600 shadow-[0_0_15px_rgba(234,179,8,0.3)] w-full transition-all">
            <i className="fas fa-download mr-2"></i> Wipe & Clone Master
        </button>
    </div>

    {/* 3. Force Reset All Data (NEW) */}
    <div className="flex flex-col gap-3">
        <div className="flex flex-col">
            <span className="text-xs font-bold text-red-600">3. Force Reset All Data</span>
            <span className="text-[10px] text-gray-400 leading-relaxed mt-1">Completely wipe ALL local data: database, config, and Git sync repo. Sync settings (repo URL, token) are preserved. App will reload.</span>
        </div>
        <button onClick={() => {
    if(confirm("⚠️ DANGER: This will permanently delete ALL local data, including your database, configuration, and Git sync repo. This action cannot be undone. Continue?")) {
        setSettings(prev => ({...prev, git_status: 'syncing', sync_msg: 'Resetting all data...', sync_progress_pct: 10}));
        backend.request(JSON.stringify({action: 'force_reset_all_data'})).then(res => {
            const data = JSON.parse(res);
            if (data.status === 'success') {
                // Build the correct file URL
                let url = window.location.href;
                // If it's a directory (ends with '/'), append index.html
                if (url.endsWith('/')) {
                    url += 'index.html';
                } else if (url.endsWith('Modular') || url.endsWith('shadow_os_cache')) {
                    // If it ends with the folder name, add '/index.html'
                    url += '/index.html';
                } else if (!url.includes('index.html') && !url.match(/\.html?$/)) {
                    // If no .html extension, add index.html
                    url = url + (url.endsWith('/') ? '' : '/') + 'index.html';
                }
                window.location.replace(url);
            } else {
                alert('Reset failed: ' + data.message);
            }
        });
    }
}} className="glass-button px-4 py-3 mt-auto rounded text-xs font-bold tracking-widest text-white uppercase bg-red-700/50 border-red-600/50 hover:bg-red-700 shadow-[0_0_15px_rgba(239,68,68,0.3)] w-full transition-all">
            <i className="fas fa-trash-alt mr-2"></i> Wipe All Data
        </button>
    </div>

</div>

                    {/* System Activity Ledger */}
                    <div className="md:col-span-2 text-blue-400 font-bold uppercase tracking-widest text-xs border-b border-white/10 pb-1 mt-4">System Activity Ledger</div>
                    <div className="md:col-span-2 bg-[#0c0c0f] border border-white/10 rounded-lg p-3 h-48 overflow-y-auto font-mono text-[10px] leading-relaxed custom-scrollbar shadow-inner relative">
                        <table className="w-full text-left">
                            <thead className="sticky top-0 bg-[#0c0c0f] text-gray-500 pb-2">
                                <tr><th className="w-1/4 pb-2">Timestamp</th><th className="w-1/4 pb-2">Module</th><th className="w-1/2 pb-2">Action</th></tr>
                            </thead>
                            <tbody>
                                {activityLogs && activityLogs.length > 0 ? activityLogs.map((log, i) => (
                                    <tr key={i} className="border-b border-white/5 hover:bg-white/5 transition-colors text-gray-300">
                                        <td className="py-1">{new Date(log.timestamp).toLocaleString()}</td>
                                        <td className="py-1 text-blue-400">[{log.module}]</td>
                                        <td className="py-1">{log.description}</td>
                                    </tr>
                                )) : <tr><td colSpan="3" className="text-gray-500 italic py-2 text-center">No activity logged yet.</td></tr>}
                            </tbody>
                        </table>
                    </div>

                    {/* File & Device Sync Config */}
                    <div className="md:col-span-2 text-blue-400 font-bold uppercase tracking-widest text-xs border-b border-white/10 pb-1 mt-4">File & Device Sync Configuration</div>
                    <div className="md:col-span-2 flex flex-col gap-3">
                        <div className="flex items-center gap-4">
                            <label className="text-xs font-bold text-gray-400 uppercase tracking-widest">Device ID</label>
                            <span className="text-xs font-mono text-blue-400 bg-black/40 px-3 py-1 rounded border border-white/10">{settings.device_id || 'Loading...'}</span>
                        </div>
                        <div className="flex items-center gap-4">
                            <label className="text-xs font-bold text-gray-400 uppercase tracking-widest">Enable Auto-Sync</label>
                            <input type="checkbox" checked={settings.sync_enabled || false} 
                                   onChange={e => handleChange('sync_enabled', e.target.checked)} 
                                   className="w-5 h-5 rounded bg-black/40 border border-white/20 accent-blue-500" />
                        </div>
                        <div className="flex flex-col gap-1">
                            <label className="text-xs font-bold text-gray-400 uppercase tracking-widest">GitHub Repository URL</label>
                            <input type="text" value={settings.sync_repo_url || ''} 
                                   onChange={e => handleChange('sync_repo_url', e.target.value)} 
                                   className="glass-input p-2.5 rounded text-sm w-full" 
                                   placeholder="https://github.com/username/repo.git" />
                        </div>
                        <div className="flex flex-col gap-1">
                            <label className="text-xs font-bold text-gray-400 uppercase tracking-widest">GitHub Token Status</label>
                            <div className="flex items-center gap-3 p-2 bg-black/40 rounded border border-white/10">
                                {settings.has_token ? (
                                    <span className="text-green-400"><i className="fas fa-check-circle mr-2"></i> ✅ PAT secured in OS Environment variables</span>
                                ) : (
                                    <span className="text-yellow-400"><i className="fas fa-exclamation-triangle mr-2"></i> ⚠️ Token not set. Add GITHUB_TOKEN to .env file</span>
                                )}
                            </div>
                        </div>
                        <div className="flex flex-col gap-1">
                            <label className="text-xs font-bold text-gray-400 uppercase tracking-widest">Auto-Sync Interval (seconds)</label>
                            <input type="number" value={settings.sync_interval || 3600} 
                                   onChange={e => handleChange('sync_interval', parseInt(e.target.value))} 
                                   className="glass-input p-2.5 rounded text-sm w-32" />
                        </div>
                    </div>

                    {/* Mapped Folders */}
                    <div className="md:col-span-2 flex flex-col gap-2 mt-2">
                        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest">Mapped Folders (Cross-Device P2P Share)</label>
                        <div className="flex gap-2">
                            <input type="text" id="folder-input" placeholder="C:/Users/... or /Users/..." className="glass-input p-2.5 rounded text-sm flex-grow" />
                            <button onClick={() => {
                                const input = document.getElementById('folder-input');
                                if (input.value) {
                                    backend.request(JSON.stringify({action: 'map_folder', path: input.value})).then(() => {
                                        input.value = '';
                                        backend.request(JSON.stringify({action: 'get_mapped_folders'})).then(res => {
                                            const data = JSON.parse(res);
                                            setSettings(prev => ({...prev, mapped_folders: data.folders}));
                                            setNetworkFolders(data.network_folders);
                                        });
                                    });
                                }
                            }} className="glass-button px-4 py-2 rounded text-xs font-bold text-green-300 uppercase border border-green-500/30 hover:bg-green-900/30"><i className="fas fa-plus mr-1"></i> Map Folder</button>
                            <button onClick={() => {
                                backend.request(JSON.stringify({action: 'open_folder_dialog'})).then(res => {
                                    const data = JSON.parse(res);
                                    if (data.path) { document.getElementById('folder-input').value = data.path; }
                                });
                            }} className="glass-button px-4 py-2 rounded text-xs font-bold text-blue-300 uppercase border border-blue-500/30 hover:bg-blue-900/30"><i className="fas fa-folder-open mr-1"></i> Browse OS</button>
                        </div>
                        <div className="flex flex-wrap gap-2 mt-2 max-h-40 overflow-y-auto p-3 bg-[#0c0c0f] rounded-lg border border-white/5 shadow-inner">
                            {settings.mapped_folders && settings.mapped_folders.length > 0 ? (
                                settings.mapped_folders.map((path, i) => (
                                    <span key={i} className="flex items-center gap-2 bg-white/10 px-3 py-1.5 rounded-full text-xs border border-white/10 group hover:bg-white/20 transition-all cursor-default">
                                        <i className="fas fa-folder text-yellow-400 text-xs shadow-sm"></i>
                                        <span className="font-mono text-gray-300 truncate max-w-xs" title={path}>{path}</span>
                                        <button onClick={() => {
                                            backend.request(JSON.stringify({action: 'unmap_folder', path: path})).then(() => {
                                                backend.request(JSON.stringify({action: 'get_mapped_folders'})).then(res => {
                                                    const data = JSON.parse(res);
                                                    setSettings(prev => ({...prev, mapped_folders: data.folders}));
                                                    setNetworkFolders(data.network_folders);
                                                });
                                            });
                                        }} className="text-red-400 hover:text-red-300 opacity-0 group-hover:opacity-100 transition-all ml-1"><i className="fas fa-times-circle"></i></button>
                                    </span>
                                ))
                            ) : (
                                <span className="text-xs text-gray-500 italic">No folders mapped. Data will be automatically packaged and pushed to the Git network.</span>
                            )}
                        </div>
                    </div>

                    {/* Cluster Topology & Sync */}
                    <div className="md:col-span-2 text-blue-400 font-bold uppercase tracking-widest text-xs border-b border-white/10 pb-1 mt-4">Cluster Topology & Sync</div>
                    <div className="md:col-span-2 flex flex-col gap-4 bg-[#0c0c0f] p-4 rounded-lg border border-white/10">
                        <div className="flex justify-between items-center">
                            <div className="flex items-center gap-3">
                                <div className={`w-3 h-3 rounded-full ${settings.git_status === 'connected' ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`}></div>
                                <span className="text-xs font-bold text-white uppercase tracking-widest">
                                    {settings.git_status === 'connected' ? 'Connected to Git Cluster' : 'Sync Disconnected'}
                                </span>
                            </div>
                            <div className="text-[10px] font-mono text-blue-400 bg-blue-950/40 px-3 py-1 rounded border border-blue-500/30">
                                Current Node: <span className="font-bold text-white">{settings.device_id ? settings.device_id.substring(0, 12) : 'Loading...'}</span>
                            </div>
                        </div>
                        <div className="flex flex-col gap-2 p-3 bg-black/40 rounded border border-white/5">
                            <div className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Cluster Master Authority</div>
                            <div className="flex justify-between items-center">
                                <div className="text-xs text-gray-300 font-mono">
                                    Master ID: <span className="text-yellow-400 font-bold">{settings.master_id ? settings.master_id.substring(0, 16) + '...' : 'None Assigned (Decentralized)'}</span>
                                </div>
                                <button onClick={() => {
                                    if(confirm("Promote this PC as the absolute Cluster Master? All other nodes will pull from this state.")) {
                                        setSettings(prev => ({...prev, git_status: 'syncing', sync_msg: 'Promoting to Master...', sync_progress_pct: 20}));
                                        backend.request(JSON.stringify({action: 'force_sync_now'}));
                                    }
                                }} className="glass-button px-4 py-1.5 rounded text-[10px] font-bold tracking-widest text-white uppercase bg-blue-600/40 border-blue-500/50 hover:bg-blue-600">
                                    <i className="fas fa-crown mr-1 text-yellow-400"></i> Promote This PC to Master
                                </button>
                            </div>
                        </div>
                        <div className="flex gap-3">
                            <button onClick={() => {
                                setSettings(prev => ({...prev, git_status: 'syncing', sync_msg: 'Syncing with cluster...'}));
                                backend.request(JSON.stringify({action: 'sync_now'}));
                            }} className="glass-button px-5 py-2 rounded text-xs font-bold tracking-widest text-white uppercase bg-green-600/30 border-green-500/50 hover:bg-green-600">
                                <i className="fas fa-sync-alt mr-2"></i> Standard Sync Now
                            </button>
                            <span className="text-[10px] text-gray-500 self-center">Merges changes or pulls from Master depending on your node role.</span>
                        </div>
                    </div>

                    {/* K-Peer Node Selectors */}
                    <div className="md:col-span-2 text-yellow-400 font-bold uppercase tracking-widest text-xs border-b border-yellow-500/30 pb-1 mt-4">Discovered Database Peer Nodes (K-Cluster)</div>
                    <div className="md:col-span-2 grid grid-cols-1 sm:grid-cols-2 gap-3">
                        {networkFolders && networkFolders.length > 0 ? networkFolders.map((f, i) => (
                            <div key={i} className="flex flex-col p-3 bg-[#0c0c0f] border border-white/10 rounded-lg shadow-md relative overflow-hidden">
                                <div className={`absolute top-0 left-0 w-1 h-full ${f.is_local ? 'bg-blue-500' : 'bg-purple-500'}`}></div>
                                <div className="flex justify-between items-center mb-2 pl-2">
                                    <span className="text-xs font-bold text-white uppercase tracking-widest font-mono">
                                        Node {f.device_id.substring(0, 8)} {f.is_local ? '(This PC)' : ''}
                                    </span>
                                    <span className="text-[9px] text-gray-400 font-mono">{f.last_update}</span>
                                </div>
                                <div className="pl-2 mt-2">
                                    {f.is_local ? (
                                        <span className="text-[10px] text-blue-400 italic">Local Database Node</span>
                                    ) : (
                                        <button onClick={() => {
                                            if(confirm(`DANGER: Completely wipe this PC's database and hard-clone all settings, goals, and pomodoro data from Node ${f.device_id.substring(0,8)}?`)) {
                                                setSettings(prev => ({...prev, git_status: 'syncing', sync_msg: `Cloning Node ${f.device_id.substring(0,8)}...`, sync_progress_pct: 10}));
                                                backend.request(JSON.stringify({action: 'hard_clone_remote', target_device: f.device_id}));
                                            }
                                        }} className="w-full py-2 bg-yellow-600/30 hover:bg-yellow-600 border border-yellow-500/50 rounded text-[10px] font-bold uppercase tracking-widest text-yellow-300 hover:text-white transition-all shadow">
                                            <i className="fas fa-file-download mr-1"></i> Hard Clone DB From This Node
                                        </button>
                                    )}
                                </div>
                            </div>
                        )) : (
                            <div className="text-xs text-gray-500 italic p-3 bg-[#0c0c0f] rounded-lg border border-white/5 col-span-2 text-center">
                                No peer nodes found in Git repository yet. Run "Standard Sync Now" to discover nodes.
                            </div>
                        )}
                    </div>

                    {/* Network Shared Folders */}
                    <div className="md:col-span-2 flex flex-col gap-2 mt-4">
                        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest">Network Drives & Discovered Nodes</label>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-1">
                            {networkFolders && networkFolders.length > 0 ? networkFolders.map((f, i) => (
                                <div key={i} className="flex flex-col p-4 bg-[#0c0c0f] border border-white/10 rounded-lg hover:border-white/20 transition-colors shadow-lg relative overflow-hidden group">
                                    <div className={`absolute top-0 left-0 w-1 h-full ${f.is_local ? 'bg-blue-500 shadow-[0_0_10px_#3b82f6]' : 'bg-green-500 shadow-[0_0_10px_#22c55e]'}`}></div>
                                    <div className="flex justify-between items-center mb-3 pl-2">
                                        <div className="flex items-center gap-2">
                                            <i className={`fas ${f.is_local ? 'fa-laptop text-blue-400' : 'fa-server text-green-400'} text-sm`}></i>
                                            <span className="text-xs font-bold text-white uppercase tracking-widest">Node {f.device_id.substring(0, 8)}</span>
                                            {f.is_local && <span className="text-[9px] bg-blue-900/50 text-blue-300 px-1.5 py-0.5 rounded ml-1">THIS PC</span>}
                                        </div>
                                        <button onClick={() => backend.request(JSON.stringify({action: 'open_network_folder', path: f.path}))} className="px-3 py-1.5 bg-white/10 hover:bg-white/20 rounded-md text-[10px] font-bold uppercase tracking-widest text-white transition-colors border border-white/10 group-hover:border-white/30">
                                            <i className="fas fa-folder-open mr-1"></i> Browse Files
                                        </button>
                                    </div>
                                    <div className="flex justify-between text-[11px] text-gray-400 font-mono bg-black/40 p-2 rounded border border-white/5 pl-2 ml-2">
                                        <span><i className="fas fa-file-archive text-gray-500 mr-2"></i> {f.file_count} files</span>
                                        <span className={f.is_local ? 'text-blue-400/70' : 'text-green-400/70'}><i className="fas fa-clock mr-1"></i> {f.last_update}</span>
                                    </div>
                                </div>
                            )) : (
                                <div className="text-xs text-gray-500 italic p-4 bg-[#0c0c0f] rounded-lg border border-white/5 shadow-inner col-span-2 text-center">
                                    <i className="fas fa-network-wired text-xl mb-2 block opacity-50"></i>
                                    No network folders discovered on the Git cluster yet. 
                                    <br/>Click "Sync Now" to fetch shared files from your other computers.
                                </div>
                            )}
                        </div>
                    </div>

                    {/* UI & Visual Settings */}
                    <div className="md:col-span-2 text-blue-400 font-bold uppercase tracking-widest text-xs border-b border-white/10 pb-1 mt-4">UI & Typography</div>
                    <div className="flex flex-col gap-1">
                        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">System Font Family</label>
                        <input type="text" value={settings.font_family || 'Inter'} onChange={e => handleChange('font_family', e.target.value)} className="glass-input p-2.5 rounded text-sm" />
                    </div>
                    <div className="flex flex-col gap-1">
                        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Custom Font Path</label>
                        <div className="flex gap-2">
                            <input type="text" value={settings.custom_font_path || ''} readOnly className="glass-input p-2.5 rounded text-sm flex-grow opacity-50" />
                            <button onClick={() => openFileDialog('custom_font_path')} className="glass-button px-4 rounded text-xs"><i className="fas fa-folder-open"></i></button>
                        </div>
                    </div>
                    <div className="flex flex-col gap-1 md:col-span-2">
                        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Wallpaper / Background Image</label>
                        <div className="flex gap-2">
                            <input type="text" value={settings.bg_image_path || ''} readOnly className="glass-input p-2.5 rounded text-sm flex-grow opacity-50" placeholder="Select an image file..." />
                            <button onClick={() => openFileDialog('bg_image_path')} className="glass-button px-4 rounded text-xs text-blue-300 hover:text-blue-200"><i className="fas fa-image mr-1"></i> Browse</button>
                            <button onClick={() => handleChange('bg_image_path', '')} className="glass-button px-4 rounded text-xs text-red-400 hover:text-red-300" title="Clear Wallpaper"><i className="fas fa-times mr-1"></i> Clear</button>
                        </div>
                    </div>
                    <div className="flex flex-col gap-1">
                        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Global Font Size</label>
                        <input type="number" value={settings.font_size || 16} onChange={e => handleChange('font_size', parseInt(e.target.value))} className="glass-input p-2.5 rounded text-sm" />
                    </div>
                    <div className="flex flex-col gap-1">
                        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Global Font Color</label>
                        <input type="color" value={settings.font_color || '#e2e8f0'} onChange={e => handleChange('font_color', e.target.value)} className="w-full h-10 rounded cursor-pointer border-0 p-0" />
                    </div>
                    <div className="flex flex-col gap-1 md:col-span-2">
                        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Panel Opacity</label>
                        <input type="range" min="50" max="255" value={settings.panel_opacity || 180} onChange={e => handleChange('panel_opacity', parseInt(e.target.value))} className="w-full accent-blue-500 mt-2" />
                    </div>

                    {/* Horology Settings */}
                    <div className="md:col-span-2 text-blue-400 font-bold uppercase tracking-widest text-xs border-b border-white/10 pb-1 mt-4">Horology & Clock Styles</div>
                    <div className="flex flex-col gap-1">
                        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Clock Style</label>
                        <select className="glass-input p-2.5 rounded text-sm" value={settings.clock_style || 'Analog Classic'} onChange={e => handleChange('clock_style', e.target.value)}><option>Analog Classic</option><option>Analog Minimal</option><option>Digital LED</option></select>
                    </div>
                    <div className="flex flex-col gap-1">
                        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Case Shape</label>
                        <select className="glass-input p-2.5 rounded text-sm" value={settings.clock_case_shape || 'Round'} onChange={e => handleChange('clock_case_shape', e.target.value)}><option>Round</option><option>Square</option><option>Cushion</option><option>Tonneau</option></select>
                    </div>
                    <div className="flex flex-col gap-1">
                        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Bezel</label>
                        <select className="glass-input p-2.5 rounded text-sm" value={settings.clock_bezel || 'Plain'} onChange={e => handleChange('clock_bezel', e.target.value)}><option>Plain</option><option>Fluted</option><option>Diver</option><option>GMT (Pepsi)</option><option>Coin-Edge</option></select>
                    </div>
                    <div className="flex flex-col gap-1">
                        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Hands Style</label>
                        <select className="glass-input p-2.5 rounded text-sm" value={settings.clock_hands || 'Classic'} onChange={e => handleChange('clock_hands', e.target.value)}><option>Classic</option><option>Spade</option><option>Breguet</option><option>Dauphine</option><option>Serpentine</option><option>Mercedes</option><option>Sword</option><option>Arrow</option></select>
                    </div>
                    <div className="flex flex-col gap-1">
                        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Clock Indices</label>
                        <select className="glass-input p-2.5 rounded text-sm" value={settings.clock_indices || 'Baton'} onChange={e => handleChange('clock_indices', e.target.value)}><option>None</option><option>Arabic</option><option>Roman</option><option>Baton</option><option>Dot</option><option>California</option></select>
                    </div>
                    <div className="flex flex-col gap-1">
                        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Clock Ticks</label>
                        <select className="glass-input p-2.5 rounded text-sm" value={settings.clock_ticks || 'Standard'} onChange={e => handleChange('clock_ticks', e.target.value)}><option>Standard</option><option>Clean</option><option>Railroad</option><option>Crosshair</option></select>
                    </div>
                    <div className="flex flex-col gap-1 md:col-span-2">
                        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Clock Complication</label>
                        <select className="glass-input p-2.5 rounded text-sm" value={settings.clock_complication || 'None'} onChange={e => handleChange('clock_complication', e.target.value)}><option>None</option><option>Date Window</option><option>Small Seconds</option></select>
                    </div>

                    {/* System Behavior & Vision Settings */}
                    <div className="md:col-span-2 text-blue-400 font-bold uppercase tracking-widest text-xs border-b border-white/10 pb-1 mt-4">System Data & Behavior</div>
                    <div className="flex items-center gap-4 md:col-span-2">
                        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest">Quiet Mode</label>
                        <input type="checkbox" checked={settings.quiet_mode || false} 
                               onChange={e => {
                                   const checked = e.target.checked;
                                   handleChange('quiet_mode', checked);
                                   backend.request(JSON.stringify({action: 'set_quiet_mode', enabled: checked}));
                               }} 
                               className="w-5 h-5 rounded bg-black/40 border border-white/20 accent-blue-500" />
                        <span className="text-xs text-gray-400">
                            {settings.quiet_mode ? '🔇 Disables webcam, sounds, and speech' : '🔊 Full mode with webcam & sounds'}
                        </span>
                    </div>
                    <div className="flex flex-col gap-1">
                        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Quotes JSON Path</label>
                        <div className="flex gap-2">
                            <input type="text" value={settings.quotes_path || ''} onChange={e => handleChange('quotes_path', e.target.value)} className="glass-input p-2.5 rounded text-sm flex-grow" />
                            <button onClick={() => openFileDialog('quotes_path')} className="glass-button px-4 rounded text-xs"><i className="fas fa-folder-open"></i></button>
                        </div>
                    </div>
                    <div className="flex flex-col gap-1">
                        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Force Close Apps After (min)</label>
                        <input type="number" value={settings.force_close_apps_mins || 5} onChange={e => handleChange('force_close_apps_mins', parseInt(e.target.value))} className="glass-input p-2.5 rounded text-sm" />
                    </div>

                    <div className="md:col-span-2 text-blue-400 font-bold uppercase tracking-widest text-xs border-b border-white/10 pb-1 mt-4">Audio & Speech Alerts</div>
                    <div className="flex gap-6 md:col-span-2">
                        <div className="flex items-center gap-2">
                            <label className="text-xs font-bold text-gray-400 uppercase tracking-widest">Mute Sounds</label>
                            <input type="checkbox" checked={settings.mute_sounds || false} onChange={e => handleChange('mute_sounds', e.target.checked)} className="w-5 h-5 rounded bg-black/40 border border-white/20 accent-blue-500" />
                        </div>
                        <div className="flex items-center gap-2">
                            <label className="text-xs font-bold text-gray-400 uppercase tracking-widest">Mute Speech</label>
                            <input type="checkbox" checked={settings.mute_speech || false} onChange={e => handleChange('mute_speech', e.target.checked)} className="w-5 h-5 rounded bg-black/40 border border-white/20 accent-blue-500" />
                        </div>
                    </div>
                    <div className="flex flex-col gap-1">
                        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">App Distraction Sound</label>
                        <select className="glass-input p-2.5 rounded text-sm" value={settings.sound_app_dist || 'Ping'} onChange={e => handleChange('sound_app_dist', e.target.value)}>
                            {["Basso", "Blow", "Bottle", "Frog", "Funk", "Glass", "Hero", "Morse", "Ping", "Pop", "Purr", "Sosumi", "Submarine", "Tink"].map(s => <option key={s} value={s}>{s}</option>)}
                        </select>
                    </div>
                    <div className="flex flex-col gap-1">
                        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Camera Distraction Sound</label>
                        <select className="glass-input p-2.5 rounded text-sm" value={settings.sound_cam_dist || 'Basso'} onChange={e => handleChange('sound_cam_dist', e.target.value)}>
                            {["Basso", "Blow", "Bottle", "Frog", "Funk", "Glass", "Hero", "Morse", "Ping", "Pop", "Purr", "Sosumi", "Submarine", "Tink"].map(s => <option key={s} value={s}>{s}</option>)}
                        </select>
                    </div>
                    <div className="flex flex-col gap-1">
                        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Camera Error Sound</label>
                        <select className="glass-input p-2.5 rounded text-sm" value={settings.sound_cam_err || 'Hero'} onChange={e => handleChange('sound_cam_err', e.target.value)}>
                            {["Basso", "Blow", "Bottle", "Frog", "Funk", "Glass", "Hero", "Morse", "Ping", "Pop", "Purr", "Sosumi", "Submarine", "Tink"].map(s => <option key={s} value={s}>{s}</option>)}
                        </select>
                    </div>
                    <div className="flex flex-col gap-1">
                        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Beep Frequency (seconds)</label>
                        <input type="number" value={settings.beep_freq || 3} onChange={e => handleChange('beep_freq', parseInt(e.target.value))} className="glass-input p-2.5 rounded text-sm" />
                    </div>

                    <div className="flex flex-col gap-1">
                        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Loop Beeps at 1m</label>
                        <input type="number" value={settings.loop_1m || 2} onChange={e => handleChange('loop_1m', parseInt(e.target.value))} className="glass-input p-2.5 rounded text-sm" />
                    </div>
                    <div className="flex flex-col gap-1">
                        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Loop Beeps at 5m</label>
                        <input type="number" value={settings.loop_5m || 5} onChange={e => handleChange('loop_5m', parseInt(e.target.value))} className="glass-input p-2.5 rounded text-sm" />
                    </div>
                    <div className="flex flex-col gap-1">
                        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Loop Beeps at 15m</label>
                        <input type="number" value={settings.loop_15m || 10} onChange={e => handleChange('loop_15m', parseInt(e.target.value))} className="glass-input p-2.5 rounded text-sm" />
                    </div>
                    <div className="flex flex-col gap-1">
                        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Loop Beeps at 30m</label>
                        <input type="number" value={settings.loop_30m || 20} onChange={e => handleChange('loop_30m', parseInt(e.target.value))} className="glass-input p-2.5 rounded text-sm" />
                    </div>
                    <div className="flex flex-col gap-1">
                        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Loop Beeps at 60m</label>
                        <input type="number" value={settings.loop_60m || 30} onChange={e => handleChange('loop_60m', parseInt(e.target.value))} className="glass-input p-2.5 rounded text-sm" />
                    </div>

                    <div className="flex flex-col gap-1 md:col-span-2">
                        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Distraction Spoken Phrase</label>
                        <input type="text" value={settings.speech_dist || ''} onChange={e => handleChange('speech_dist', e.target.value)} className="glass-input p-2.5 rounded text-sm" />
                    </div>
                    <div className="flex flex-col gap-1 md:col-span-2">
                        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Completion Spoken Phrase</label>
                        <input type="text" value={settings.speech_comp || ''} onChange={e => handleChange('speech_comp', e.target.value)} className="glass-input p-2.5 rounded text-sm" />
                    </div>

                    <div className="md:col-span-2 text-blue-400 font-bold uppercase tracking-widest text-xs border-b border-white/10 pb-1 mt-4">Vision Tracker Settings</div>
                    <div className="flex flex-col gap-1">
                        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Vision Mode</label>
                        <select className="glass-input p-2.5 rounded text-sm" value={settings.vision_mode || 'Strict (Face & Eyes)'} onChange={e => handleChange('vision_mode', e.target.value)}><option>Strict (Face & Eyes)</option><option>Visible (Face Only)</option></select>
                    </div>
                    <div className="flex flex-col gap-1">
                        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Vision Sample Interval (ms)</label>
                        <input type="number" value={settings.vision_sample_interval || 30} onChange={e => handleChange('vision_sample_interval', parseInt(e.target.value))} className="glass-input p-2.5 rounded text-sm" />
                    </div>
                    <div className="flex flex-col gap-1">
                        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Vision Distraction Delay (s)</label>
                        <input type="number" value={settings.dist_delay || 3} onChange={e => handleChange('dist_delay', parseInt(e.target.value))} className="glass-input p-2.5 rounded text-sm" />
                    </div>
                    <div className="flex flex-col gap-1">
                        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Face Scale Factor</label>
                        <input type="number" step="0.05" value={settings.face_scale_factor || 1.2} onChange={e => handleChange('face_scale_factor', parseFloat(e.target.value))} className="glass-input p-2.5 rounded text-sm" />
                    </div>
                    <div className="flex flex-col gap-1">
                        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Face Min Neighbors</label>
                        <input type="number" value={settings.face_min_neighbors || 8} onChange={e => handleChange('face_min_neighbors', parseInt(e.target.value))} className="glass-input p-2.5 rounded text-sm" />
                    </div>
                    <div className="flex flex-col gap-1">
                        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Face Min Size (px)</label>
                        <input type="number" value={settings.face_min_size || 120} onChange={e => handleChange('face_min_size', parseInt(e.target.value))} className="glass-input p-2.5 rounded text-sm" />
                    </div>

                    {/* Distributed Sync Network Section */}
                    <div className="md:col-span-2 text-blue-400 font-bold uppercase tracking-widest text-xs border-b border-white/10 pb-1 mt-6">Distributed Sync Network</div>
                    <div className="flex flex-col gap-1">
                        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">GitHub Repo URL</label>
                        <input type="text" value={settings.sync_repo_url || ''} onChange={e => handleChange('sync_repo_url', e.target.value)} className="glass-input p-2.5 rounded text-sm" placeholder="https://github.com/user/repo.git" />
                    </div>
                    <div className="flex flex-col gap-1">
                        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Sync Interval (seconds)</label>
                        <input type="number" value={settings.sync_interval || 3600} onChange={e => handleChange('sync_interval', parseInt(e.target.value))} className="glass-input p-2.5 rounded text-sm" />
                    </div>
                    <div className="flex gap-6 md:col-span-2">
                        <div className="flex items-center gap-2">
                            <label className="text-xs font-bold text-gray-400 uppercase tracking-widest">Enable Sync</label>
                            <input type="checkbox" checked={settings.sync_enabled || false} onChange={e => handleChange('sync_enabled', e.target.checked)} className="w-5 h-5 rounded bg-black/40 border border-white/20 accent-blue-500" />
                        </div>
                    </div>
                    <div className="md:col-span-2">
                        <button onClick={() => {
                            backend.request(JSON.stringify({action: 'sync_now'}));
                        }} className="glass-button px-6 py-2 rounded text-xs font-bold tracking-widest text-white uppercase bg-green-600/30 border-green-500/50 hover:bg-green-600 shadow-lg w-full">
                            <i className="fas fa-sync-alt mr-2"></i> Force Sync Now
                        </button>
                    </div>

                    {/* Network Folders */}
                    <div className="md:col-span-2 text-blue-400 font-bold uppercase tracking-widest text-xs border-b border-white/10 pb-1 mt-4">Network Nodes</div>
                    <div className="md:col-span-2">
                        {networkFolders && networkFolders.length > 0 ? (
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                {networkFolders.map(f => (
                                    <div key={f.device_id} className="bg-white/5 p-3 rounded border border-white/10">
                                        <div className="flex justify-between items-center mb-2">
                                            <span className="text-xs font-bold text-white">{f.device_id.substring(0, 8)}...</span>
                                            {f.is_local && <span className="text-[10px] text-blue-400 font-bold uppercase">This Device</span>}
                                        </div>
                                        <div className="text-[10px] text-gray-400">
                                            <div>Files: {f.file_count}</div>
                                            <div>Last Update: {f.last_update}</div>
                                        </div>
                                        {!f.is_local && (
                                            <button onClick={() => {
                                                if (confirm(`Wipe local DB and clone from Node ${f.device_id.substring(0, 8)}?`)) {
                                                    backend.request(JSON.stringify({action: 'hard_clone_remote', target_device: f.device_id}));
                                                }
                                            }} className="w-full py-2 mt-2 bg-yellow-600/30 hover:bg-yellow-600 border border-yellow-500/50 rounded text-[10px] font-bold uppercase tracking-widest text-yellow-300 hover:text-white transition-all shadow">
                                                <i className="fas fa-file-download mr-1"></i> Hard Clone From This Node
                                            </button>
                                        )}
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="text-xs text-gray-500 italic p-3 bg-[#0c0c0f] rounded-lg border border-white/5 text-center">
                                No peer nodes found. Run "Force Sync Now" to discover nodes.
                            </div>
                        )}
                    </div>

                    {/* Danger Zone */}
                    <div className="md:col-span-2 text-red-500 font-bold uppercase tracking-widest text-xs border-b border-red-500/30 pb-1 mt-6">Danger Zone</div>
                    <div className="md:col-span-2 grid grid-cols-1 md:grid-cols-3 gap-4 p-4 bg-red-900/10 border border-red-500/20 rounded-lg">
                        {/* Master Overwrite */}
                        <div className="flex flex-col gap-3">
                            <div className="flex flex-col">
                                <span className="text-xs font-bold text-red-400">1. Master Overwrite</span>
                                <span className="text-[10px] text-gray-400 leading-relaxed mt-1">Make THIS device the absolute Master. Forces this data to the cloud and deletes conflicting nodes.</span>
                            </div>
                            <button onClick={() => {
                                if (confirm("WARNING: This will make this device the absolute master and wipe conflicting remote data. Continue?")) {
                                    backend.request(JSON.stringify({action: 'force_sync_now'}));
                                }
                            }} className="glass-button px-4 py-3 mt-auto rounded text-xs font-bold tracking-widest text-white uppercase bg-red-600/50 border-red-500/50 hover:bg-red-600 shadow-[0_0_15px_rgba(239,68,68,0.3)] w-full transition-all">
                                <i className="fas fa-upload mr-2"></i> Force Push as Master
                            </button>
                        </div>

                        {/* Hard Clone */}
                        <div className="flex flex-col gap-3">
                            <div className="flex flex-col">
                                <span className="text-xs font-bold text-yellow-400">2. Hard Clone</span>
                                <span className="text-[10px] text-gray-400 leading-relaxed mt-1">Wipe THIS device's database completely and clone an exact 1:1 copy of the Master Node.</span>
                            </div>
                            <button onClick={() => {
                                if (confirm("DANGER: This will completely WIPE this PC's local database and download the master copy from Git. Proceed?")) {
                                    backend.request(JSON.stringify({action: 'hard_clone_remote'}));
                                }
                            }} className="glass-button px-4 py-3 mt-auto rounded text-xs font-bold tracking-widest text-white uppercase bg-yellow-600/50 border-yellow-500/50 hover:bg-yellow-600 shadow-[0_0_15px_rgba(234,179,8,0.3)] w-full transition-all">
                                <i className="fas fa-download mr-2"></i> Wipe & Clone Master
                            </button>
                        </div>

                        {/* Force Reset All Data */}
                        <div className="flex flex-col gap-3">
                            <div className="flex flex-col">
                                <span className="text-xs font-bold text-red-600">3. Wipe All Data</span>
                                <span className="text-[10px] text-gray-400 leading-relaxed mt-1">Completely wipe ALL local data: database, config, and Git sync repo. Sync settings are preserved.</span>
                            </div>
                            <button onClick={() => {
                                if (confirm("DANGER: This will permanently delete ALL local data. Continue?")) {
                                    backend.request(JSON.stringify({action: 'force_reset_all_data'}));
                                }
                            }} className="glass-button px-4 py-3 mt-auto rounded text-xs font-bold tracking-widest text-white uppercase bg-red-700/50 border-red-600/50 hover:bg-red-700 shadow-[0_0_15px_rgba(239,68,68,0.3)] w-full transition-all">
                                <i className="fas fa-trash-alt mr-2"></i> Wipe All Data
                            </button>
                        </div>
                    </div>

                </div>
            </div>
        </div>
    );
});   // <-- this is the correct closing for React.memo

const NavBtn = React.memo(({id, icon, label, current, set, collapsed}) => (
    <button onClick={() => set(id)} 
        className={`flex items-center p-3 md:px-4 rounded-lg transition-all duration-200 group relative
            ${current === id ? 'bg-white/10 text-white border border-white/10 shadow-[inset_0_0_15px_rgba(255,255,255,0.05)]' : 'text-gray-400 hover:bg-white/5 hover:text-gray-200 border border-transparent'}
            ${collapsed ? 'justify-center' : 'justify-start'}`}>
        
        <i className={`fas ${icon} text-lg w-6 text-center transition-transform group-hover:scale-110 ${current === id ? 'text-blue-400' : ''} ${collapsed ? '' : 'mr-4'}`}></i>
        
        {!collapsed && <span className="font-bold text-[11px] tracking-widest uppercase whitespace-nowrap">{label}</span>}
        
        {collapsed && (
            <div className="absolute left-14 bg-black border border-white/10 text-white text-[10px] font-bold uppercase tracking-widest px-2 py-1 rounded opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all whitespace-nowrap z-50 shadow-xl">
                {label}
            </div>
        )}
    </button>
));  
