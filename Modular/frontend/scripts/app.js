        const { useState, useEffect, useMemo, useRef, useCallback } = React;

        /* Clock feed pub/sub: keeps the once-per-second QWebChannel clock
           signal from re-rendering the entire App tree. Widgets subscribe
           through subscribeClock / useClockFeed instead of App state. */
        const clockFeedSubs = new Set();
        let lastClockFeed = null;
        const subscribeClock = (fn) => { clockFeedSubs.add(fn); return () => clockFeedSubs.delete(fn); };
        const publishClock = (b64) => {
            lastClockFeed = b64;
            clockFeedSubs.forEach(fn => fn(b64));
        };
        const useClockFeed = () => {
            const [feed, setFeed] = useState(lastClockFeed);
            useEffect(() => subscribeClock(setFeed), []);
            return feed;
        };

        /* Timer feed pub/sub: the once-per-second pomodoro state signal drives
           ONLY the widgets that render live timer state (mini widget + hub),
           instead of re-rendering the whole App tree on every tick. */
        const DEFAULT_TIMER_STATE = { is_running: false, time_str: "25:00", progress: 0, distractions: 0, course: "General", active_queue_id: null, total_time: 1500, time_left: 1500, distraction_markers: [], distraction_log: [] };
        let timerSubs = new Set();
        let lastTimerState = DEFAULT_TIMER_STATE;
        let lastQueueJson = null;
        const subscribeTimer = (fn) => { timerSubs.add(fn); return () => timerSubs.delete(fn); };
        const publishTimer = (state) => { lastTimerState = state; timerSubs.forEach(fn => fn(state)); };
        const useTimerState = () => {
            const [timer, setTimer] = useState(lastTimerState);
            useEffect(() => subscribeTimer(setTimer), []);
            return timer;
        };

        const DEFAULT_LAYOUT = [
            { id: 'pomodoro_mini', type: 'PomodoroMini', size: 'quarter', visible: true, order: 0 },
            { id: 'clock', type: 'Clock', size: 'quarter', visible: true, order: 1 },
            { id: 'targets', type: 'GlobalTargets', size: 'quarter', visible: true, order: 2 },
            { id: 'study_streak', type: 'StudyStreak', size: 'quarter', visible: true, order: 3 },
            { id: 'daily_summary', type: 'DailySummary', size: 'third', visible: true, order: 4 },
            { id: 'daily_checkin', type: 'DailyCheckin', size: 'third', visible: true, order: 5 },
            { id: 'correlations', type: 'CorrelationCharts', size: 'third', visible: true, order: 6 },
            { id: 'goal_progress', type: 'GoalProgress', size: 'half', visible: true, order: 7 },
            { id: 'goal_time_chart', type: 'GoalTimeChart', size: 'half', visible: true, order: 8 },
            { id: 'weekly_breakdown', type: 'WeeklyGoalBreakdown', size: 'half', visible: true, order: 9 },
            { id: 'best_hours', type: 'BestHours', size: 'half', visible: true, order: 10 },
            { id: 'calendar', type: 'Calendar', size: 'full', visible: true, order: 11 },
            { id: 'matrix', type: 'GitHubMatrix', size: 'half', visible: true, order: 12 },
            { id: 'recent_activity', type: 'RecentActivity', size: 'half', visible: true, order: 13 },
            { id: 'habits', type: 'HabitsWidget', size: 'half', visible: true, order: 14 },
            { id: 'metrics', type: 'MetricsWidget', size: 'half', visible: true, order: 15 },
            { id: 'architecture', type: 'ArchitectureWidget', size: 'full', visible: true, order: 16 },
            { id: 'health_trends', type: 'HealthTrends', size: 'full', visible: true, order: 17 }
        ];

        const App = () => {
            const [currentView, setCurrentView] = useState('hub');
            const [backend, setBackend] = useState(null);
            
            // New State for Collapsible Sidebar
            const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
            const [syncLogs, setSyncLogs] = useState([]);
            const [courses, setCourses] = useState([]);
            const [goals, setGoals] = useState([]);
            const [flatGoals, setFlatGoals] = useState([]);
            const [heatmap, setHeatmap] = useState([]);
            const [settings, setSettings] = useState({
                git_status: 'unknown', git_last_sync: null, process_list: [], mapped_folders: [], has_token: false,
                health_age: 25, health_height: 175, health_weight: 70, health_gender: 'Male', health_activity: 1.2, health_deficit: 500
            });
            const [metrics, setMetrics] = useState(null);
            const [habits, setHabits] = useState([]);
            const [habitLogs, setHabitLogs] = useState([]);
            const [flashcards, setFlashcards] = useState([]);
            const [quizzes, setQuizzes] = useState([]);
            const [queue, setQueue] = useState([]);
            const [notes, setNotes] = useState([]);
            const [networkFolders, setNetworkFolders] = useState([]);
            const [courseColors, setCourseColors] = useState({});
            
            // New Activity Logs
            const [activityLogs, setActivityLogs] = useState([]);
            
            const [healthProfile, setHealthProfile] = useState({});
            const [healthLogs, setHealthLogs] = useState([]);
            const [customFoods, setCustomFoods] = useState([]);
            const [customActivities, setCustomActivities] = useState([]);
            const [healthPlans, setHealthPlans] = useState([]);
            
            const [ingredients, setIngredients] = useState([]);
            const [compositeFoods, setCompositeFoods] = useState([]);
            
            const [layout, setLayout] = useState(DEFAULT_LAYOUT);
            const [isEditingLayout, setIsEditingLayout] = useState(false);
            
            const [todaySessions, setTodaySessions] = useState([]);
            const [studiedHours, setStudiedHours] = useState({});
            const [showScanModal, setShowScanModal] = useState(false);
            const [scanEditData, setScanEditData] = useState({});
            
            // Daily Check-in / Analytics
            const [dailyMetrics, setDailyMetrics] = useState(null);
            const [correlations, setCorrelations] = useState({});
            const [insights, setInsights] = useState([]);

            // Auto-collapse sidebar on smaller screens
            useEffect(() => {
                const handleResize = () => {
                    if (window.innerWidth < 1024) { setIsSidebarCollapsed(true); }
                    else { setIsSidebarCollapsed(false); }
                };
                window.addEventListener('resize', handleResize);
                handleResize(); // Check on mount
                return () => window.removeEventListener('resize', handleResize);
            }, []);

            const refreshTodayData = () => {
                if (backend) {
                    backend.request(JSON.stringify({action: 'get_today_data'})).then(res => {
                        const data = JSON.parse(res);
                        if (data.today_sessions) setTodaySessions(data.today_sessions);
                        if (data.studied_hours) setStudiedHours(data.studied_hours);
                    });
                }
            };

            const refreshGoals = (data) => {
                if (data && data.goals) setGoals(data.goals);
                if (data && data.flat_goals) setFlatGoals(data.flat_goals);
                if (!data && backend) {
                    backend.request(JSON.stringify({action: 'init'})).then(res => {
                        const data = JSON.parse(res);
                        if (data.goals) setGoals(data.goals);
                        if (data.flat_goals) setFlatGoals(data.flat_goals);
                    });
                }
            };

            const dumpCurrentUiState = () => {
                const state = {
                    currentView,
                    ts: new Date().toISOString(),
                    goals: goals,
                    flatGoals: flatGoals,
                    habits: habits,
                    habitLogs: habitLogs,
                    studiedHours: studiedHours,
                    metrics: metrics,
                    activityLogsCount: activityLogs ? activityLogs.length : 0,
                    todaySessionsCount: todaySessions ? todaySessions.length : 0,
                    flashcardsCount: flashcards ? flashcards.length : 0,
                    quizzesCount: quizzes ? quizzes.length : 0,
                    queueCount: queue ? queue.length : 0,
                    notesCount: notes ? notes.length : 0,
                    health_logsCount: healthLogs ? healthLogs.length : 0,
                    hasUiError: window.__uiError ? window.__uiError : null,
                };
                if (backend) {
                    backend.request(JSON.stringify({action: 'dump_ui_state', ui_state: state})).then(res => {
                        const data = JSON.parse(res);
                        console.log('[ui-debug] UI state saved:', data.path || data.status);
                    });
                }
                return state;
            };
            window.__dumpUiState = dumpCurrentUiState;
            window.addEventListener('error', (e) => {
                window.__uiError = e.message + ' @ ' + (e.filename || '') + ':' + (e.lineno || '');
                console.log('[ui-debug] JS error captured:', window.__uiError);
            });

            useEffect(() => {
                if (!backend) return;
                console.log('[ui-debug] dumpUiState available: type window.__dumpUiState()');
                const onKeyDown = (e) => {
                    if (e.ctrlKey && e.shiftKey && (e.key === 'D' || e.key === 'd')) {
                        e.preventDefault();
                        window.__dumpUiState();
                    }
                };
                window.addEventListener('keydown', onKeyDown);
                return () => window.removeEventListener('keydown', onKeyDown);
            }, [backend, currentView, goals, habits, studiedHours, metrics]);

            useEffect(() => {
                if (typeof qt !== 'undefined') {
                    new QWebChannel(qt.webChannelTransport, (channel) => {
                        const py = channel.objects.backend;
                        setBackend(py);
                        
                        py.state_update.connect((state_json) => { 
                            const state = JSON.parse(state_json);
                            if (lastTimerState.is_running && !state.is_running) {
                                setTimeout(() => {
                                    py.request(JSON.stringify({action: 'get_today_data'})).then(r => {
                                        const d = JSON.parse(r);
                                        if (d.today_sessions) setTodaySessions(d.today_sessions);
                                        if (d.studied_hours) setStudiedHours(d.studied_hours);
                                    });
                                }, 500);
                            }
                            publishTimer(state);
                            if (state.queue) {
                                const qJson = JSON.stringify(state.queue);
                                if (qJson !== lastQueueJson) {
                                    lastQueueJson = qJson;
                                    setQueue(state.queue);
                                }
                            }
                        });
                        
                        py.video_feed.connect((b64) => { 
                            const img = document.getElementById('vision-tracker-img');
                            if (img) {
                                img.src = `data:image/jpeg;base64,${b64}`;
                                img.classList.remove('hidden');
                                const placeholder = document.getElementById('vision-tracker-placeholder');
                                if (placeholder) placeholder.classList.add('hidden');
                            }
                        });
                        
                        py.clock_feed.connect((b64) => { publishClock(b64); });
                        py.scan_ready.connect((json_str) => {
                            const data = JSON.parse(json_str);
                            setScanEditData(data);
                            setShowScanModal(true);
                        });

                        py.sync_progress.connect((msg) => {
                            const match = msg.match(/\((\d+(\.\d+)?)%\)/);
                            const pct = match ? parseFloat(match[1]) : 50;
                            setSettings(prev => ({
                                ...prev, 
                                git_status: 'syncing', 
                                sync_msg: msg,
                                sync_progress_pct: pct
                            }));
                            // Use a callback to prevent state batching issues
                            setSyncLogs(prev => {
                                const newLogs = [...prev, `🔄 ${msg}`];
                                return newLogs.slice(-50);
                            });
                        });


                    
                        py.sync_completed.connect((success, msg) => {
                            setSettings(prev => ({
                                ...prev, 
                                git_status: success ? 'connected' : 'error',
                                git_last_sync: new Date().toLocaleString(),
                                sync_msg: msg,
                                sync_progress_pct: success ? 100 : 0
                            }));
                            setSyncLogs(prev => {
                                const newLogs = [...prev, `${success ? '✅' : '❌'} ${msg}`];
                                return newLogs.slice(-50);
                            });
                            if(success) {
                                py.request(JSON.stringify({action: 'init'})).then(res => {
                                    const data = JSON.parse(res);
                                    if(data.activity_logs) setActivityLogs(data.activity_logs);
                                });
                            }
                        });
                        py.request(JSON.stringify({action: 'init'})).then(res => {
                            const data = JSON.parse(res);
                            if (data.courses) setCourses(data.courses);
                            if (data.goals) setGoals(data.goals);
                            if (data.flat_goals) setFlatGoals(data.flat_goals);
                            if (data.heatmap) setHeatmap(data.heatmap);
                            
                            // Safe merge to prevent bg_image_path from being overwritten if missing
                            setSettings(prev => ({...prev, ...data.settings}));
                            
                            if (data.activity_logs) setActivityLogs(data.activity_logs);
                            if (data.habits) setHabits(data.habits);
                            if (data.habit_logs) setHabitLogs(data.habit_logs);
                            if (data.flashcards) setFlashcards(data.flashcards);
                            if (data.quizzes) setQuizzes(data.quizzes);
                            if (data.queue) setQueue(data.queue);
                            if (data.notes) setNotes(data.notes);
                            if (data.course_colors) setCourseColors(data.course_colors);
                            if (data.metrics_data) setMetrics(data.metrics_data);
                            if (data.studied_hours) setStudiedHours(data.studied_hours);

                            if (data.health_profile) {
                                setHealthProfile(data.health_profile);
                                setSettings(prev => ({
                                    ...prev,
                                    health_age: data.health_profile.age || prev.health_age,
                                    health_height: data.health_profile.height || prev.health_height,
                                    health_weight: data.health_profile.weight || prev.health_weight,
                                    health_gender: data.health_profile.gender || prev.health_gender,
                                    health_activity: data.health_profile.activity || prev.health_activity,
                                    health_deficit: data.health_profile.deficit_goal || prev.health_deficit
                                }));
                            }

                            if (data.health_logs) setHealthLogs(data.health_logs);
                            if (data.custom_foods) setCustomFoods(data.custom_foods);
                            if (data.custom_activities) setCustomActivities(data.custom_activities);
                            if (data.health_plans) setHealthPlans(data.health_plans);
                            
                            py.request(JSON.stringify({action: 'manage_nutrition', sub: 'get_all'})).then(resN => {
                                const nData = JSON.parse(resN);
                                if(nData.ingredients) setIngredients(nData.ingredients);
                                if(nData.composite_foods) setCompositeFoods(nData.composite_foods);
                            });

                            py.request(JSON.stringify({action: 'get_sync_status'})).then(res => {
                                const syncData = JSON.parse(res);
                                setSettings(prev => ({
                                    ...prev,
                                    device_id: syncData.device_id,
                                    sync_enabled: syncData.enabled,
                                    sync_repo_url: syncData.repo_url,
                                    sync_interval: syncData.interval,
                                    has_token: syncData.has_token
                                }));
                            });
                            py.request(JSON.stringify({action: 'get_mapped_folders'})).then(res => {
                                const data = JSON.parse(res);
                                setSettings(prev => ({...prev, mapped_folders: data.folders}));
                                setNetworkFolders(data.network_folders);
                            });
                            
                            // Initialize Timeline Data on Boot
                            py.request(JSON.stringify({action: 'get_today_data'})).then(r => {
                                const d = JSON.parse(r);
                                if (d.today_sessions) setTodaySessions(d.today_sessions);
                                if (d.studied_hours) setStudiedHours(d.studied_hours);
                            });

                            py.request(JSON.stringify({action: 'get_active_wallpaper'})).then(r => {
                                const wallpaper = JSON.parse(r);
                                if (wallpaper.data_url) {
                                    setSettings(prev => ({...prev, bg_image_path: '', bg_image_data_url: wallpaper.data_url}));
                                }
                            });
                            
                            // Fetch daily check-in
                            py.request(JSON.stringify({action: 'manage_analytics', sub: 'get_daily_checkin'})).then(r => {
                                const d = JSON.parse(r);
                                if (d.date) setDailyMetrics(d);
                            });
                            
                            // Fetch correlations and insights
                            py.request(JSON.stringify({action: 'manage_analytics', sub: 'get_correlations'})).then(r => {
                                const d = JSON.parse(r);
                                if (d.correlations) setCorrelations(d.correlations);
                            });
                            py.request(JSON.stringify({action: 'manage_analytics', sub: 'get_insights'})).then(r => {
                                const d = JSON.parse(r);
                                if (d.insights) setInsights(d.insights);
                            });
                        });
                    });
                }
            }, []);

            // Safe fallback logic for Background Image
            useEffect(() => {
                const bg = settings.bg_image_data_url || (settings.bg_image_path !== undefined ? settings.bg_image_path : 'img/bg.jpg');
                document.body.style.backgroundImage = `url('${bg}')`;
                document.body.style.backgroundSize = 'cover';
                document.body.style.backgroundPosition = 'center';
                document.body.style.backgroundAttachment = 'fixed';
                
                if (settings.font_family) document.body.style.fontFamily = settings.font_family;
                if (settings.font_color) document.body.style.color = settings.font_color;
            }, [settings.bg_image_data_url, settings.bg_image_path, settings.font_family, settings.font_color]);
            
            const renderContent = () => {
                switch(currentView) {
                    case 'dashboard': return <DashboardView layout={layout} setLayout={setLayout} goals={goals} isEditingLayout={isEditingLayout} setIsEditingLayout={setIsEditingLayout} heatmap={heatmap} habits={habits} habitLogs={habitLogs} metrics={metrics} backend={backend} refreshGoals={refreshGoals} healthProfile={healthProfile} healthLogs={healthLogs} studiedHours={studiedHours} courseColors={courseColors} dailyMetrics={dailyMetrics} setDailyMetrics={setDailyMetrics} correlations={correlations} insights={insights} activityLogs={activityLogs} todaySessions={todaySessions} flatGoals={flatGoals} />;
                    case 'health': return <HealthFitnessView backend={backend} healthProfile={healthProfile} setHealthProfile={setHealthProfile} healthLogs={healthLogs} setHealthLogs={setHealthLogs} customFoods={customFoods} customActivities={customActivities} healthPlans={healthPlans} ingredients={ingredients} setIngredients={setIngredients} compositeFoods={compositeFoods} setCompositeFoods={setCompositeFoods} onScanParsed={(data) => { setScanEditData(data); setShowScanModal(true); }} />;
                    case 'hub': return <ProductivityHubView backend={backend} flatGoals={flatGoals} queue={queue} refreshQueue={setQueue} settings={settings} todaySessions={todaySessions} courseColors={courseColors} />;
                    case 'architecture': return <LifeArchitectureView goals={goals} backend={backend} refreshGoals={(d) => {setGoals(d.goals); setFlatGoals(d.flat_goals);}} courseColors={courseColors} studiedHours={studiedHours} />;
                    case 'habits': return <HabitMatrixView habits={habits} backend={backend} refreshHabits={setHabits} habitLogs={habitLogs} setHabitLogs={setHabitLogs} />;
                    case 'summary': return <DaySummaryView metrics={metrics} />;
                    case 'library': return <PDFLibraryView backend={backend} />;
                    case 'quiz': return <QuizEngineView quizzes={quizzes} backend={backend} refreshQuizzes={setQuizzes} flatGoals={flatGoals} courseColors={courseColors} />;
                    case 'flashcards': return <FlashcardsView flashcards={flashcards} backend={backend} refreshCards={setFlashcards} flatGoals={flatGoals} courseColors={courseColors} />;
                    case 'notes': return <NotesView notes={notes} backend={backend} refreshNotes={setNotes} flatGoals={flatGoals} courseColors={courseColors} />;
                    case 'settings': return <SettingsView settings={settings} setSettings={setSettings} backend={backend} networkFolders={networkFolders} setNetworkFolders={setNetworkFolders} activityLogs={activityLogs} syncLogs={syncLogs} />;
                    default: return <div className="text-white text-center mt-20 font-bold">Module Loading...</div>;
                }
            };

            return (
                <div className="h-screen w-screen flex overflow-hidden">
                    <div className={`transition-all duration-300 ease-in-out ${isSidebarCollapsed ? 'w-20' : 'w-64'} glass-panel-darker border-r border-white/10 flex flex-col py-6 z-50 shrink-0 relative shadow-2xl rounded-none border-y-0 border-l-0`}>
                        
                        <button onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)} className="absolute -right-3 top-8 bg-blue-600 text-white w-6 h-6 rounded-full flex items-center justify-center shadow-[0_0_10px_rgba(59,130,246,0.5)] hover:bg-blue-500 z-50 transition-transform">
                            <i className={`fas fa-chevron-${isSidebarCollapsed ? 'right' : 'left'} text-[10px]`}></i>
                        </button>

<div className={`px-4 md:px-8 mb-8 flex items-center ${isSidebarCollapsed ? 'justify-center' : 'justify-start'} gap-3 transition-all`}>
    <img src="../assets/logo.svg" alt="Mind Palace Logo" className="w-8 h-8 md:w-10 md:h-10 shrink-0 drop-shadow-[0_0_10px_rgba(59,130,246,0.6)]" />
    {!isSidebarCollapsed && (
        <h1 className="text-xl font-serif font-bold tracking-widest text-white uppercase drop-shadow-md whitespace-nowrap overflow-hidden">Mind Palace OS</h1>
    )}
</div>
                        
                        <nav className="flex flex-col gap-1 px-2 md:px-4 overflow-y-auto flex-grow custom-scrollbar">
                            {[
                                { id: 'dashboard', icon: 'fa-th-large', label: 'Dashboard' },
                                { id: 'health', icon: 'fa-heartbeat', label: 'Health & Fitness' },
                                { id: 'hub', icon: 'fa-bolt', label: 'Productivity Hub' },
                                { id: 'architecture', icon: 'fa-sitemap', label: 'Life Architecture' },
                                { id: 'habits', icon: 'fa-check-square', label: 'Habit Matrix' },
                                { id: 'summary', icon: 'fa-calendar-day', label: 'Day Summary' },
                                { id: 'library', icon: 'fa-book-reader', label: 'PDF Library' },
                                { id: 'quiz', icon: 'fa-question-circle', label: 'Quiz Engine' },
                                { id: 'flashcards', icon: 'fa-clone', label: 'Flashcards' },
                                { id: 'notes', icon: 'fa-edit', label: 'Notes' },
                            ].map(nav => (
                                <NavBtn key={nav.id} id={nav.id} icon={nav.icon} label={nav.label} current={currentView} set={setCurrentView} collapsed={isSidebarCollapsed} />
                            ))}
                        </nav>
                        
                        <div className="px-2 md:px-4 mt-4 pt-4 border-t border-white/10">
                            <NavBtn id="settings" icon="fa-cog" label="Settings" current={currentView} set={setCurrentView} collapsed={isSidebarCollapsed} />
                        </div>
                    </div>
                    
                    <div className="flex-grow flex flex-col relative h-full overflow-hidden p-4 sm:p-6 lg:p-8">
                        {renderContent()}
                    </div>
                    
                    {/* Global Editor Modal for OCR Scans */}
                    {showScanModal && (
                        <div className="fixed inset-0 bg-black/90 z-[100] flex items-center justify-center p-4 backdrop-blur-md">
                            <div className="glass-panel p-8 max-w-lg w-full shadow-2xl border border-white/20 fade-in">
                                <h3 className="text-white font-serif font-bold text-2xl mb-1 tracking-wider uppercase text-center">Review Scan Data</h3>
                                <p className="text-gray-400 text-[10px] uppercase tracking-widest text-center mb-6">Correct any OCR errors before saving</p>
                                
                                <div className="grid grid-cols-2 gap-x-6 gap-y-4 mb-8">
                                    {['weight', 'body_score', 'bmi', 'body_fat', 'muscle_mass', 'water', 'bmr'].map(key => (
                                        <div key={key} className="flex flex-col">
                                            <label className="text-[10px] text-gray-400 uppercase tracking-widest mb-1 pl-1">{key.replace('_', ' ')}</label>
                                            <input type="number" step="0.1" 
                                                className="glass-input p-3 rounded-lg text-sm font-mono font-bold text-blue-300 focus:border-blue-500 focus:bg-white/5 transition-all" 
                                                value={scanEditData[key] || ''} 
                                                onChange={e => setScanEditData({...scanEditData, [key]: parseFloat(e.target.value) || null})} 
                                            />
                                        </div>
                                    ))}
                                </div>
                                
                                <div className="flex gap-4 mt-4">
                                    <button onClick={() => {
                                        backend.request(JSON.stringify({action: 'save_body_scan', data: scanEditData})).then(saveRes => {
                                            const saveData = JSON.parse(saveRes);
                                            if (saveData.status === 'success') {
                                                if(saveData.health_profile) setHealthProfile(saveData.health_profile);
                                                if(saveData.health_logs) setHealthLogs(saveData.health_logs);
                                            }
                                            setShowScanModal(false);
                                        });
                                    }} className="glass-button px-6 py-3 rounded-lg text-xs font-bold tracking-widest w-full bg-green-600/30 text-green-400 border border-green-500/50 hover:bg-green-600 hover:text-white transition uppercase shadow-lg">Save to DB</button>
                                    
                                    <button onClick={() => setShowScanModal(false)} className="glass-button px-6 py-3 rounded-lg text-xs font-bold tracking-widest w-full bg-red-600/30 text-red-400 border border-red-500/50 hover:bg-red-600 hover:text-white transition uppercase shadow-lg">Discard</button>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            );
        };

        const root = ReactDOM.createRoot(document.getElementById('root'));
        root.render(<App />);
