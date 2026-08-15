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

    return <div className="flex flex-col h-full fade-in">
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
