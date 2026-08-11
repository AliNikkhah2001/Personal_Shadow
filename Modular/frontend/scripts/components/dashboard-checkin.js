        const DailyCheckinWidget = ({ backend, dailyMetrics, setDailyMetrics }) => {
            const [checkin, setCheckin] = useState({
                sleep_hours: 7.5,
                sleep_quality: 3,
                energy_level: 3,
                mood_tags: [],
                stress_level: 2,
                notes: ""
            });
            const [showModal, setShowModal] = useState(false);
            
            const moodOptions = ["😊 Happy", "😌 Calm", "😴 Tired", "😰 Anxious", "😤 Stressed", "😞 Sad", "😐 Neutral", "🤩 Motivated", "🧠 Focused", "💪 Strong"];
            
            useEffect(() => {
                if (dailyMetrics) {
                    setCheckin({
                        sleep_hours: dailyMetrics.sleep_hours || 7.5,
                        sleep_quality: dailyMetrics.sleep_quality || 3,
                        energy_level: dailyMetrics.energy_level || 3,
                        mood_tags: dailyMetrics.mood_tags || [],
                        stress_level: dailyMetrics.stress_level || 2,
                        notes: dailyMetrics.notes || ""
                    });
                }
            }, [dailyMetrics]);

            const saveCheckin = () => {
                const today = new Date().toISOString().slice(0, 10);
                const payload = {
                    action: 'manage_analytics',
                    sub: 'save_daily_checkin',
                    date: today,
                    ...checkin
                };
                backend.request(JSON.stringify(payload)).then(res => {
                    const data = JSON.parse(res);
                    if (data.status === 'saved') {
                        setShowModal(false);
                        if (setDailyMetrics) setDailyMetrics(checkin);
                    }
                });
            };

            return (
                <div className="p-4 h-full flex flex-col w-full">
                    <h3 className="text-gray-300 font-bold uppercase tracking-widest text-sm border-b border-white/10 pb-2 mb-4 flex items-center justify-between">
                        <span>Daily Check-in</span>
                        <span className="text-[10px] font-bold text-blue-400">{new Date().toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}</span>
                    </h3>
                    
                    {!showModal ? (
                        <div className="flex-grow flex flex-col gap-4">
                            <div className="flex flex-wrap gap-2">
                                <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest w-full">Sleep</span>
                                <div className="flex items-center gap-2 flex-grow">
                                    <i className="fas fa-moon text-blue-400 text-lg"></i>
                                    <input type="number" step="0.5" min="0" max="14" className="glass-input p-2 rounded text-xs w-16" value={checkin.sleep_hours} readOnly />
                                    <span className="text-xs text-gray-500">hrs</span>
                                </div>
                            </div>
                            <div className="flex flex-wrap gap-2">
                                <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest w-full">Quality</span>
                                <div className="flex gap-1 flex-grow">
                                    {[1,2,3,4,5].map(q => (
                                        <div key={q} className={`flex-1 h-6 rounded border border-white/10 flex items-center justify-center text-xs font-bold cursor-default transition ${checkin.sleep_quality >= q ? 'bg-blue-600 text-white' : 'bg-white/5 text-gray-500'}`}>
                                            {q}
                                        </div>
                                    ))}
                                </div>
                            </div>
                            <div className="flex flex-wrap gap-2">
                                <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest w-full">Energy</span>
                                <div className="flex gap-1 flex-grow">
                                    {[1,2,3,4,5].map(e => (
                                        <div key={e} className={`flex-1 h-6 rounded border border-white/10 flex items-center justify-center text-xs font-bold cursor-default transition ${checkin.energy_level >= e ? 'bg-green-600 text-white' : 'bg-white/5 text-gray-500'}`}>
                                            {e}
                                        </div>
                                    ))}
                                </div>
                            </div>
                            <div className="flex flex-wrap gap-2">
                                <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest w-full">Stress</span>
                                <div className="flex gap-1 flex-grow">
                                    {[1,2,3,4,5].map(s => (
                                        <div key={s} className={`flex-1 h-6 rounded border border-white/10 flex items-center justify-center text-xs font-bold cursor-default transition ${checkin.stress_level >= s ? 'bg-red-600 text-white' : 'bg-white/5 text-gray-500'}`}>
                                            {s}
                                        </div>
                                    ))}
                                </div>
                            </div>
                            <div className="flex flex-wrap gap-2">
                                <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest w-full">Mood</span>
                                <div className="flex flex-wrap gap-1 flex-grow">
                                    {checkin.mood_tags.map((m, i) => (
                                        <span key={i} className="bg-purple-600/30 text-purple-300 px-2 py-0.5 rounded-full text-[9px] font-bold flex items-center gap-1">
                                            {m}
                                            <button onClick={() => { const newTags = checkin.mood_tags.filter((_el, idx) => idx !== i); setCheckin({...checkin, mood_tags: newTags}); }} className="text-purple-500 hover:text-purple-300"><i className="fas fa-times text-[8px]"></i></button>
                                        </span>
                                    ))}
                                </div>
                            </div>
                            {checkin.notes && (
                                <div className="text-xs text-gray-500 italic bg-black/30 p-2 rounded border border-white/5">
                                    "{checkin.notes}"
                                </div>
                            )}
                            <button onClick={() => setShowModal(true)} className="glass-button w-full py-2 rounded text-[11px] font-bold tracking-widest text-blue-300 uppercase border border-blue-500/30 bg-blue-900/30 hover:bg-blue-600 hover:text-white transition mt-2">
                                <i className="fas fa-edit mr-2"></i> Edit Check-in
                            </button>
                        </div>
                    ) : null}
                    
                    {showModal && (
                        <div className="absolute inset-0 bg-black/90 z-50 flex items-center justify-center p-4 backdrop-blur-md">
                            <div className="w-full max-w-lg flex flex-col gap-4 glass-panel p-6 border border-purple-500/30 shadow-[0_0_20px_rgba(168,85,247,0.2)]">
                                <h3 className="text-white font-bold text-lg">Daily Check-in</h3>
                                
                                <div className="flex flex-col gap-3">
                                    <div>
                                        <label className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-1">Sleep Duration (hours)</label>
                                        <input type="number" step="0.5" min="0" max="14" className="glass-input p-2 rounded text-sm" value={checkin.sleep_hours} onChange={e=>setCheckin({...checkin, sleep_hours: parseFloat(e.target.value)||0})} />
                                    </div>
                                    <div>
                                        <label className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-1">Sleep Quality</label>
                                        <div className="flex gap-2">
                                            {[1,2,3,4,5].map(q => (
                                                <button key={q} onClick={() => setCheckin({...checkin, sleep_quality: q})} className={`flex-1 h-10 rounded font-bold text-xs transition ${checkin.sleep_quality === q ? 'bg-blue-600 text-white shadow-[0_0_10px_rgba(59,130,246,0.5)]' : 'bg-white/5 text-gray-500 hover:bg-white/10'}`}>
                                                    {q} ⭐
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                    <div>
                                        <label className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-1">Energy Level</label>
                                        <div className="flex gap-2">
                                            {[1,2,3,4,5].map(e => (
                                                <button key={e} onClick={() => setCheckin({...checkin, energy_level: e})} className={`flex-1 h-10 rounded font-bold text-xs transition ${checkin.energy_level === e ? 'bg-green-600 text-white shadow-[0_0_10px_rgba(34,197,94,0.5)]' : 'bg-white/5 text-gray-500 hover:bg-white/10'}`}>
                                                    {e} ⚡
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                    <div>
                                        <label className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-1">Stress Level</label>
                                        <div className="flex gap-2">
                                            {[1,2,3,4,5].map(s => (
                                                <button key={s} onClick={() => setCheckin({...checkin, stress_level: s})} className={`flex-1 h-10 rounded font-bold text-xs transition ${checkin.stress_level === s ? 'bg-red-600 text-white shadow-[0_0_10px_rgba(239,68,68,0.5)]' : 'bg-white/5 text-gray-500 hover:bg-white/10'}`}>
                                                    {s} 😰
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                    <div>
                                        <label className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-1">Mood Tags</label>
                                        <div className="flex flex-wrap gap-2">
                                            {moodOptions.map(m => (
                                                <button key={m} onClick={() => setCheckin(prev => {
                                                    const has = prev.mood_tags.includes(m);
                                                    return {...prev, mood_tags: has ? prev.mood_tags.filter(t => t !== m) : [...prev.mood_tags, m]};
                                                })} className={`px-3 py-1.5 rounded-full text-xs font-bold transition ${checkin.mood_tags.includes(m) ? 'bg-purple-600 text-white' : 'bg-white/5 text-gray-400 hover:bg-white/10'}`}>
                                                    {m}
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                    <div>
                                        <label className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-1">Notes</label>
                                        <textarea placeholder="Anything notable today..." className="glass-input p-2 rounded text-sm h-16" value={checkin.notes} onChange={e=>setCheckin({...checkin, notes: e.target.value})}></textarea>
                                    </div>
                                </div>
                                
                                <div className="flex gap-3 mt-4">
                                    <button onClick={saveCheckin} className="glass-button bg-purple-600/50 hover:bg-purple-600 text-white font-bold py-2 rounded-lg flex-grow shadow-[0_0_15px_rgba(168,85,247,0.4)] tracking-widest uppercase text-sm">Save Check-in</button>
                                    <button onClick={() => setShowModal(false)} className="glass-button bg-gray-600/30 hover:bg-gray-600 text-white font-bold py-2 rounded-lg w-1/4 tracking-widest uppercase text-sm">Cancel</button>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            );
        };
