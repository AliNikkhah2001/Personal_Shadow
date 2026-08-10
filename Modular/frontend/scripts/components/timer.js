const ProductivityHubView = ({ backend, timerState, flatGoals, queue, refreshQueue, settings, todaySessions, courseColors }) => {
            const [dur, setDur] = useState(25); const [crs, setCrs] = useState(""); const [type, setType] = useState("Work");
            const [editingId, setEditingId] = useState(null); const [activeTab, setActiveTab] = useState("timeline");
            const [showProcessList, setShowProcessList] = useState(false); const [selectedProcesses, setSelectedProcesses] = useState([]);
            const [isPaused, setIsPaused] = useState(false);
            
            // Timeline Config from settings
            const timelineStartHour = settings?.timeline_start_hour ?? 0;
            const timelineEndHour = settings?.timeline_end_hour ?? 24;
            const timelinePixelPerHour = settings?.timeline_pixel_per_hour ?? 120;
            const timelineHours = timelineEndHour - timelineStartHour;
            const timelineWidth = timelineHours * timelinePixelPerHour;

            // History Tab States
            const [historyData, setHistoryData] = useState([]);
            const [selectedDateFilter, setSelectedDateFilter] = useState("");
            
            // Session Modals
            const [showNoteModal, setShowNoteModal] = useState(false);
            const [sessionNote, setSessionNote] = useState("");
            const [noteSessionId, setNoteSessionId] = useState(null);
            const [showStatsModal, setShowStatsModal] = useState(false);
            const [statsSession, setStatsSession] = useState(null);

            const timelineContainerRef = useRef(null);

            // Shut off intense base64 video encoding when not on the Vision tab
            useEffect(() => {
                if (backend) {
                    backend.request(JSON.stringify({action: 'set_vision_ui', active: activeTab === 'vision'}));
                }
            }, [activeTab, backend]);

            useEffect(() => {
                if (activeTab === 'timeline' && timelineContainerRef.current) {
                    const now = new Date();
                    const mins = now.getHours() * 60 + now.getMinutes();
                    const relativeMins = mins - (timelineStartHour * 60);
                    const pxPerMin = timelinePixelPerHour / 60;
                    const scrollTarget = (relativeMins * pxPerMin) - (timelineContainerRef.current.clientWidth / 2);
                    timelineContainerRef.current.scrollLeft = Math.max(0, scrollTarget);
                }
                
                if (activeTab === 'history' && backend) {
                    backend.request(JSON.stringify({action: 'get_history_data'})).then(res => {
                        const data = JSON.parse(res);
                        setHistoryData(data.history_sessions || []);
                        if (data.history_sessions && data.history_sessions.length > 0) {
                            const firstDate = data.history_sessions[0].timestamp.split('T')[0];
                            if(!selectedDateFilter) setSelectedDateFilter(firstDate);
                        }
                    });
                }
            }, [todaySessions, activeTab]);

        useEffect(() => {
                if (timerState.last_completed_session_id && timerState.last_completed_session_id !== noteSessionId) {
                    setNoteSessionId(timerState.last_completed_session_id);
                    setSessionNote("");
                    
                    // Show the Note Modal automatically
                    setShowNoteModal(true);
                    
                    // Also immediately trigger the timelapse via the backend
                    if (timerState.last_session_data && timerState.last_session_data.timelapse_path) {
                        backend.request(JSON.stringify({
                            action: 'play_timelapse', 
                            path: timerState.last_session_data.timelapse_path,
                            duration: timerState.last_session_data.duration,
                            distractions: timerState.last_session_data.distractions,
                            data: timerState.last_session_data
                        }));
                    }
                }
            }, [timerState.last_completed_session_id, timerState.last_session_data, noteSessionId, backend]);
            const saveSessionNote = () => {
                if (!backend) return;
                backend.request(JSON.stringify({action: 'save_session_note', session_id: noteSessionId, note: sessionNote})).then(() => {
                    setShowNoteModal(false);
                    if(backend) {
                        backend.request(JSON.stringify({action: 'get_today_data'})).then(res => {
                            // Backend fetches updated data; React parent receives via channel
                        });
                    }
                });
            };

            const startFocusSession = () => {
                if (!backend) return;
                if (settings && settings.app_monitoring_enabled && !showProcessList) {
                    backend.request(JSON.stringify({action: 'get_processes'})).then(res => {
                        const data = JSON.parse(res); setSelectedProcesses(data.processes || []); setShowProcessList(true);
                    }); return;
                }
                
                if (queue && queue.some(q => q.status === 'pending' || q.status === 'active')) {
                    backend.request(JSON.stringify({action: 'start_timer', queue_id: 'auto'})).then(res => {
                        const data = JSON.parse(res); if (data.status === 'started') { setShowProcessList(false); setIsPaused(false); }
                    });
                } else {
                    backend.request(JSON.stringify({action: 'start_timer', duration: parseInt(dur) || 25, course: crs || "General", type: type || "Work"})).then(res => {
                        const data = JSON.parse(res); if (data.status === 'started') { setShowProcessList(false); setIsPaused(false); }
                    });
                }
            };

            const getTaskColor = (courseName, isBreak) => {
                if (isBreak) return courseColors && courseColors['Break'] ? courseColors['Break'] : 'rgba(100, 100, 100, 0.8)';
                if (!courseName || courseName === 'General') return courseColors && courseColors['General'] ? courseColors['General'] : 'rgba(64, 196, 99, 0.8)';
                return courseColors && courseColors[courseName] ? courseColors[courseName] : 'rgba(64, 196, 99, 0.8)';
            };

            const handleAction = (sub, item={}) => {
                const payload = { action: 'manage_queue', sub: sub, id: item.id, title: item.title || crs || "General", duration: item.duration || dur, type: item.type || type, course: item.course || crs || "General" };
                backend.request(JSON.stringify(payload)).then(res => { const data = JSON.parse(res); if(data.queue) refreshQueue(data.queue); setEditingId(null); });
            };

            const toggleTimer = () => {
                if (!backend) return;
                if (timerState.is_running) { 
                    backend.request(JSON.stringify({action: 'pause_timer'})); 
                    setIsPaused(true); 
                } else if (timerState.total_time > 0 && timerState.time_left > 0 && timerState.time_left < timerState.total_time) {
                    backend.request(JSON.stringify({action: 'resume_timer'})); 
                    setIsPaused(false);
                } else { 
                    startFocusSession(); 
                }
            };
            const renderTimelineHours = () => {
                const hours = [];
                for (let i = timelineStartHour; i <= timelineEndHour; i++) {
                    const pos = (i - timelineStartHour) * timelinePixelPerHour;
                    hours.push(
                        <div key={`hr-${i}`} className="absolute top-0 bottom-0 border-l border-white/10 flex flex-col justify-between py-1" style={{ left: `${pos}px` }}>
                            <span className="text-[10px] text-gray-500 font-bold pl-1 -translate-x-1/2 bg-black/50 px-1 rounded">{i.toString().padStart(2, '0')}:00</span>
                        </div>
                    );
                }
                return hours;
            };

            // PERFECT MATH: Include seconds to prevent block drifting and overlap
            const now = new Date();
            const nowMins = now.getHours() * 60 + now.getMinutes() + (now.getSeconds() / 60);
            const nowRelativeMins = nowMins - (timelineStartHour * 60);
            
            const tTot = Number(timerState.total_time) || 0;
            const tLeft = Number(timerState.time_left) || 0;
            const workedMins = (tTot > 0) ? ((tTot - tLeft) / 60) : 0;
            const activeStartMins = nowRelativeMins - workedMins;
            const activeWidthMins = tTot / 60;
            const isActiveSession = timerState.is_running || (tTot > 0 && tLeft < tTot);
            
            // Queue blocks must start *after* the active session to prevent squishing
            let futureStartMins = isActiveSession ? (activeStartMins + activeWidthMins) : nowRelativeMins;
            
            const historyDates = [...new Set(historyData.map(s => s.timestamp.split('T')[0]))];
            const filteredHistory = historyData.filter(s => s.timestamp.split('T')[0] === selectedDateFilter);

            return (
                <div className="h-full flex flex-col fade-in relative">
                    <div className="flex justify-between items-center mb-4 shrink-0"><h2 className="text-2xl font-serif font-bold text-white tracking-widest uppercase drop-shadow-md">Focus Hub</h2></div>
                    <div className="flex gap-6 border-b border-white/10 mb-6 shrink-0">
                        <button onClick={() => setActiveTab('timeline')} className={`pb-2 text-xs font-bold uppercase tracking-widest transition-all ${activeTab === 'timeline' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-gray-500 hover:text-gray-300'}`}>Timeline & Queue</button>
                        <button onClick={() => setActiveTab('history')} className={`pb-2 text-xs font-bold uppercase tracking-widest transition-all ${activeTab === 'history' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-gray-500 hover:text-gray-300'}`}>History & Notes</button>
                        <button onClick={() => setActiveTab('vision')} className={`pb-2 text-xs font-bold uppercase tracking-widest transition-all ${activeTab === 'vision' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-gray-500 hover:text-gray-300'}`}>Vision Tracker</button>
                    </div>

                    {activeTab === 'timeline' && (
                        <div className="flex flex-col flex-grow overflow-hidden">
                            <div className="flex flex-wrap items-center gap-3 mb-4 w-full glass-panel p-3 shrink-0 bg-black/40 z-10">
                                <select className="glass-input px-3 py-1.5 rounded text-xs font-bold uppercase w-48" value={crs} onChange={e => setCrs(e.target.value)}><option value="">General</option>{flatGoals && flatGoals.map(c => <option key={c} value={c}>{c}</option>)}</select>
                                <input type="number" className="glass-input px-3 py-1.5 rounded text-xs font-bold uppercase w-20" value={dur} onChange={e => setDur(parseInt(e.target.value))} />
                                <select className="glass-input px-3 py-1.5 rounded text-xs font-bold uppercase w-28" value={type} onChange={e => setType(e.target.value)}><option>Work</option><option>Break</option></select>
                                {editingId ? (
                                    <button onClick={() => handleAction('edit', {id: editingId})} className="glass-button px-5 py-1.5 rounded text-[11px] font-bold text-blue-300 uppercase">Save</button>
                                ) : (
                                    <button onClick={() => handleAction('add')} className="glass-button px-5 py-1.5 rounded text-[11px] font-bold text-gray-200 uppercase">+ Add</button>
                                )}
                                <button onClick={() => handleAction('clear')} className="glass-button px-5 py-1.5 rounded text-[11px] font-bold text-red-300 uppercase ml-auto">Clear All</button>
                            </div>

                            <div className="flex flex-col lg:flex-row gap-4 flex-grow overflow-hidden">
                                <div className="glass-panel rounded-xl flex flex-col p-6 w-full lg:w-2/3 bg-black/20 overflow-hidden">
                                    <div className="flex justify-between items-end shrink-0 mb-6">
                                        <div className={`text-6xl lg:text-7xl font-mono font-bold tracking-widest drop-shadow-lg ${timerState.is_running ? 'text-blue-400' : isPaused ? 'text-yellow-400' : 'text-gray-300'}`}>{timerState.time_str || "25:00"}</div>
                                        <div className="flex gap-3">
                                            <button onClick={toggleTimer} className={`px-6 py-4 rounded-lg text-xs font-bold tracking-widest text-white uppercase shadow-lg transition-colors ${timerState.is_running ? 'bg-yellow-600/50 hover:bg-yellow-600 border border-yellow-500/50' : 'bg-green-600/50 hover:bg-green-600 border border-green-500/50'}`}><i className={`fas ${timerState.is_running ? 'fa-pause' : 'fa-play'} mr-2`}></i>{timerState.is_running ? 'Pause' : isPaused ? 'Resume' : 'Start'}</button>
                                            <button onClick={() => { backend.request(JSON.stringify({action: 'stop_timer'})); setIsPaused(false); }} className="px-6 py-4 rounded-lg text-xs font-bold tracking-widest text-white uppercase bg-red-600/50 hover:bg-red-600 border border-red-500/50 shadow-lg transition-colors"><i className="fas fa-stop mr-2"></i> Stop</button>
                                        </div>
                                    </div>
                                    
                                    <h3 className="text-gray-400 text-[10px] font-bold tracking-widest uppercase mb-2">Absolute Daily Timeline ({timelineStartHour.toString().padStart(2, '0')}:00 - {timelineEndHour.toString().padStart(2, '0')}:00)</h3>
                                    <div ref={timelineContainerRef} className="w-full h-36 bg-black/60 border border-white/10 rounded-xl overflow-x-auto custom-scrollbar relative shadow-inner shrink-0 cursor-ew-resize">
                                        <div className="absolute top-0 left-0 h-full" style={{ width: `${timelineWidth}px` }}>
                                            {renderTimelineHours()}
                                            
                                            {/* Current Time Line */}
                                            <div className="absolute top-0 bottom-0 w-0.5 bg-blue-500 shadow-[0_0_10px_#3b82f6] z-50" style={{ left: `${nowRelativeMins * (timelinePixelPerHour / 60)}px` }}>
                                                <div className="absolute -top-1 -translate-x-1/2 w-3 h-3 bg-blue-500 rounded-full"></div>
                                            </div>

                                            {/* Plotted Past Sessions */}
                                            {todaySessions && todaySessions.map((s, i) => {
                                                const end = new Date(s.timestamp);
                                                const endMins = end.getHours() * 60 + end.getMinutes();
                                                const endRelativeMins = endMins - (timelineStartHour * 60);
                                                const plannedDur = s.duration;
                                                const actualDur = s.actual_duration || s.duration;
                                                const startRelativeMins = endRelativeMins - actualDur;
                                                const pxPerMin = timelinePixelPerHour / 60;
                                                
                                                return (
                                                    <div key={`past-${i}`} onClick={() => { setStatsSession(s); setShowStatsModal(true); }} className="absolute top-10 h-14 cursor-pointer group" 
                                                         style={{ left: `${startRelativeMins * pxPerMin}px`, width: `${Math.max(plannedDur, actualDur) * pxPerMin}px` }}>
                                                        <div className="absolute top-0 left-0 h-full border-2 border-dashed border-white/30 rounded-md pointer-events-none" style={{ width: `${plannedDur * pxPerMin}px` }}></div>
                                                        
                                                        <div className="absolute top-0 left-0 h-full rounded-md shadow-md flex items-center justify-center overflow-hidden border border-white/20"
                                                             style={{ width: `${actualDur * pxPerMin}px`, backgroundColor: getTaskColor(s.course, s.type === 'Break') }}>
                                                            <span className="text-[9px] font-bold text-white drop-shadow-md truncate px-1 opacity-0 group-hover:opacity-100 transition-opacity">{s.course}</span>
                                                            
                                                            {s.distraction_data && s.distraction_data.map((d, di) => {
                                                                const dType = d.length > 2 ? d[2] : "Manual";
                                                                const distColor = dType === "App" ? "bg-orange-500" : (dType === "Camera" ? "bg-red-500" : "bg-yellow-400");
                                                                return (
                                                                    <div key={di} className={`absolute top-0 h-full ${distColor} z-10 opacity-80`} style={{ left: `${(d[0] / actualDur) * 100}%`, width: `${Math.max((d[1] / actualDur) * 100, 2)}%` }}></div>
                                                                );
                                                            })}
                                                        </div>
                                                    </div>
                                                );
                                            })}

{/* Active Session Pulsing Block */}
                                            {isActiveSession && (
                                                <div className={`absolute top-10 h-14 rounded-md shadow-[0_0_15px_rgba(255,255,255,0.3)] flex items-center justify-center overflow-hidden border-2 border-white/50 ${timerState.is_running ? 'animate-pulse' : 'opacity-50 grayscale'}`} 
                                                     style={{ left: `${activeStartMins * pxPerMin}px`, width: `${activeWidthMins * pxPerMin}px`, backgroundColor: getTaskColor(timerState.course, false) }}>
                                                    <span className="text-[10px] font-bold text-white drop-shadow-md z-10">{timerState.course}</span>
                                                    
                                                    {/* Active Distraction Markers */}
                                                    {timerState.distraction_log && timerState.distraction_log.map((d, di) => {
                                                       const dType = d.length > 2 ? d[2] : "Manual";
                                                       const distColor = dType === "App" ? "bg-orange-500" : (dType === "Camera" ? "bg-red-500" : "bg-yellow-400");
                                                       return (
                                                           <div key={di} className={`absolute top-0 h-full ${distColor} z-10 opacity-80`} style={{ left: `${(d[0] / activeWidthMins) * 100}%`, width: `${Math.max((d[1] / activeWidthMins) * 100, 2)}%` }}></div>
                                                       );
                                                    })}
                                                </div>
                                            )}
                                            
                                            {/* Future Queue Blocks (Strictly filtered to ONLY pending to prevent active overlap) */}
                                            {queue && queue.filter(q => q.status === 'pending').map((q, i) => {
                                                const start = futureStartMins;
                                                futureStartMins += q.duration;
                                                return (
                                                    <div key={`q-${q.id}`} className="absolute top-10 h-14 rounded-md flex items-center justify-center overflow-hidden border border-white/10 opacity-50" 
                                                         style={{ left: `${start * pxPerMin}px`, width: `${q.duration * pxPerMin}px`, backgroundColor: getTaskColor(q.course, q.type === 'Break') }}>
                                                        <span className="text-[9px] font-bold text-white drop-shadow-md truncate px-1">{q.duration}m</span>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </div>
                                    
                                    <div className="flex-grow mt-6 bg-black/30 rounded-xl border border-white/10 p-4 overflow-y-auto">
                                        <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest border-b border-white/10 pb-2 mb-3">Today's Completed Blocks</h3>
                                        <div className="flex flex-col gap-2">
                                            {(!todaySessions || todaySessions.length === 0) && <div className="text-gray-500 text-xs italic">No blocks completed today.</div>}
                                            {todaySessions && todaySessions.slice().reverse().map(s => (
                                                <div key={s.id} onClick={() => { setStatsSession(s); setShowStatsModal(true); }} className="flex justify-between items-center p-3 bg-black/60 border border-white/5 rounded-lg hover:bg-white/5 transition cursor-pointer group">
                                                    <div className="flex items-center gap-4">
                                                        <div className="w-4 h-4 rounded-full shadow-lg" style={{backgroundColor: getTaskColor(s.course, s.type === 'Break')}}></div>
                                                        <div className="flex flex-col">
                                                            <span className="text-sm font-bold text-white">{s.course} <span className="text-gray-400 text-xs font-normal">(Plan: {s.duration}m | Act: {s.actual_duration || s.duration}m)</span></span>
                                                            <span className="text-[10px] text-gray-500 font-mono tracking-wider">Ended at {new Date(s.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
                                                        </div>
                                                    </div>
                                                    <div className="flex items-center gap-6">
                                                        <div className="flex flex-col items-end">
                                                            <span className="text-xs font-bold text-red-400"><i className="fas fa-exclamation-triangle mr-1"></i> {s.distractions} Distracts</span>
                                                            {s.note ? <span className="text-[10px] text-blue-400"><i className="fas fa-sticky-note mr-1"></i> Note attached</span> : <span className="text-[10px] text-gray-600 italic opacity-0 group-hover:opacity-100 transition">Click to add note</span>}
                                                        </div>
                                                        {s.timelapse_path && s.type === 'Work' && (
                                                            <button onClick={(e) => { e.stopPropagation(); backend.request(JSON.stringify({action: 'play_timelapse', path: s.timelapse_path, duration: s.duration, distractions: s.distractions, data: s}))}} 
                                                                    className="w-10 h-10 rounded-full bg-blue-600/30 hover:bg-blue-600 text-white flex items-center justify-center transition border border-blue-500/50 shadow-[0_0_10px_rgba(59,130,246,0.3)]">
                                                                <i className="fas fa-play text-sm ml-1"></i>
                                                            </button>
                                                        )}
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                </div>

                                <div className="glass-panel rounded-xl flex flex-col p-4 w-full lg:w-1/3 bg-black/20 overflow-y-auto">
                                    <h3 className="text-gray-400 text-[10px] font-bold tracking-widest uppercase mb-4 border-b border-white/10 pb-2">Up Next in Queue</h3>
                                    <div className="flex flex-col gap-2">
                                        {queue && queue.filter(q => q.status !== 'completed').map(q => {
                                            const isActive = timerState.active_queue_id === q.id;
                                            return (
                                                <div key={q.id} className={`flex flex-col p-3 rounded-lg transition group border ${isActive ? 'bg-blue-600/20 border-blue-500/40 shadow-[inset_0_0_15px_rgba(59,130,246,0.2)]' : 'bg-white/5 hover:bg-white/10 border-white/5'}`}>
                                                    <div className="flex justify-between items-center mb-1">
                                                        <span className={`text-sm ${isActive ? 'text-white font-bold' : 'text-gray-300 font-bold group-hover:text-white'}`}>
                                                            [{q.type}] {q.course}
                                                        </span>
                                                        <span className="text-xs font-mono text-gray-400">{q.duration}m</span>
                                                    </div>
                                                    
                                                    {!isActive && (
                                                        <div className="flex justify-end gap-4 opacity-0 group-hover:opacity-100 transition mt-2">
                                                            <button onClick={() => {setEditingId(q.id); setCrs(q.course); setDur(q.duration); setType(q.type);}} className="text-[10px] font-bold text-gray-400 hover:text-yellow-400 uppercase tracking-widest"><i className="fas fa-edit mr-1"></i>Edit</button>
                                                            <button onClick={() => handleAction('delete', {id: q.id})} className="text-[10px] font-bold text-gray-400 hover:text-red-400 uppercase tracking-widest"><i className="fas fa-trash mr-1"></i>Remove</button>
                                                        </div>
                                                    )}
                                                </div>
                                            );
                                        })}
                                        {queue && queue.filter(q => q.status !== 'completed').length === 0 && <div className="text-xs text-gray-500 italic text-center py-4">Queue is empty</div>}
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}

                    {activeTab === 'history' && (
                        <div className="flex flex-col flex-grow overflow-hidden gap-4">
                            <div className="flex gap-2 shrink-0 bg-black/40 p-2 rounded-xl border border-white/10 overflow-x-auto custom-scrollbar">
                                {historyDates.map(dateStr => (
                                    <button key={dateStr} onClick={() => setSelectedDateFilter(dateStr)} className={`px-4 py-2 rounded-lg text-xs font-bold whitespace-nowrap transition ${selectedDateFilter === dateStr ? 'bg-blue-600 text-white shadow-[0_0_10px_rgba(59,130,246,0.5)]' : 'bg-white/5 text-gray-400 hover:bg-white/10'}`}>
                                        {dateStr === new Date().toISOString().split('T')[0] ? 'Today' : dateStr}
                                    </button>
                                ))}
                                {historyDates.length === 0 && <span className="text-gray-500 text-xs py-2 px-4 italic">No history found.</span>}
                            </div>
                            
                            <div className="glass-panel flex-grow overflow-y-auto p-6 rounded-xl flex flex-col gap-4">
                                {filteredHistory.map(s => (
                                    <div key={s.id} onClick={() => { setStatsSession(s); setShowStatsModal(true); }} className="bg-black/40 border border-white/10 rounded-xl p-4 hover:bg-white/5 transition flex flex-col gap-3 cursor-pointer group">
                                        <div className="flex justify-between items-start">
                                            <div className="flex items-center gap-3">
                                                <div className="w-4 h-4 rounded-full" style={{backgroundColor: getTaskColor(s.course, s.type === 'Break')}}></div>
                                                <div>
                                                    <h4 className="text-white font-bold text-lg">{s.course} <span className="text-xs font-normal text-gray-400 ml-2">[{s.type}]</span></h4>
                                                    <span className="text-xs font-mono text-gray-500">{new Date(s.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
                                                </div>
                                            </div>
                                            <div className="flex gap-4 text-right">
                                                <div className="flex flex-col"><span className="text-[10px] text-gray-500 uppercase tracking-widest">Duration</span><span className="text-blue-400 font-bold font-mono">{s.actual_duration || s.duration} / {s.duration}m</span></div>
                                                <div className="flex flex-col"><span className="text-[10px] text-gray-500 uppercase tracking-widest">Distractions</span><span className="text-red-400 font-bold font-mono">{s.distractions}</span></div>
                                                {s.timelapse_path && (
                                                    <button onClick={(e) => { e.stopPropagation(); backend.request(JSON.stringify({action: 'play_timelapse', path: s.timelapse_path, duration: s.duration, distractions: s.distractions, data: s}))}} 
                                                            className="w-10 h-10 rounded-full bg-blue-600/30 hover:bg-blue-600 text-white flex items-center justify-center transition border border-blue-500/50 ml-2">
                                                        <i className="fas fa-play text-sm ml-1"></i>
                                                    </button>
                                                )}
                                            </div>
                                        </div>
                                        
                                        {/* Distraction Sub-Bar */}
                                        {s.distraction_data && s.distraction_data.length > 0 && (
                                            <div className="w-full h-2 bg-white/5 rounded-full flex overflow-hidden border border-white/10 relative mt-2">
                                                {s.distraction_data.map((d, di) => {
                                                    const dType = d.length > 2 ? d[2] : "Manual";
                                                    const distColor = dType === "App" ? "bg-orange-500" : (dType === "Camera" ? "bg-red-500" : "bg-yellow-400");
                                                    const totalDur = s.actual_duration || s.duration;
                                                    return (
                                                        <div key={di} className={`absolute h-full ${distColor} opacity-80`} title={`${dType}: ${d[1].toFixed(1)}m`} style={{ left: `${(d[0] / totalDur) * 100}%`, width: `${Math.max((d[1] / totalDur) * 100, 1)}%` }}></div>
                                                    );
                                                })}
                                            </div>
                                        )}
                                        
                                        {/* Session Note */}
                                        {s.note ? (
                                            <div className="bg-blue-900/20 border border-blue-500/30 p-3 rounded mt-2">
                                                <div className="text-[10px] text-blue-400 uppercase tracking-widest mb-1"><i className="fas fa-sticky-note mr-1"></i> Session Note</div>
                                                <p className="text-sm text-gray-200 whitespace-pre-wrap">{s.note}</p>
                                            </div>
                                        ) : (
                                            <div className="text-xs text-gray-500 italic mt-2 opacity-0 group-hover:opacity-100 transition">Click to add session notes...</div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {activeTab === 'vision' && (
                        <div className="flex-grow glass-panel rounded-xl flex items-center justify-center p-4 relative overflow-hidden bg-black/40">
                            {timerState.is_running ? (
                                <img src="http://127.0.0.1:5050/video_feed" onError={(e) => { e.target.style.display='none'; e.target.nextSibling.style.display='flex'; }} className="w-full h-full object-contain opacity-90 rounded drop-shadow-2xl" />
                            ) : null}
                            <div className="text-gray-500 flex flex-col items-center" style={{display: timerState.is_running ? 'none' : 'flex'}}>
                                <i className="fas fa-video-slash text-5xl mb-4 opacity-50"></i>
                                <p className="text-sm font-bold uppercase tracking-widest">Vision Tracker Offline / Paused</p>
                            </div>
                            <div className="absolute top-6 left-6 bg-black/80 px-4 py-2 rounded text-[10px] font-mono text-blue-400 font-bold border border-white/10 shadow-lg"><i className="fas fa-circle text-[8px] text-red-500 mr-2 animate-pulse"></i> VISION ENGINE ACTIVE</div>
                        </div>
                    )}




{/* Post-Session Note Modal (Now with Markdown!) */}
                    {showNoteModal && (
                        <div className="absolute inset-0 bg-black/90 z-[100] flex items-center justify-center p-6 backdrop-blur-md">
                            <div className="w-full max-w-5xl flex flex-col gap-3 glass-panel p-8 border-blue-500/50 border-2 shadow-[0_0_50px_rgba(59,130,246,0.3)]">
                                <h3 className="text-white font-bold text-2xl mb-1"><i className="fas fa-flag-checkered text-green-400 mr-2"></i> Session Complete!</h3>
                                <p className="text-gray-400 text-sm mb-4">Add your session notes using Markdown. They will be pinned permanently to this block.</p>
                                
                                <div className="flex flex-col md:flex-row gap-6 h-[400px]">
                                    <div className="w-full md:w-1/2 flex flex-col">
                                        <div className="bg-black/60 px-3 py-2 border-b border-white/10 rounded-t text-xs font-bold text-gray-400 tracking-widest uppercase">Markdown Editor</div>
                                        <textarea className="glass-input p-4 rounded-b text-sm w-full flex-grow resize-none custom-scrollbar font-mono text-gray-200" placeholder="## What did I accomplish?&#10;- Fixed the bug&#10;- Read chapter 2" value={sessionNote} onChange={e=>setSessionNote(e.target.value)} autoFocus></textarea>
                                    </div>
                                    <div className="w-full md:w-1/2 flex flex-col">
                                        <div className="bg-black/60 px-3 py-2 border-b border-white/10 rounded-t text-xs font-bold text-gray-400 tracking-widest uppercase">Live Preview</div>
                                        <div className="flex-grow bg-black/30 border border-white/10 rounded-b p-4 overflow-y-auto text-gray-200 prose prose-invert max-w-none text-sm custom-scrollbar" dangerouslySetInnerHTML={{__html: marked.parse(sessionNote || "*Preview will appear here*")}}></div>
                                    </div>
                                </div>
                                
                                <div className="flex gap-4 mt-6">
                                    <button onClick={saveSessionNote} className="glass-button bg-blue-600/70 hover:bg-blue-600 text-white font-bold py-3 rounded-lg flex-grow shadow-[0_0_15px_rgba(59,130,246,0.4)] tracking-widest uppercase text-sm">Save Markdown Note</button>
                                    <button onClick={() => setShowNoteModal(false)} className="glass-button bg-gray-600/30 hover:bg-gray-600 text-white font-bold py-3 rounded-lg w-1/4 tracking-widest uppercase text-sm">Skip</button>
                                </div>
                            </div>
                        </div>
                    )}




                    {/* Session Stats Modal */}
                    {showStatsModal && statsSession && (
                        <div className="absolute inset-0 bg-black/90 z-50 flex items-center justify-center rounded-xl p-4 backdrop-blur-md">
                            <div className="w-full max-w-lg flex flex-col gap-3 glass-panel p-6 border-white/20 border">
                                <div className="flex justify-between items-center border-b border-white/10 pb-3 mb-2">
                                    <h3 className="text-white font-bold text-lg uppercase tracking-widest">{statsSession.course} <span className="text-xs text-gray-500 ml-2 font-mono">{new Date(statsSession.timestamp).toLocaleTimeString()}</span></h3>
                                    <button onClick={() => setShowStatsModal(false)} className="text-gray-400 hover:text-white"><i className="fas fa-times"></i></button>
                                </div>
                                <div className="grid grid-cols-2 gap-4 mb-2">
                                    <div className="bg-black/40 p-3 rounded border border-white/5">
                                        <div className="text-[10px] text-gray-500 uppercase tracking-widest">Planned vs Actual</div>
                                        <div className="text-xl font-bold text-blue-400">{statsSession.duration}m <span className="text-gray-500 text-sm">/</span> {statsSession.actual_duration || statsSession.duration}m</div>
                                    </div>
                                    <div className="bg-black/40 p-3 rounded border border-white/5">
                                        <div className="text-[10px] text-gray-500 uppercase tracking-widest">Distractions</div>
                                        <div className="text-xl font-bold text-red-400">{statsSession.distractions}</div>
                                    </div>
                                </div>
                                
                                {statsSession.note ? (
                                    <div className="bg-blue-900/20 border border-blue-500/30 p-3 rounded mb-2 flex flex-col">
                                        <div className="flex justify-between items-center mb-1">
                                            <div className="text-[10px] text-blue-400 uppercase tracking-widest"><i className="fas fa-sticky-note mr-1"></i> Session Note</div>
                                            <button onClick={() => { setSessionNote(statsSession.note); setNoteSessionId(statsSession.id); setShowStatsModal(false); setShowNoteModal(true); }} className="text-[10px] text-blue-300 hover:text-white uppercase"><i className="fas fa-edit"></i> Edit</button>
                                        </div>
                                        <p className="text-sm text-gray-200 whitespace-pre-wrap">{statsSession.note}</p>
                                    </div>
                                ) : (
                                    <div className="flex justify-between items-center mt-2 border-t border-white/5 pt-2">
                                        <div className="text-xs text-gray-500 italic">No notes recorded for this session.</div>
                                        <button onClick={() => { setSessionNote(""); setNoteSessionId(statsSession.id); setShowStatsModal(false); setShowNoteModal(true); }} className="glass-button px-3 py-1 rounded text-[10px] font-bold tracking-widest uppercase text-blue-300"><i className="fas fa-plus"></i> Add Note</button>
                                    </div>
                                )}

                                {statsSession.timelapse_path && (
                                    <button onClick={() => { setShowStatsModal(false); backend.request(JSON.stringify({action: 'play_timelapse', path: statsSession.timelapse_path, duration: statsSession.duration, distractions: statsSession.distractions, data: statsSession})); }} className="glass-button bg-purple-600/30 hover:bg-purple-600 border-purple-500/50 text-white font-bold py-3 rounded mt-2 uppercase tracking-widest text-xs flex items-center justify-center">
                                        <i className="fas fa-video mr-2"></i> Play Session Timelapse
                                    </button>
                                )}
                            </div>
                        </div>
                    )}

                </div>
            );
        };
