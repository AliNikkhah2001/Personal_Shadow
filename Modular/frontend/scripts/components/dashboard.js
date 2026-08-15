        const NativeGitHubMatrix = ({ heatmap }) => {
            const matrix = heatmap && heatmap.length > 0 ? heatmap : Array.from({ length: 28 }, () => Array(7).fill(0));
            const getColor = (val) => {
                if (val === 0) return 'bg-[#161b22]/50 border border-white/5';
                if (val === 1) return 'bg-[#0e4429] border border-[#0e4429]';
                if (val === 2) return 'bg-[#006d32] border border-[#006d32]';
                if (val === 3) return 'bg-[#26a641] border border-[#26a641]';
                return 'bg-[#39d353] border border-[#39d353] shadow-[0_0_8px_rgba(57,211,83,0.4)]';
            };
            return (
                <div className="p-6 h-full flex flex-col">
                    <h3 className="text-gray-300 text-sm font-semibold tracking-wide mb-4 border-b border-white/10 pb-2">Contribution Matrix</h3>
                    <div className="flex-grow flex items-center justify-center overflow-x-auto">
                        <div className="flex gap-1.5 pb-2">
                            <div className="flex flex-col gap-1.5 pr-2 text-[9px] text-gray-500 font-bold">
                                {['Mon', '', 'Wed', '', 'Fri', '', 'Sun'].map((day, i) => (
                                    <div key={i} className="h-3.5 sm:h-4 flex items-center justify-end w-4">{day}</div>
                                ))}
                            </div>
                            {matrix.map((week, wIdx) => (
                                <div key={wIdx} className="flex flex-col gap-1.5">
                                    {week.map((day, dIdx) => (
                                        <div key={`${wIdx}-${dIdx}`} className={`w-3.5 h-3.5 sm:w-4 sm:h-4 rounded-[3px] ${getColor(day)} transition-all hover:ring-1 hover:ring-white cursor-pointer`}></div>
                                    ))}
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            );
        };

        const DualCalendar = ({ backend, refreshGoals, goals }) => {
            const [currentDate, setCurrentDate] = useState(new Date());
            const [showModal, setShowModal] = useState(false);
            const [selectedDate, setSelectedDate] = useState(null);
            const [gTitle, setGTitle] = useState("");
            const [gCat, setGCat] = useState("Goal");
            const [gTgt, setGTgt] = useState("");

            const monthNames = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
            const year = currentDate.getFullYear(); const month = currentDate.getMonth();
            const daysInMonth = new Date(year, month + 1, 0).getDate();
            const firstDayOfMonth = new Date(year, month, 1).getDay();
            const [jYear, jMonth, jDay] = g2j(year, month + 1, 1);

            const handleDayClick = (i) => {
                const d = new Date(year, month, i);
                const offset = new Date(d.getTime() - (d.getTimezoneOffset() * 60000));
                setSelectedDate(offset.toISOString().slice(0, 16).replace('T', ' '));
                setShowModal(true);
            };

            const handleSaveGoal = () => {
                backend.request(JSON.stringify({action: 'manage_goal', sub: 'add', title: gTitle || "New Objective", target_hours: gTgt || 0, category: gCat || "Goal", deadline: selectedDate || new Date().toISOString().slice(0, 16).replace('T', ' '), parent_id: null})).then(res => {
                    const data = JSON.parse(res);
                    if (data.goals && typeof refreshGoals === 'function') refreshGoals(data);
                    setShowModal(false); setGTitle(""); setGTgt("");
                });
            };

            const renderDays = () => {
                let days = [];
                for (let i = 0; i < firstDayOfMonth; i++) days.push(<div key={`empty-${i}`} className="min-h-[70px]"></div>);
                for (let i = 1; i <= daysInMonth; i++) {
                    const dateObj = new Date(year, month, i);
                    const isToday = new Date().toDateString() === dateObj.toDateString();
                    const [jy, jm, jd] = g2j(year, month + 1, i);
                    const hasGoal = goals && goals.some(g => {
                        if (!g.deadline) return false;
                        return new Date(g.deadline).toDateString() === dateObj.toDateString();
                    });
                    days.push(
                        <div key={i} onClick={() => handleDayClick(i)} className={`relative p-1.5 flex flex-col min-h-[70px] border border-white/5 rounded-lg ${isToday ? 'bg-blue-600/30 border-blue-400 shadow-[0_0_15px_rgba(59,130,246,0.5)]' : 'bg-black/20 hover:bg-white/10'} transition-all overflow-hidden cursor-pointer group`}>
                            <div className="flex justify-between items-start w-full">
                                <span className={`text-sm font-bold ${isToday ? 'text-white' : 'text-gray-200'}`}>{i}</span>
                                <span className="text-[10px] font-bold text-yellow-500 font-[Tahoma]">{toFarsi(jd)}</span>
                            </div>
                            {hasGoal && <div className="absolute bottom-1 right-1 flex items-center gap-1"><span className="text-[8px] text-green-400"><i className="fas fa-flag"></i></span></div>}
                        </div>
                    );
                }
                return days;
            };

            return (
                <div className="p-4 h-full flex flex-col w-full relative">
                    <div className="flex justify-between items-center mb-4 bg-black/40 p-2 rounded-xl border border-white/10 backdrop-blur-md">
                        <button onClick={() => setCurrentDate(new Date(year, month - 1, 1))} className="w-6 h-6 hover:bg-white/10 rounded-full transition text-gray-300"><i className="fas fa-chevron-left text-xs"></i></button>
                        <div className="flex flex-col items-center">
                            <h2 className="text-sm font-bold text-white tracking-widest uppercase">{monthNames[month]} {year}</h2>
                            <h3 className="text-[10px] font-bold text-yellow-500 font-[Tahoma] tracking-wider">{jalaliMonths[jMonth-1]} {toFarsi(jYear)}</h3>
                        </div>
                        <button onClick={() => setCurrentDate(new Date(year, month + 1, 1))} className="w-6 h-6 hover:bg-white/10 rounded-full transition text-gray-300"><i className="fas fa-chevron-right text-xs"></i></button>
                    </div>
                    <div className="calendar-grid mb-1">
                        {['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'].map((day, i) => (<div key={day} className={`text-center text-[10px] font-bold uppercase ${(i===0||i===6)?'text-red-400':'text-gray-400'}`}>{day}</div>))}
                    </div>
                    <div className="calendar-grid flex-grow overflow-y-auto pr-1">{renderDays()}</div>

                    {showModal && (
                        <div className="absolute inset-0 bg-black/90 z-50 flex items-center justify-center rounded-xl p-4 backdrop-blur-md">
                            <div className="w-full max-w-sm flex flex-col gap-3">
                                <h3 className="text-white font-bold text-lg mb-2">Set Goal for {selectedDate.split(' ')[0]}</h3>
                                <input type="text" placeholder="Goal Title..." className="glass-input p-2 rounded text-sm w-full" value={gTitle} onChange={e=>setGTitle(e.target.value)} />
                                <select className="glass-input p-2 rounded text-sm w-full" value={gCat} onChange={e=>setGCat(e.target.value)}><option>Career</option><option>Health</option><option>Education</option><option>Finance</option><option>Project</option></select>
                                <input type="number" placeholder="Target Hours" className="glass-input p-2 rounded text-sm w-full" value={gTgt} onChange={e=>setGTgt(e.target.value)} />
                                <div className="flex gap-2 mt-4">
                                    <button onClick={handleSaveGoal} className="glass-button bg-blue-600/50 hover:bg-blue-600 text-white font-bold py-2 rounded flex-grow">Save Goal</button>
                                    <button onClick={() => setShowModal(false)} className="glass-button bg-red-600/30 hover:bg-red-600 text-white font-bold py-2 rounded flex-grow">Cancel</button>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            );
        };

        const GlobalTargets = ({ metrics }) => {
            const totalHours = metrics?.global_study_hours || 0;
            const targetHours = metrics?.global_target_hours || 50;
            const progress = targetHours > 0 ? Math.min((totalHours / targetHours) * 100, 100) : 0;
            return (
                <div className="p-4 h-full flex flex-col items-center justify-center text-center w-full">
                    <h3 className="text-gray-300 font-bold uppercase tracking-widest text-[11px] mb-6">Global Progress</h3>
                    <div className="w-32 h-32 sm:w-40 sm:h-40 rounded-full border-[8px] border-black/40 relative flex items-center justify-center shadow-inner">
                        <div className="absolute inset-0 border-[8px] border-blue-500 rounded-full border-t-transparent border-r-transparent opacity-80 shadow-[0_0_15px_rgba(59,130,246,0.6)]" style={{ transform: `rotate(${-45 + (progress / 100) * 360}deg)` }}></div>
                        <div className="flex flex-col items-center z-10">
                            <span className="text-3xl font-bold text-white drop-shadow-lg">{Math.round(progress)}%</span>
                            <span className="text-[10px] text-gray-400 mt-1 font-mono tracking-wider">{totalHours.toFixed(1)} / {targetHours.toFixed(1)} Hrs</span>
                        </div>
                    </div>
                </div>
            );
        };

        const MetricsWidget = ({ metrics }) => {
            const hVol = metrics && metrics.hourly_vol ? metrics.hourly_vol : [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
            const maxVol = Math.max(...hVol, 1);
            return (
                <div className="p-4 h-full flex flex-col w-full">
                    <h3 className="text-gray-300 font-bold uppercase tracking-widest text-sm border-b border-white/10 pb-2 mb-4 w-full text-left">Study Volume by Hour (08:00 - 20:00)</h3>
                    <div className="flex-grow flex items-end justify-between gap-1 mt-auto">
                        {hVol.map((h, i) => (
                            <div key={i} className="w-full bg-blue-500/60 hover:bg-blue-400 rounded-t-sm transition-all relative group" style={{height: `${(h/maxVol)*100}%`}}>
                                <span className="absolute -top-6 left-1/2 -translate-x-1/2 bg-black text-white text-[10px] px-1 rounded opacity-0 group-hover:opacity-100 transition">{h.toFixed(1)}m</span>
                            </div>
                        ))}
                    </div>
                    <div className="flex justify-between text-[8px] text-gray-500 mt-2 font-mono"><span>08:00</span><span>20:00</span></div>
                </div>
            );
        };

        const DashboardHabitWidget = ({ habits, habitLogs }) => {
            return (
                <div className="p-4 h-full flex flex-col w-full overflow-y-auto">
                    <h3 className="text-gray-300 font-bold uppercase tracking-widest text-sm border-b border-white/10 pb-2 mb-4">Habit Streaks</h3>
                    <div className="flex flex-col gap-2">
                        {habits && habits.map(h => {
                            const isPos = h.type === 'Positive';
                            return (
                                <div key={h.id} className="flex justify-between items-center p-2 bg-white/5 rounded border border-white/5">
                                    <span className={`text-xs font-bold ${isPos ? 'text-green-400' : 'text-red-400'}`}>{h.name}</span>
                                    <span className="text-[10px] font-mono text-gray-400">Streak: Active</span>
                                </div>
                            );
                        })}
                    </div>
                </div>
            );
        };

        const DashboardArchitectureWidget = ({ goals, studiedHours, courseColors }) => {
            const sortedGoals = goals ? [...goals].filter(g => g.deadline).sort((a,b) => new Date(a.deadline) - new Date(b.deadline)) : [];
            const now = new Date();
            const upcomingGoals = sortedGoals.filter(g => new Date(g.deadline) >= now);
            return (
                <div className="p-4 h-full flex flex-col w-full overflow-y-auto">
                    <h3 className="text-gray-300 font-bold uppercase tracking-widest text-sm border-b border-white/10 pb-2 mb-4">Upcoming Deadlines & Goals <span className="text-[10px] text-gray-500 ml-2">({upcomingGoals.length})</span></h3>
                    {sortedGoals.length === 0 ? (
                        <div className="text-center text-gray-500 py-8"><i className="fas fa-calendar-plus text-3xl mb-2 opacity-50"></i><p className="text-xs">No goals set</p></div>
                    ) : (
                        upcomingGoals.slice(0, 5).map(g => {
                            const daysUntil = Math.ceil((new Date(g.deadline) - now) / (1000 * 60 * 60 * 24));
                            const logged = studiedHours && studiedHours[g.title] ? studiedHours[g.title] : 0;
                            const rem = Math.max(0, (g.target_hours || 0) - logged);
                            const rootColor = (courseColors && courseColors[g.title]) ? courseColors[g.title] : '#3b82f6';
                            const pct = g.target_hours > 0 ? Math.min(100, Math.round((logged / g.target_hours) * 100)) : 0;

                            return (
                                <div key={g.id} className="flex flex-col p-3 bg-white/5 rounded border border-white/5 hover:bg-white/10 transition mb-2" style={{ borderLeft: `3px solid ${rootColor}` }}>
                                    <div className="flex justify-between items-center mb-1">
                                        <span className="text-xs font-bold text-gray-200" style={{ color: rootColor }}>{g.title}</span>
                                        <div className="flex items-center gap-2">
                                            <span className={`text-[10px] font-bold ${daysUntil <= 1 ? 'text-red-400' : 'text-yellow-400'}`}>{daysUntil <= 0 ? 'Today!' : `${daysUntil}d left`}</span>
                                        </div>
                                    </div>
                                    {g.target_hours > 0 && (
                                        <div className="flex flex-col gap-1 mt-1">
                                            <div className="flex justify-between items-center">
                                                <span className="text-[9px] text-gray-400 font-mono">{logged.toFixed(1)}h / {g.target_hours}h</span>
                                                <span className="text-[9px] font-bold" style={{color: rootColor}}>{pct}%</span>
                                            </div>
                                            <div className="flex-grow h-1.5 bg-black/50 rounded-full overflow-hidden">
                                                <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, backgroundColor: rootColor }}></div>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            );
                        })
                    )}
                </div>
            );
        };

        const GoalProgressWidget = ({ goals, studiedHours, courseColors }) => {
            const chartRef = useRef(null);
            useEffect(() => {
                if (!chartRef.current || !window.Chart || !goals || goals.length === 0) return;
                const ctx = chartRef.current.getContext('2d');
                const goalData = goals.filter(g => g.target_hours > 0).slice(0, 8);
                if (goalData.length === 0) return;
                const labels = goalData.map(g => g.title.length > 15 ? g.title.substring(0, 15) + '...' : g.title);
                const targetData = goalData.map(g => g.target_hours);
                const actualData = goalData.map(g => studiedHours && studiedHours[g.title] ? Math.min(studiedHours[g.title], g.target_hours) : 0);
                const pctData = goalData.map(g => {
                    const logged = studiedHours && studiedHours[g.title] ? studiedHours[g.title] : 0;
                    return g.target_hours > 0 ? Math.round((logged / g.target_hours) * 100) : 0;
                });
                const colors = goalData.map(g => (courseColors && courseColors[g.title]) ? courseColors[g.title] : '#3b82f6');
                let chartInstance = new window.Chart(ctx, {
                    type: 'bar',
                    data: {
                        labels,
                        datasets: [
                            { label: 'Target Hours', data: targetData, backgroundColor: colors.map(c => c + '33'), borderColor: colors, borderWidth: 2 },
                            { label: 'Logged Hours', data: actualData, backgroundColor: colors.map(c => c + 'CC'), borderColor: colors, borderWidth: 1 }
                        ]
                    },
                    options: {
                        responsive: true, maintainAspectRatio: false,
                        scales: {
                            y: { ticks: { color: 'gray', font: {size: 9} }, grid: {color: 'rgba(255,255,255,0.05)'} },
                            x: { ticks: { color: 'gray', font: {size: 9}, maxRotation: 45 }, grid: {display: false} }
                        },
                        plugins: {
                            legend: { labels: { color: 'white', boxWidth: 12, font: {size: 10} } },
                            tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${ctx.raw}h`, afterBody: (items) => { const idx = items[0].dataIndex; return `Progress: ${pctData[idx]}%`; } } }
                        }
                    }
                });
                return () => chartInstance.destroy();
            }, [goals, studiedHours, courseColors]);

            return (
                <div className="p-4 h-full flex flex-col w-full">
                    <h3 className="text-gray-300 font-bold uppercase tracking-widest text-sm border-b border-white/10 pb-2 mb-4">Goal Progress Overview</h3>
                    <div className="flex-grow relative min-h-[180px]"><canvas ref={chartRef}></canvas></div>
                </div>
            );
        };

        const GoalTimeChartWidget = ({ backend, goals, studiedHours }) => {
            const chartRef = useRef(null);
            const [timeData, setTimeData] = useState(null);

            useEffect(() => {
                if (!backend) return;
                backend.request(JSON.stringify({action: 'get_history_data'})).then(res => {
                    const data = JSON.parse(res);
                    setTimeData(data.history_sessions || []);
                });
            }, [backend]);

            useEffect(() => {
                if (!chartRef.current || !window.Chart || !timeData || !goals) return;
                const ctx = chartRef.current.getContext('2d');
                const last7 = [];
                for (let i = 6; i >= 0; i--) {
                    const d = new Date(); d.setDate(d.getDate() - i);
                    last7.push(d.toISOString().split('T')[0]);
                }
                const topGoals = goals.filter(g => g.target_hours > 0).slice(0, 4);
                if (topGoals.length === 0) return;
                const colors = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444'];
                const datasets = topGoals.map((g, idx) => {
                    const dailyMins = last7.map(dateStr => {
                        const sessions = timeData.filter(s => s.course === g.title && s.timestamp.split('T')[0] === dateStr && s.type === 'Work');
                        return sessions.reduce((sum, s) => sum + (s.actual_duration || s.duration || 0), 0) / 60;
                    });
                    return {
                        label: g.title.length > 20 ? g.title.substring(0, 20) + '...' : g.title,
                        data: dailyMins,
                        borderColor: colors[idx % colors.length],
                        backgroundColor: colors[idx % colors.length] + '33',
                        tension: 0.3,
                        fill: false,
                        pointRadius: 4,
                        pointHoverRadius: 6
                    };
                });
                const dayLabels = last7.map(d => {
                    const date = new Date(d + 'T12:00:00');
                    return date.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
                });
                let chartInstance = new window.Chart(ctx, {
                    type: 'line',
                    data: { labels: dayLabels, datasets },
                    options: {
                        responsive: true, maintainAspectRatio: false,
                        scales: {
                            y: { title: { display: true, text: 'Hours', color: 'gray', font: {size: 10} }, ticks: { color: 'gray', font: {size: 9} }, grid: {color: 'rgba(255,255,255,0.05)'} },
                            x: { ticks: { color: 'gray', font: {size: 9} }, grid: {display: false} }
                        },
                        plugins: {
                            legend: { labels: { color: 'white', boxWidth: 12, font: {size: 10} } },
                            tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${ctx.raw.toFixed(1)}h` } }
                        }
                    }
                });
                return () => chartInstance.destroy();
            }, [timeData, goals]);

            return (
                <div className="p-4 h-full flex flex-col w-full">
                    <h3 className="text-gray-300 font-bold uppercase tracking-widest text-sm border-b border-white/10 pb-2 mb-4">Time Worked Per Goal (Last 7 Days)</h3>
                    <div className="flex-grow relative min-h-[180px]"><canvas ref={chartRef}></canvas></div>
                </div>
            );
        };

        const DailySummaryWidget = ({ metrics, todaySessions }) => {
            const totalMins = todaySessions ? todaySessions.reduce((s, sess) => s + (sess.actual_duration || sess.duration || 0), 0) : 0;
            const totalDistr = todaySessions ? todaySessions.reduce((s, sess) => s + (sess.distractions || 0), 0) : 0;
            const workSessions = todaySessions ? todaySessions.filter(s => s.type === 'Work').length : 0;
            return (
                <div className="p-4 h-full flex flex-col w-full">
                    <h3 className="text-gray-300 font-bold uppercase tracking-widest text-sm border-b border-white/10 pb-2 mb-4">Today's Summary</h3>
                    <div className="grid grid-cols-3 gap-3 flex-grow">
                        <div className="bg-black/40 rounded-lg p-3 flex flex-col items-center justify-center border border-white/5">
                            <i className="fas fa-clock text-blue-400 text-lg mb-2"></i>
                            <span className="text-2xl font-bold text-white">{Math.floor(totalMins/60)}h {Math.floor(totalMins%60)}m</span>
                            <span className="text-[9px] text-gray-500 uppercase tracking-widest mt-1">Total Time</span>
                        </div>
                        <div className="bg-black/40 rounded-lg p-3 flex flex-col items-center justify-center border border-white/5">
                            <i className="fas fa-bullseye text-green-400 text-lg mb-2"></i>
                            <span className="text-2xl font-bold text-white">{workSessions}</span>
                            <span className="text-[9px] text-gray-500 uppercase tracking-widest mt-1">Sessions</span>
                        </div>
                        <div className="bg-black/40 rounded-lg p-3 flex flex-col items-center justify-center border border-white/5">
                            <i className="fas fa-exclamation-triangle text-red-400 text-lg mb-2"></i>
                            <span className="text-2xl font-bold text-white">{totalDistr}</span>
                            <span className="text-[9px] text-gray-500 uppercase tracking-widest mt-1">Distractions</span>
                        </div>
                    </div>
                </div>
            );
        };

        const RecentActivityWidget = ({ activityLogs }) => {
            return (
                <div className="p-4 h-full flex flex-col w-full overflow-y-auto">
                    <h3 className="text-gray-300 font-bold uppercase tracking-widest text-sm border-b border-white/10 pb-2 mb-4">Recent Activity</h3>
                    <div className="flex flex-col gap-2">
                        {activityLogs && activityLogs.length > 0 ? activityLogs.slice(0, 8).map((log, i) => (
                            <div key={i} className="flex items-start gap-2 p-2 bg-black/30 rounded border border-white/5">
                                <div className="w-1.5 h-1.5 rounded-full bg-blue-400 mt-1.5 shrink-0"></div>
                                <div className="flex flex-col">
                                    <span className="text-[10px] text-gray-400 font-mono">{new Date(log.timestamp).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}</span>
                                    <span className="text-xs text-gray-300">{log.description}</span>
                                </div>
                            </div>
                        )) : <div className="text-xs text-gray-500 italic text-center py-4">No recent activity</div>}
                    </div>
                </div>
            );
        };

        const CorrelationChartsWidget = ({ backend, correlations, insights }) => {
            const chartRef = useRef(null);
            const [error, setError] = useState(null);

            useEffect(() => {
                if (!chartRef.current || !window.Chart || !correlations) return;
                try {
                    const ctx = chartRef.current.getContext('2d');
                    const corrData = Object.entries(correlations).filter(([k, v]) => !isNaN(v) && v !== null);
                    if (corrData.length === 0) { setError('No correlation data available'); return; }
                    const labels = corrData.map(([k]) => k.replace(/_/g, ' ').replace(/ vs /g, ' vs ').replace(/([A-Z])/g, ' $1').trim());
                    const values = corrData.map(([, v]) => Math.round(v * 100) / 100);
                    const colors = values.map(v => v > 0.3 ? '#22c55e' : v < -0.3 ? '#ef4444' : v > 0 ? '#84cc16' : v < 0 ? '#f97316' : '#64748b');
                    let chartInstance = new window.Chart(ctx, {
                        type: 'bar',
                        data: { labels, datasets: [{ label: 'Correlation Coefficient', data: values, backgroundColor: colors, borderColor: colors.map(c => c + 'CC'), borderWidth: 1 }] },
                        options: {
                            indexAxis: 'y', responsive: true, maintainAspectRatio: false,
                            scales: { x: { min: -1, max: 1, ticks: { color: 'gray', stepSize: 0.5 }, grid: { color: 'rgba(255,255,255,0.1)' } }, y: { ticks: { color: 'white', font: { size: 10 } } } },
                            plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx) => { const v = ctx.raw; let strength = Math.abs(v) > 0.7 ? 'Strong' : Math.abs(v) > 0.3 ? 'Moderate' : 'Weak'; return `r = ${v.toFixed(2)} (${strength})`; } } } }
                        }
                    });
                    return () => chartInstance.destroy();
                } catch (e) { setError(e.message); }
            }, [correlations]);

            if (error) return <div className="p-4 h-full flex flex-col w-full"><h3 className="text-gray-300 font-bold uppercase tracking-widest text-sm border-b border-white/10 pb-2 mb-4">Behavioral Correlations</h3><div className="flex-grow flex items-center justify-center text-red-400 text-sm">Chart unavailable: {error}</div></div>;

            return (
                <div className="p-4 h-full flex flex-col w-full">
                    <h3 className="text-gray-300 font-bold uppercase tracking-widest text-sm border-b border-white/10 pb-2 mb-4">Behavioral Correlations</h3>
                    <div className="flex-grow relative min-h-[200px]"><canvas ref={chartRef}></canvas></div>
                    {insights && insights.length > 0 && (
                        <div className="mt-4 flex flex-col gap-2 max-h-40 overflow-y-auto">
                            {insights.map((insight, i) => (
                                <div key={i} className={`text-xs p-2 rounded border-l-4 ${insight.type === 'positive' ? 'bg-green-900/30 border-green-500' : insight.type === 'warning' ? 'bg-yellow-900/30 border-yellow-500' : insight.type === 'negative' ? 'bg-red-900/30 border-red-500' : 'bg-blue-900/30 border-blue-500'}`}>
                                    <div className="font-bold text-white mb-1">{insight.title}</div>
                                    <div className="text-gray-300">{insight.description}</div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            );
        };

        const DashboardHealthWidget = ({ healthProfile, healthLogs }) => {
            const chartRef = useRef(null);
            useEffect(() => {
                if (chartRef.current && window.Chart) {
                    const ctx = chartRef.current.getContext('2d');
                    const dailyStats = {};
                    (healthLogs || []).forEach(l => {
                        if (!dailyStats[l.date]) dailyStats[l.date] = { intake: 0, burn: 0 };
                        if (l.type === 'food') dailyStats[l.date].intake += (parseFloat(l.data.kcal) || 0);
                        if (l.type === 'exercise') dailyStats[l.date].burn += (parseFloat(l.data.kcal_burn) || 0);
                    });
                    const sortedDates = Object.keys(dailyStats).sort();
                    const bmr = (healthProfile && healthProfile.weight) ? ((10 * healthProfile.weight) + (6.25 * healthProfile.height) - (5 * healthProfile.age) + (healthProfile.gender === 'Male' ? 5 : -161)) : 0;
                    const tdee = bmr * (healthProfile?.activity || 1.2);
                    const deficits = sortedDates.map(d => (tdee + dailyStats[d].burn) - dailyStats[d].intake);
                    let projWeight = healthProfile?.weight || 70;
                    const projWeights = sortedDates.map((d, i) => { projWeight -= (deficits[i] / 7700); return projWeight; });
                    let chartInstance = new window.Chart(ctx, {
                        type: 'line',
                        data: {
                            labels: sortedDates.length > 0 ? sortedDates : [new Date().toISOString().slice(0, 10)],
                            datasets: [{ label: 'Proj. Weight (kg)', data: projWeights.length > 0 ? projWeights : [healthProfile?.weight || 70], borderColor: '#3b82f6', tension: 0.3, yAxisID: 'y' }, { type: 'bar', label: 'Deficit (kcal)', data: deficits.length > 0 ? deficits : [0], backgroundColor: '#22c55e', yAxisID: 'y1' }]
                        },
                        options: { responsive: true, maintainAspectRatio: false, scales: { y: { type: 'linear', position: 'left', ticks: {color: 'gray'} }, y1: { type: 'linear', position: 'right', ticks: {color: 'gray'}, grid: {drawOnChartArea: false} }, x: { ticks: {color: 'gray'} } }, plugins: { legend: { labels: {color: 'white', boxWidth: 12, font: {size: 10}} } } }
                    });
                    return () => chartInstance.destroy();
                }
            }, [healthLogs, healthProfile]);
            return (
                <div className="p-4 h-full flex flex-col w-full relative">
                    <h3 className="text-gray-300 font-bold uppercase tracking-widest text-sm border-b border-white/10 pb-2 mb-4">Health Trends</h3>
                    <div className="flex-grow relative min-h-[150px]"><canvas ref={chartRef}></canvas></div>
                </div>
            );
        };


        const DashboardView = ({ layout, setLayout, goals, isEditingLayout, setIsEditingLayout, clockFeed, heatmap, habits, habitLogs, metrics, backend, refreshGoals, healthProfile, healthLogs, studiedHours, courseColors, dailyMetrics, setDailyMetrics, correlations, insights, activityLogs, todaySessions }) => {
            const SIZE_OPTIONS = ['quarter', 'third', 'half', 'full'];
            const SIZE_CLASSES = { quarter: 'w-full md:w-1/4', third: 'w-full md:w-1/3', half: 'w-full md:w-1/2', full: 'w-full' };

            const toggleWidgetVisibility = (id) => setLayout(prev => prev.map(w => w.id === id ? { ...w, visible: !w.visible } : w));
            const cycleWidgetSize = (id) => setLayout(prev => prev.map(w => {
                if (w.id !== id) return w;
                const idx = SIZE_OPTIONS.indexOf(w.size);
                const next = SIZE_OPTIONS[(idx + 1) % SIZE_OPTIONS.length];
                return { ...w, size: next };
            }));
            const moveWidget = (id, dir) => {
                setLayout(prev => {
                    const sorted = [...prev].sort((a,b) => a.order - b.order);
                    const idx = sorted.findIndex(w => w.id === id);
                    if (idx < 0) return prev;
                    const swap = dir === 'up' ? idx - 1 : idx + 1;
                    if (swap < 0 || swap >= sorted.length) return prev;
                    const temp = sorted[idx].order;
                    sorted[idx] = { ...sorted[idx], order: sorted[swap].order };
                    sorted[swap] = { ...sorted[swap], order: temp };
                    return sorted;
                });
            };

            const renderWidget = (widget) => {
                switch(widget.type) {
                    case 'Clock': return <div className="flex flex-col items-center justify-center h-full p-4 w-full">{clockFeed ? <img src={clockFeed} className="w-56 h-56 drop-shadow-2xl object-contain" /> : <div className="text-gray-500">Loading Horology...</div>}</div>;
                    case 'Calendar': return <DualCalendar backend={backend} refreshGoals={refreshGoals} goals={goals} />;
                    case 'GlobalTargets': return <GlobalTargets metrics={metrics} />;
                    case 'GitHubMatrix': return <NativeGitHubMatrix heatmap={heatmap} />;
                    case 'HabitsWidget': return <DashboardHabitWidget habits={habits} habitLogs={habitLogs} />;
                    case 'MetricsWidget': return <MetricsWidget metrics={metrics} />;
                    case 'ArchitectureWidget': return <DashboardArchitectureWidget goals={goals} studiedHours={studiedHours} courseColors={courseColors} />;
                    case 'GoalProgress': return <GoalProgressWidget goals={goals} studiedHours={studiedHours} courseColors={courseColors} />;
                    case 'GoalTimeChart': return <GoalTimeChartWidget backend={backend} goals={goals} studiedHours={studiedHours} />;
                    case 'DailySummary': return <DailySummaryWidget metrics={metrics} todaySessions={todaySessions} />;
                    case 'RecentActivity': return <RecentActivityWidget activityLogs={activityLogs} />;
                    case 'HealthTrends': return <DashboardHealthWidget healthProfile={healthProfile} healthLogs={healthLogs} />;
                    case 'DailyCheckin': return <DailyCheckinWidget backend={backend} dailyMetrics={dailyMetrics} setDailyMetrics={setDailyMetrics} />;
                    case 'CorrelationCharts': return <CorrelationChartsWidget backend={backend} correlations={correlations} insights={insights} />;
                    default: return null;
                }
            };

            const sortedLayout = [...layout].sort((a, b) => a.order - b.order);
            const bmr = (healthProfile && healthProfile.weight) ? ((10 * healthProfile.weight) + (6.25 * healthProfile.height) - (5 * healthProfile.age) + (healthProfile.gender === 'Male' ? 5 : -161)) : 0;
            const tdee = bmr * (healthProfile?.activity || 1.2);

            return (
                <div className="h-full flex flex-col fade-in">
                    <div className="flex justify-between items-center mb-6 shrink-0">
                        <h2 className="text-2xl font-serif font-bold text-white tracking-widest uppercase text-shadow-blue drop-shadow-md">Dashboard</h2>
                        <div className="flex gap-4 items-center">
                            {healthProfile && healthProfile.weight && (
                                <div className="hidden lg:flex items-center gap-3 bg-black/40 border border-white/10 px-4 py-2 rounded shadow-lg backdrop-blur-md">
                                    <div className="text-xs text-green-400 font-bold"><i className="fas fa-heartbeat mr-1"></i> TDEE: {tdee.toFixed(0)} kcal</div>
                                    <div className="text-xs text-blue-400 font-bold"><i className="fas fa-weight mr-1"></i> {healthProfile.weight} kg</div>
                                </div>
                            )}
                            <button onClick={() => setIsEditingLayout(!isEditingLayout)} className={`px-4 py-2 rounded text-xs font-bold transition-all shadow-lg border backdrop-blur-md ${isEditingLayout ? 'bg-blue-600 text-white border-blue-400 shadow-[0_0_15px_rgba(59,130,246,0.6)]' : 'bg-white/5 text-gray-300 border-white/10 hover:bg-white/15'}`}><i className={`fas ${isEditingLayout ? 'fa-check' : 'fa-sliders-h'} mr-2`}></i> {isEditingLayout ? 'Done' : 'Edit Layout'}</button>
                        </div>
                    </div>
                    <div className="flex flex-wrap -mx-3 items-stretch overflow-y-auto pb-10 flex-grow content-start">
                        {sortedLayout.filter(w => isEditingLayout || w.visible).map((widget) => {
                            const widthClass = SIZE_CLASSES[widget.size] || SIZE_CLASSES.half;
                            return (
                                <div key={widget.id} className={`${widthClass} px-3 mb-6 transition-all duration-300`}>
                                    <div className={`glass-panel overflow-hidden h-full flex flex-col relative ${!widget.visible ? 'opacity-30 grayscale' : ''}`} style={{ minHeight: '320px' }}>
                                        {isEditingLayout && (
                                            <div className="absolute inset-0 bg-black/80 z-50 flex flex-col items-center justify-center backdrop-blur-sm gap-3 rounded-xl border-2 border-blue-500 border-dashed">
                                                <div className="text-white font-bold text-lg uppercase tracking-widest">{widget.type}</div>
                                                <div className="flex gap-2 mt-4 flex-wrap justify-center">
                                                    <button onClick={() => toggleWidgetVisibility(widget.id)} className={`px-3 py-1.5 rounded text-xs font-bold ${widget.visible ? 'bg-green-600' : 'bg-red-600'} text-white`}><i className={`fas fa-${widget.visible ? 'eye' : 'eye-slash'} mr-1`}></i> {widget.visible ? 'Hide' : 'Show'}</button>
                                                    <button onClick={() => cycleWidgetSize(widget.id)} className="px-3 py-1.5 rounded text-xs font-bold bg-blue-600 text-white"><i className="fas fa-arrows-alt-h mr-1"></i> Size: {widget.size}</button>
                                                    <button onClick={() => moveWidget(widget.id, 'up')} className="px-2 py-1.5 rounded text-xs font-bold bg-white/10 text-white hover:bg-white/20"><i className="fas fa-arrow-up"></i></button>
                                                    <button onClick={() => moveWidget(widget.id, 'down')} className="px-2 py-1.5 rounded text-xs font-bold bg-white/10 text-white hover:bg-white/20"><i className="fas fa-arrow-down"></i></button>
                                                </div>
                                            </div>
                                        )}
                                        {renderWidget(widget)}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            );
        };
