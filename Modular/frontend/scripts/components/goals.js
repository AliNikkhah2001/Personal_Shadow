        const formatDate = (date) => date.toISOString().split('T')[0];

const parseBackendDate = (str) => {
    const match = str.match(/(\d+)\/(\d+)/);
    if (match) {
        const month = parseInt(match[1], 10) - 1;
        const day = parseInt(match[2], 10);
        const year = new Date().getFullYear();
        return formatDate(new Date(year, month, day));
    }
    const d = new Date(str);
    return isNaN(d.getTime()) ? str : formatDate(d);
};

const LifeArchitectureView = ({ goals, backend, refreshGoals, courseColors, studiedHours }) => {
            const [title, setTitle] = useState(""); const [target, setTarget] = useState(""); const [parent, setParent] = useState(""); const [deadline, setDeadline] = useState(new Date(new Date().getTime() + 7 * 24 * 60 * 60 * 1000).toISOString().slice(0, 16));

            const addGoal = () => { backend.request(JSON.stringify({action: 'manage_goal', sub: 'add', title: title, target_hours: target, parent_id: parent || null, deadline: deadline.replace('T', ' ')})).then(res => { refreshGoals(JSON.parse(res)); setTitle(""); setTarget(""); }); };
            const delGoal = (id) => { backend.request(JSON.stringify({action: 'manage_goal', sub: 'delete', id: id})).then(res => { refreshGoals(JSON.parse(res)); }); };

            const buildTree = (items) => {
                let map = {}, roots = []; items.forEach(g => { map[g.id] = {...g, children: []}; });
                items.forEach(g => { if (g.parent_id && map[g.parent_id]) map[g.parent_id].children.push(map[g.id]); else roots.push(map[g.id]); });
                return roots;
            };

            const renderNode = (node, depth=0) => {
                const nodeColor = (courseColors && courseColors[node.title]) ? courseColors[node.title] : '#ffffff';
                const logged = studiedHours && studiedHours[node.title] ? studiedHours[node.title] : 0;
                const pct = node.target_hours > 0 ? Math.min(100, Math.round((logged / node.target_hours) * 100)) : 0;

                return (
                    <div key={node.id} style={{ marginLeft: depth * 20 }} className="mb-2">
                        <div className="flex flex-col bg-black/20 p-3 rounded hover:bg-white/5 border transition" style={{ borderColor: `${nodeColor}40`, borderLeft: `4px solid ${nodeColor}` }}>
                            <div className="flex justify-between items-center">
                                <span>
                                    <strong style={{ color: nodeColor }}>{node.title}</strong>
                                    {node.target_hours > 0 && <span className="text-gray-400 ml-2 text-xs">Target: {node.target_hours}h</span>}
                                    {node.deadline && <span className="text-[10px] text-yellow-500 ml-2">DL: {node.deadline}</span>}
                                </span>
                                <div className="flex gap-3 items-center">
                                    {node.target_hours > 0 && <span className="text-xs font-bold" style={{color: nodeColor}}>{pct}%</span>}
                                    <button onClick={() => setParent(node.id)} className="text-xs text-blue-400 hover:text-blue-300">+ Sub</button>
                                    <i onClick={() => delGoal(node.id)} className="fas fa-trash text-red-500 cursor-pointer hover:scale-110"></i>
                                </div>
                            </div>
                            {node.target_hours > 0 && (
                                <div className="flex items-center gap-2 mt-2">
                                    <div className="flex-grow h-1.5 bg-black/50 rounded-full overflow-hidden">
                                        <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, backgroundColor: nodeColor }}></div>
                                    </div>
                                    <span className="text-[9px] text-gray-400 font-mono shrink-0">{logged.toFixed(1)}h / {node.target_hours}h</span>
                                </div>
                            )}
                        </div>
                        {node.children.map(child => renderNode(child, depth + 1))}
                    </div>
                );
            };
            return (
                <div className="h-full flex flex-col fade-in bg-gray-900/50">
                    <div className="flex justify-between items-center mb-6 shrink-0"><h2 className="text-2xl font-serif font-bold text-white tracking-widest uppercase drop-shadow-md">Life Architecture</h2></div>
                    <div className="flex gap-2 mb-4 shrink-0 glass-panel p-2 flex-wrap">
                        {parent && <span className="text-xs text-blue-400 self-center">Adding sub-goal... <i className="fas fa-times cursor-pointer text-red-400" onClick={()=>setParent("")}></i></span>}
                        <input type="text" placeholder="Goal Title..." className="glass-input px-3 py-1.5 rounded text-xs font-bold flex-grow min-w-[150px]" value={title} onChange={e=>setTitle(e.target.value)} />
                        <input type="number" placeholder="Target Hrs..." className="glass-input px-3 py-1.5 rounded text-xs font-bold w-24" value={target} onChange={e=>setTarget(e.target.value)} />
                        <input type="datetime-local" className="glass-input px-3 py-1.5 rounded text-xs font-bold" value={deadline} onChange={e=>setDeadline(e.target.value)} />
                        <button onClick={addGoal} className="glass-button px-4 py-1.5 rounded text-[11px] font-bold text-blue-300 uppercase">+ Add Goal</button>
                    </div>
                    <div className="glass-panel p-6 flex-grow overflow-y-auto text-sm text-gray-300">
                        {goals && goals.length > 0 ? buildTree(goals).map(root => renderNode(root)) : <p>No goals defined.</p>}
                    </div>
                </div>
            );
};

const HabitMatrixView = ({ habits, backend, refreshHabits, habitLogs, setHabitLogs }) => {
            const [newName, setNewName] = useState(""); const [newType, setNewType] = useState("Positive"); const [editingId, setEditingId] = useState(null);
            const days = []; const dayLabels = []; const today = new Date();
            for (let i = 6; i >= 0; i--) { 
                const date = new Date(today); 
                date.setDate(date.getDate() - i); 
                days.push(formatDate(date));
                dayLabels.push(date.toLocaleDateString('en-US', { weekday: 'short', month: 'numeric', day: 'numeric' }));
            }

            const normalizedHabitLogs = React.useMemo(() => {
                return (habitLogs || []).map(log => ({...log, normDate: parseBackendDate(log.date)}));
            }, [habitLogs]);

            const calculateStreak = (habitId) => {
                if (!normalizedHabitLogs.length) return 0;
                const logs = normalizedHabitLogs.filter(log => log.habit_id === habitId).sort((a, b) => a.normDate.localeCompare(b.normDate));
                if (!logs.length) return 0;
                let streak = 0;
                for (let i = 0; i < days.length; i++) {
                    const log = logs.find(l => l.normDate === days[i]);
                    if (log && log.status === 1) streak++;
                    else if (i > 0 && (!log || log.status === 0)) break;
                }
                return streak;
            };

            const handleAction = (sub, id, name, type) => {
                backend.request(JSON.stringify({action: 'manage_habit', sub: sub, id: id, name: name || newName, type: type || newType})).then(res => {
                    const data = JSON.parse(res); if (data.habits) refreshHabits(data.habits); if (data.habit_logs) setHabitLogs(data.habit_logs); setNewName(""); setEditingId(null);
                });
            };

            const toggleLog = (hid, dateIdx) => {
                const dateStr = days[dateIdx];
                const logExists = normalizedHabitLogs.some(log => log.habit_id === hid && log.normDate === dateStr);
                const currentStatus = logExists ? 1 : 0; const newStatus = currentStatus === 1 ? 0 : 1;
                backend.request(JSON.stringify({action: 'manage_habit', sub: 'toggle_log', habit_id: hid, date: dateStr, status: newStatus})).then(res => {
                    const data = JSON.parse(res); if (data.habits) refreshHabits(data.habits); if (data.habit_logs) setHabitLogs(data.habit_logs);
                });
            };

            return (
                <div className="h-full flex flex-col fade-in bg-gray-900/50">
                    <div className="flex justify-between items-center mb-6 shrink-0"><h2 className="text-2xl font-serif font-bold text-white tracking-widest uppercase drop-shadow-md">Habit Matrix</h2><span className="text-xs text-gray-400 font-mono">7-DAY ROLLING</span></div>
                    <div className="flex gap-2 mb-4 shrink-0 glass-panel p-2">
                        <select className="glass-input px-3 py-1.5 rounded text-xs font-bold" value={newType} onChange={e => setNewType(e.target.value)}><option value="Positive">Positive (+)</option><option value="Negative">Negative (-)</option></select>
                        <input type="text" placeholder="New Habit Name..." className="glass-input px-3 py-1.5 rounded text-xs font-bold flex-grow" value={newName} onChange={e => setNewName(e.target.value)} />
                        <button onClick={() => handleAction('add')} className="glass-button px-4 py-1.5 rounded text-[11px] font-bold text-blue-300 uppercase">+ Add Habit</button>
                    </div>
                    <div className="glass-panel p-1 rounded-xl overflow-x-auto">
                        <table className="w-full text-left border-collapse min-w-[600px]">
                            <thead>
                                <tr className="border-b border-white/10 bg-black/40">
                                    <th className="p-4 text-xs font-bold text-gray-400 uppercase w-12 text-center">#</th>
                                    <th className="p-4 text-xs font-bold text-gray-400 uppercase">Habit</th>
                                    <th className="p-4 text-xs font-bold text-gray-400 uppercase text-center">Streak</th>
                                    {dayLabels.map((day, idx) => (<th key={idx} className="p-4 text-[10px] font-bold text-gray-400 uppercase text-center whitespace-nowrap">{day}</th>))}
                                    <th className="p-4 text-[10px] font-bold text-gray-400 uppercase text-center">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {habits && habits.map((h, idx) => {
                                    const isPos = h.type === 'Positive'; const streak = calculateStreak(h.id);
                                    return (
                                        <tr key={h.id} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                                            <td className="p-4 text-xs font-mono text-gray-500 text-center">{idx + 1}</td>
                                            <td className={`p-4 text-sm font-bold tracking-wide ${isPos ? 'text-green-400' : 'text-red-400'}`}>
                                                {editingId === h.id ? (<input type="text" className="glass-input px-2 py-1 rounded text-xs w-full" defaultValue={h.name} onBlur={(e) => handleAction('edit', h.id, e.target.value, h.type)} autoFocus />) : (<span>{isPos ? '+' : '-'} {h.name}</span>)}
                                            </td>
                                            <td className="p-4 text-xs font-mono text-blue-400 text-center font-bold">{streak > 0 ? `${streak}d` : '\u2014'}</td>
                                            {days.map((day, dIdx) => (
                                                <td key={dIdx} className="p-4 text-center"><input type="checkbox" onChange={() => toggleLog(h.id, dIdx)} checked={normalizedHabitLogs.some(log => log.habit_id === h.id && log.normDate === day && log.status === 1)} className={`w-5 h-5 rounded bg-black/40 border border-white/20 checked:border-transparent appearance-none cursor-pointer transition-all flex items-center justify-center checked:after:content-['\\2713'] checked:after:text-white checked:after:text-sm ${isPos ? 'checked:bg-green-500' : 'checked:bg-red-500'}`} /></td>
                                            ))}
                                            <td className="p-4 text-center"><i onClick={() => setEditingId(h.id)} className="fas fa-edit text-yellow-400 cursor-pointer mx-2 hover:scale-110"></i><i onClick={() => handleAction('delete', h.id)} className="fas fa-trash text-red-400 cursor-pointer mx-2 hover:scale-110"></i></td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                </div>
            );
        };

        const DaySummaryView = ({ metrics }) => {
            const tdyStudy = metrics ? metrics.tdy_study : 0; const ydyStudy = metrics ? metrics.ydy_study : 0; const tdyDist = metrics ? metrics.tdy_dist : 0; const ydyDist = metrics ? metrics.ydy_dist : 0;
            const studyDiff = tdyStudy - ydyStudy; const distDiff = tdyDist - ydyDist;
            return (
                <div className="flex flex-col h-full fade-in bg-gray-900/50">
                    <div className="flex justify-between items-center mb-6 shrink-0"><h2 className="text-2xl font-serif font-bold text-white tracking-widest uppercase drop-shadow-md">Day Summary</h2></div>
                    <div className="flex flex-col gap-4 overflow-y-auto">
                        <div className="glass-panel p-8 text-center border-t-2 border-t-blue-500/50">
                            <h3 className="text-gray-400 font-bold uppercase tracking-widest text-xs mb-2">Time Studied Today</h3>
                            <div className="text-5xl font-mono text-white mb-2">{Math.floor(tdyStudy/60)}h {Math.floor(tdyStudy%60)}m</div>
                            <span className={`text-sm font-semibold ${studyDiff >= 0 ? 'text-green-400' : 'text-red-400'}`}><i className={`fas fa-arrow-${studyDiff >= 0 ? 'up' : 'down'} mr-1`}></i> {Math.abs(studyDiff).toFixed(1)}m compared to yesterday</span>
                        </div>
                        <div className="glass-panel p-8 text-center border-t-2 border-t-red-500/50">
                            <h3 className="text-gray-400 font-bold uppercase tracking-widest text-xs mb-2">Total Distractions</h3>
                            <div className="text-5xl font-mono text-white mb-2">{tdyDist}</div>
                            <span className={`text-sm font-semibold ${distDiff <= 0 ? 'text-green-400' : 'text-red-400'}`}><i className={`fas fa-arrow-${distDiff >= 0 ? 'up' : 'down'} mr-1`}></i> {Math.abs(distDiff)} compared to yesterday</span>
                        </div>
                    </div>
                </div>
            );
        };
