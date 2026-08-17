const SettingsView = React.memo(({ settings, setSettings, backend, networkFolders, setNetworkFolders, activityLogs, syncLogs }) => {
    const handleChange = useCallback((key, value) => setSettings(prev => ({...prev, [key]: value})), [setSettings]);
    const saveSettings = useCallback(() => backend.request(JSON.stringify({action: 'save_settings', data: settings})), [backend, settings]);
    const openFileDialog = useCallback(key => {
        backend.request(JSON.stringify({action: 'open_file_dialog'})).then(res => {
            const data = JSON.parse(res);
            if (!data.path) return;
            if (key === 'bg_image_path') {
                backend.request(JSON.stringify({action: 'save_wallpaper', path: data.path})).then(wallpaperRes => {
                    const wallpaper = JSON.parse(wallpaperRes);
                    if (wallpaper.data_url) setSettings(prev => ({...prev, bg_image_path: '', bg_image_data_url: wallpaper.data_url}));
                });
                return;
            }
            handleChange(key, data.path);
        });
    }, [backend, handleChange, setSettings]);

    return <div className="flex flex-col h-full fade-in bg-gray-900/50">
        <div className="flex justify-between items-center mb-6 shrink-0">
            <h2 className="text-2xl font-serif font-bold text-white tracking-widest uppercase drop-shadow-md">Settings</h2>
            <div className="flex gap-4 items-center"><button onClick={saveSettings} className="glass-button px-6 py-2 rounded text-xs font-bold text-white uppercase bg-blue-600/30 hover:bg-blue-600 border-blue-500/50 shadow-lg">Apply All Settings</button></div>
        </div>
        <div className="glass-panel p-6 flex-grow overflow-y-auto custom-scrollbar">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-6 max-w-4xl">
                <SettingsMonitoring settings={settings} setSettings={setSettings} backend={backend} handleChange={handleChange} />
                <SettingsSync settings={settings} setSettings={setSettings} backend={backend} networkFolders={networkFolders} setNetworkFolders={setNetworkFolders} activityLogs={activityLogs} syncLogs={syncLogs} handleChange={handleChange} />
                <SettingsSystem settings={settings} setSettings={setSettings} backend={backend} networkFolders={networkFolders} handleChange={handleChange} openFileDialog={openFileDialog} />
            </div>
        </div>
    </div>;
});

const NavBtn = React.memo(({id, icon, label, current, set, collapsed}) => <button onClick={() => set(id)} className={`flex items-center p-3 md:px-4 rounded-lg transition-all duration-200 group relative ${current === id ? 'bg-white/10 text-white border border-white/10 shadow-[inset_0_0_15px_rgba(255,255,255,0.05)]' : 'text-gray-400 hover:bg-white/5 hover:text-gray-200 border border-transparent'} ${collapsed ? 'justify-center' : 'justify-start'}`}>
    <i className={`fas ${icon} text-lg w-6 text-center transition-transform group-hover:scale-110 ${current === id ? 'text-blue-400' : ''} ${collapsed ? '' : 'mr-4'}`}></i>
    {!collapsed && <span className="font-bold text-[11px] tracking-widest uppercase whitespace-nowrap">{label}</span>}
    {collapsed && <div className="absolute left-14 bg-black border border-white/10 text-white text-[10px] font-bold uppercase tracking-widest px-2 py-1 rounded opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all whitespace-nowrap z-50 shadow-xl">{label}</div>}
</button>);
