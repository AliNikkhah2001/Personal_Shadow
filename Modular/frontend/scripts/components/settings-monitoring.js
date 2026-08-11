const SettingsMonitoring = React.memo(({ settings, setSettings, backend, handleChange }) => {
    const [showProcessModal, setShowProcessModal] = useState(false);
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

    return <>
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
                    <option value="1.2">Sedentary (1.2)</option><option value="1.375">Light (1.375)</option>
                    <option value="1.55">Moderate (1.55)</option><option value="1.725">Intense (1.725)</option>
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
                <input type="checkbox" checked={settings.app_monitoring_enabled || false} onChange={e => {
                    const checked = e.target.checked;
                    handleChange('app_monitoring_enabled', checked);
                    backend.request(JSON.stringify({action: 'set_app_monitoring', enabled: checked}));
                }} className="w-5 h-5 rounded bg-black/40 border border-white/20 accent-blue-500" />
            </div>
            <div className="flex items-center gap-4">
                <label className="text-xs font-bold text-gray-400 uppercase tracking-widest">Auto-Block Disallowed Apps</label>
                <input type="checkbox" checked={settings.auto_block || false} onChange={e => {
                    const checked = e.target.checked;
                    handleChange('auto_block', checked);
                    backend.request(JSON.stringify({action: 'set_auto_block', enabled: checked}));
                }} className="w-5 h-5 rounded bg-black/40 border border-white/20 accent-red-500" />
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
                <button onClick={() => backend.request(JSON.stringify({action: 'check_current_distractions'}))} className="glass-button px-6 py-2 rounded text-xs font-bold tracking-widest text-white uppercase bg-blue-600/30 border-blue-500/50 hover:bg-blue-600">
                    <i className="fas fa-search mr-2"></i> Check Distractions
                </button>
            </div>
            <div className="flex gap-6 mt-2">
                <div className="flex-1">
                    <label className="text-[10px] font-bold text-green-400 uppercase tracking-widest">Allowed Apps ({settings.allowed_apps?.length || 0})</label>
                    <div className="flex flex-wrap gap-1 mt-1 max-h-20 overflow-y-auto">
                        {settings.allowed_apps && settings.allowed_apps.length > 0 ? settings.allowed_apps.map((app, i) => (
                            <span key={i} className="text-xs bg-green-900/30 text-green-400 px-2 py-0.5 rounded border border-green-500/30 flex items-center gap-1">
                                {app}<button onClick={() => {
                                    const newList = settings.allowed_apps.filter((_, idx) => idx !== i);
                                    handleChange('allowed_apps', newList);
                                    backend.request(JSON.stringify({action: 'set_allowed_apps', apps: newList}));
                                }} className="text-red-400 hover:text-red-300"><i className="fas fa-times text-[8px]"></i></button>
                            </span>
                        )) : <span className="text-xs text-gray-500 italic">No allowed apps configured</span>}
                    </div>
                </div>
                <div className="flex-1">
                    <label className="text-[10px] font-bold text-red-400 uppercase tracking-widest">Blocked Apps ({settings.blocked_apps?.length || 0})</label>
                    <div className="flex flex-wrap gap-1 mt-1 max-h-20 overflow-y-auto">
                        {settings.blocked_apps && settings.blocked_apps.length > 0 ? settings.blocked_apps.map((app, i) => (
                            <span key={i} className="text-xs bg-red-900/30 text-red-400 px-2 py-0.5 rounded border border-red-500/30 flex items-center gap-1">
                                {app}<button onClick={() => {
                                    const newList = settings.blocked_apps.filter((_, idx) => idx !== i);
                                    handleChange('blocked_apps', newList);
                                    backend.request(JSON.stringify({action: 'set_blocked_apps', apps: newList}));
                                }} className="text-red-400 hover:text-red-300"><i className="fas fa-times text-[8px]"></i></button>
                            </span>
                        )) : <span className="text-xs text-gray-500 italic">No blocked apps configured</span>}
                    </div>
                </div>
            </div>
        </div>

        {showProcessModal && (
            <div className="fixed inset-0 bg-black/90 z-50 flex items-center justify-center p-4 backdrop-blur-md">
                <div className="glass-panel p-6 max-w-2xl w-full max-h-[80vh] overflow-y-auto">
                    <div className="flex justify-between items-center mb-4">
                        <h3 className="text-white font-bold text-xl">📋 Running Applications</h3>
                        <button onClick={() => setShowProcessModal(false)} className="text-gray-400 hover:text-white"><i className="fas fa-times text-xl"></i></button>
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
                        }} className="glass-button px-4 py-2 rounded text-xs font-bold tracking-widest text-white uppercase bg-blue-600/30 border-blue-500/50 hover:bg-blue-600">Apply Rules</button>
                    </div>
                    <div className="flex flex-col gap-1 max-h-60 overflow-y-auto">
                        {settings.process_list && settings.process_list.map((p, i) => {
                            const isAllowed = settings.allowed_apps?.includes(p.name);
                            const isBlocked = settings.blocked_apps?.includes(p.name);
                            return <div key={i} className="flex items-center gap-3 p-2 bg-white/5 rounded border border-white/10 hover:bg-white/10 transition">
                                <input type="checkbox" className="process-checkbox" data-app={p.name} defaultChecked={isAllowed || isBlocked} />
                                <span className="text-sm text-gray-300 flex-grow">{p.name}</span>
                                <span className="text-[10px] text-gray-500">PID: {p.pid}</span>
                                <select data-action={p.name} className="glass-input text-xs px-2 py-1 rounded w-24" defaultValue={isAllowed ? 'allow' : isBlocked ? 'block' : 'ignore'}>
                                    <option value="ignore">Ignore</option><option value="allow">✅ Allow</option><option value="block">🚫 Block</option>
                                </select>
                            </div>;
                        })}
                    </div>
                </div>
            </div>
        )}
    </>;
});
