const SettingsSystem = React.memo(({ settings, setSettings, backend, networkFolders, handleChange, openFileDialog }) => {
    const sounds = ["Basso", "Blow", "Bottle", "Frog", "Funk", "Glass", "Hero", "Morse", "Ping", "Pop", "Purr", "Sosumi", "Submarine", "Tink"];
    const numberField = (label, key, fallback, extra = {}) => <div className="flex flex-col gap-1">
        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">{label}</label>
        <input type="number" value={extra.nullish ? (settings[key] ?? fallback) : (settings[key] || fallback)} onChange={e => handleChange(key, extra.float ? parseFloat(e.target.value) : parseInt(e.target.value))} className="glass-input p-2.5 rounded text-sm" {...extra.attrs} />
    </div>;
    const selectField = (label, key, fallback, options, wide = false) => <div className={`flex flex-col gap-1 ${wide ? 'md:col-span-2' : ''}`}>
        <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">{label}</label>
        <select className="glass-input p-2.5 rounded text-sm" value={settings[key] || fallback} onChange={e => handleChange(key, e.target.value)}>
            {options.map(option => <option key={option}>{option}</option>)}
        </select>
    </div>;

    return <>
        <div className="md:col-span-2 text-blue-400 font-bold uppercase tracking-widest text-xs border-b border-white/10 pb-1 mt-4">UI & Typography</div>
        <div className="flex flex-col gap-1">
            <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">System Font Family</label>
            <input type="text" value={settings.font_family || 'Inter'} onChange={e => handleChange('font_family', e.target.value)} className="glass-input p-2.5 rounded text-sm" />
        </div>
        <div className="flex flex-col gap-1">
            <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Custom Font Path</label>
            <div className="flex gap-2"><input type="text" value={settings.custom_font_path || ''} readOnly className="glass-input p-2.5 rounded text-sm flex-grow opacity-50" /><button onClick={() => openFileDialog('custom_font_path')} className="glass-button px-4 rounded text-xs"><i className="fas fa-folder-open"></i></button></div>
        </div>
        <div className="flex flex-col gap-1 md:col-span-2">
            <label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Wallpaper / Background Image</label>
            <div className="flex gap-2">
                <input type="text" value={settings.bg_image_data_url ? 'Stored in synchronized database' : (settings.bg_image_path || '')} readOnly className="glass-input p-2.5 rounded text-sm flex-grow opacity-50" placeholder="Select an image file..." />
                <button onClick={() => openFileDialog('bg_image_path')} className="glass-button px-4 rounded text-xs text-blue-300 hover:text-blue-200"><i className="fas fa-image mr-1"></i> Browse</button>
                <button onClick={() => backend.request(JSON.stringify({action: 'clear_wallpaper'})).then(() => setSettings(prev => ({...prev, bg_image_path: '', bg_image_data_url: ''})))} className="glass-button px-4 rounded text-xs text-red-400 hover:text-red-300" title="Clear Wallpaper"><i className="fas fa-times mr-1"></i> Clear</button>
            </div>
        </div>
        {numberField('Global Font Size', 'font_size', 16)}
        <div className="flex flex-col gap-1"><label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Global Font Color</label><input type="color" value={settings.font_color || '#e2e8f0'} onChange={e => handleChange('font_color', e.target.value)} className="w-full h-10 rounded cursor-pointer border-0 p-0" /></div>
        <div className="flex flex-col gap-1 md:col-span-2"><label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Panel Opacity</label><input type="range" min="50" max="255" value={settings.panel_opacity || 180} onChange={e => handleChange('panel_opacity', parseInt(e.target.value))} className="w-full accent-blue-500 mt-2" /></div>

        <div className="md:col-span-2 text-blue-400 font-bold uppercase tracking-widest text-xs border-b border-white/10 pb-1 mt-4">Timeline Configuration</div>
        {numberField('Timeline Start Hour (0-23)', 'timeline_start_hour', 0, {nullish: true, attrs: {min: 0, max: 23}})}
        {numberField('Timeline End Hour (1-24)', 'timeline_end_hour', 24, {nullish: true, attrs: {min: 1, max: 24}})}
        {numberField('Pixels Per Hour (Scaling)', 'timeline_pixel_per_hour', 120, {nullish: true, attrs: {min: 60, max: 300}})}

        <div className="md:col-span-2 text-blue-400 font-bold uppercase tracking-widest text-xs border-b border-white/10 pb-1 mt-4">Horology & Clock Styles</div>
        {selectField('Clock Style', 'clock_style', 'Analog Classic', ['Analog Classic', 'Analog Minimal', 'Digital LED'])}
        {selectField('Case Shape', 'clock_case_shape', 'Round', ['Round', 'Square', 'Cushion', 'Tonneau'])}
        {selectField('Bezel', 'clock_bezel', 'Plain', ['Plain', 'Fluted', 'Diver', 'GMT (Pepsi)', 'Coin-Edge'])}
        {selectField('Hands Style', 'clock_hands', 'Classic', ['Classic', 'Spade', 'Breguet', 'Dauphine', 'Serpentine', 'Mercedes', 'Sword', 'Arrow'])}
        {selectField('Clock Indices', 'clock_indices', 'Baton', ['None', 'Arabic', 'Roman', 'Baton', 'Dot', 'California'])}
        {selectField('Clock Ticks', 'clock_ticks', 'Standard', ['Standard', 'Clean', 'Railroad', 'Crosshair'])}
        {selectField('Clock Complication', 'clock_complication', 'None', ['None', 'Date Window', 'Small Seconds'], true)}

        <div className="md:col-span-2 text-blue-400 font-bold uppercase tracking-widest text-xs border-b border-white/10 pb-1 mt-4">System Data & Behavior</div>
        <div className="flex items-center gap-4 md:col-span-2">
            <label className="text-xs font-bold text-gray-400 uppercase tracking-widest">Quiet Mode</label>
            <input type="checkbox" checked={settings.quiet_mode || false} onChange={e => { const checked = e.target.checked; handleChange('quiet_mode', checked); backend.request(JSON.stringify({action: 'set_quiet_mode', enabled: checked})); }} className="w-5 h-5 rounded bg-black/40 border border-white/20 accent-blue-500" />
            <span className="text-xs text-gray-400">{settings.quiet_mode ? 'Disables webcam, sounds, and speech' : 'Full mode with webcam & sounds'}</span>
        </div>
        <div className="flex flex-col gap-1"><label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Quotes JSON Path</label><div className="flex gap-2"><input type="text" value={settings.quotes_path || ''} onChange={e => handleChange('quotes_path', e.target.value)} className="glass-input p-2.5 rounded text-sm flex-grow" /><button onClick={() => openFileDialog('quotes_path')} className="glass-button px-4 rounded text-xs"><i className="fas fa-folder-open"></i></button></div></div>
        {numberField('Force Close Apps After (min)', 'force_close_apps_mins', 5)}

        <div className="md:col-span-2 text-blue-400 font-bold uppercase tracking-widest text-xs border-b border-white/10 pb-1 mt-4">Audio & Speech Alerts</div>
        <div className="flex gap-6 md:col-span-2">
            <div className="flex items-center gap-2"><label className="text-xs font-bold text-gray-400 uppercase tracking-widest">Mute Sounds</label><input type="checkbox" checked={settings.mute_sounds || false} onChange={e => handleChange('mute_sounds', e.target.checked)} className="w-5 h-5 rounded bg-black/40 border border-white/20 accent-blue-500" /></div>
            <div className="flex items-center gap-2"><label className="text-xs font-bold text-gray-400 uppercase tracking-widest">Mute Speech</label><input type="checkbox" checked={settings.mute_speech || false} onChange={e => handleChange('mute_speech', e.target.checked)} className="w-5 h-5 rounded bg-black/40 border border-white/20 accent-blue-500" /></div>
        </div>
        {selectField('App Distraction Sound', 'sound_app_dist', 'Ping', sounds)}
        {selectField('Camera Distraction Sound', 'sound_cam_dist', 'Basso', sounds)}
        {selectField('Camera Error Sound', 'sound_cam_err', 'Hero', sounds)}
        {numberField('Beep Frequency (seconds)', 'beep_freq', 3)}
        {numberField('Loop Beeps at 1m', 'loop_1m', 2)}{numberField('Loop Beeps at 5m', 'loop_5m', 5)}
        {numberField('Loop Beeps at 15m', 'loop_15m', 10)}{numberField('Loop Beeps at 30m', 'loop_30m', 20)}{numberField('Loop Beeps at 60m', 'loop_60m', 30)}
        <div className="flex flex-col gap-1 md:col-span-2"><label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Distraction Spoken Phrase</label><input type="text" value={settings.speech_dist || ''} onChange={e => handleChange('speech_dist', e.target.value)} className="glass-input p-2.5 rounded text-sm" /></div>
        <div className="flex flex-col gap-1 md:col-span-2"><label className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-1">Completion Spoken Phrase</label><input type="text" value={settings.speech_comp || ''} onChange={e => handleChange('speech_comp', e.target.value)} className="glass-input p-2.5 rounded text-sm" /></div>

        <div className="md:col-span-2 text-blue-400 font-bold uppercase tracking-widest text-xs border-b border-white/10 pb-1 mt-4">Vision Tracker Settings</div>
        {selectField('Vision Mode', 'vision_mode', 'Strict (Face & Eyes)', ['Strict (Face & Eyes)', 'Visible (Face Only)'])}
        {numberField('Vision Sample Interval (ms)', 'vision_sample_interval', 30)}{numberField('Vision Distraction Delay (s)', 'dist_delay', 3)}
        {numberField('Face Scale Factor', 'face_scale_factor', 1.2, {float: true, attrs: {step: 0.05}})}
        {numberField('Face Min Neighbors', 'face_min_neighbors', 8)}{numberField('Face Min Size (px)', 'face_min_size', 120)}
    </>;
});
