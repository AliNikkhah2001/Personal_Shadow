        const HealthFitnessView = ({ backend, healthProfile, setHealthProfile, healthLogs, setHealthLogs, customFoods, customActivities, healthPlans, ingredients, setIngredients, compositeFoods, setCompositeFoods, onScanParsed }) => {
                    const [activeTab, setActiveTab] = useState('dashboard');
                    const [intakeTab, setIntakeTab] = useState('diary'); // 'diary', 'ingredients', 'builder'
                    // Exercise States
                    const [exName, setExName] = useState("");
                    const [exDur, setExDur] = useState("");
                    const [exKcal, setExKcal] = useState("");
                    
                    // Ingredient DB States
                    const [ingName, setIngName] = useState("");
                    const [ingKcal, setIngKcal] = useState("");
                    const [ingPro, setIngPro] = useState("");
                    const [ingFat, setIngFat] = useState("");
                    const [ingCarbs, setIngCarbs] = useState("");
                    const [isIranian, setIsIranian] = useState(false);
                    
                    // Recipe Builder States
                    const [recName, setRecName] = useState("");
                    const [recInstructions, setRecInstructions] = useState("");
                    const [recPrepTime, setRecPrepTime] = useState(0);
                    const [recCookTime, setRecCookTime] = useState(0);
                    const [recServings, setRecServings] = useState(1);
                    const [recParts, setRecParts] = useState([]);
                    const [partSelect, setPartSelect] = useState("");
                    const [partGrams, setPartGrams] = useState(100);
                    
                    // Diary State
                    const [diarySelect, setDiarySelect] = useState("");
                    const [diaryAmount, setDiaryAmount] = useState(100);
                    const [diaryIsRecipe, setDiaryIsRecipe] = useState(false);
                    
                    // Plan Builder
                    const [planType, setPlanType] = useState("Diet");
                    const [planTitle, setPlanTitle] = useState("");
                    const [planDetails, setPlanDetails] = useState("");

                    const logEntry = (type, data) => {
                        const today = new Date().toISOString().slice(0, 10);
                        backend.request(JSON.stringify({action: 'manage_health', sub: 'log_entry', log_type: type, date: today, data})).then(res => {
                            const parsed = JSON.parse(res);
                            if (parsed.health_logs) setHealthLogs(parsed.health_logs);
                        });
                    };

                    const logDiaryEntry = () => {
                        if(!diarySelect) return;
                        let targetKcal = 0; let targetPro = 0;
                        
                        if(diaryIsRecipe) {
                            const r = compositeFoods.find(c => c.name === diarySelect);
                            if(r) { targetKcal = (r.kcal * (diaryAmount/100.0)); targetPro = (r.protein * (diaryAmount/100.0)); }
                        } else {
                            const i = ingredients.find(ing => ing.name === diarySelect);
                            if(i) { targetKcal = (i.kcal * (diaryAmount/100.0)); targetPro = (i.protein * (diaryAmount/100.0)); }
                        }
                        
                        logEntry('food', {name: diarySelect, amount_grams: parseFloat(diaryAmount), kcal: targetKcal, protein: targetPro});
                        setDiarySelect(""); setDiaryAmount(100);
                    };

                    const saveIngredient = () => {
                        if(!ingName) return;
                        backend.request(JSON.stringify({action: 'manage_nutrition', sub: 'add_ingredient', name: ingName, kcal: ingKcal, protein: ingPro, fat: ingFat, carbs: ingCarbs, is_iranian: isIranian})).then(res => {
                            const data = JSON.parse(res);
                            setIngredients(data.ingredients); setCompositeFoods(data.composite_foods);
                            setIngName(""); setIngKcal(""); setIngPro(""); setIngFat(""); setIngCarbs(""); setIsIranian(false);
                        });
                    };

                    const saveRecipe = () => {
                        if(!recName || recParts.length === 0) return;
                        backend.request(JSON.stringify({action: 'manage_nutrition', sub: 'add_composite', name: recName, parts: recParts, instructions: recInstructions, prep_time_min: parseInt(recPrepTime)||0, cook_time_min: parseInt(recCookTime)||0, servings: parseInt(recServings)||1})).then(res => {
                            const data = JSON.parse(res);
                            setIngredients(data.ingredients); setCompositeFoods(data.composite_foods);
                            setRecName(""); setRecInstructions(""); setRecPrepTime(0); setRecCookTime(0); setRecServings(1); setRecParts([]);
                        });
                    };

                    const saveCustomEx = () => {
                        if(!exName) return;
                        backend.request(JSON.stringify({action: 'manage_health', sub: 'save_activity', name: exName, met: 5.0, category: "Cardio"})).then(() => {
                            logEntry('exercise', {name: exName, duration: exDur, kcal_burn: parseFloat(exKcal)||0});
                            setExName(""); setExDur(""); setExKcal("");
                        });
                    };

                    const savePlan = () => {
                        backend.request(JSON.stringify({action: 'manage_health', sub: 'save_plan', type: planType, title: planTitle, details: planDetails})).then(res => {
                            setPlanTitle(""); setPlanDetails("");
                        });
                    };

                    const importBodyScan = () => {
                        backend.request(JSON.stringify({action: 'import_body_scan'})).then(res => {
                            const data = JSON.parse(res);
                            if (data.status === 'success') {
                                if (onScanParsed) onScanParsed(data.parsed_data);
                            } else if (data.status === 'error') {
                                console.error(`❌ Error parsing scan: ${data.message}`);
                            }
                        });
                    };

                    const bmr = (healthProfile && healthProfile.weight) ? ((10 * healthProfile.weight) + (6.25 * healthProfile.height) - (5 * healthProfile.age) + (healthProfile.gender === 'Male' ? 5 : -161)) : 0;
                    const tdee = bmr * (healthProfile?.activity || 1.2);
                    const targetKcal = tdee - (healthProfile?.deficit_goal || 500);

                    const todayStr = new Date().toISOString().slice(0, 10);
                    const safeHealthLogs = healthLogs || [];
                    const todayLogs = safeHealthLogs.filter(l => l.date === todayStr);
                    const todayFood = todayLogs.filter(l => l.type === 'food');
                    const todayEx = todayLogs.filter(l => l.type === 'exercise');

                    const totalIntake = todayFood.reduce((sum, l) => sum + (parseFloat(l.data.kcal) || 0), 0);
                    const totalBurn = todayEx.reduce((sum, l) => sum + (parseFloat(l.data.kcal_burn) || 0), 0);
                    const currentDeficit = tdee + totalBurn - totalIntake;
                    
                    const chartRef = useRef(null);
                    
                    useEffect(() => {
                        if (activeTab === 'dashboard' && chartRef.current && window.Chart) {
                            const ctx = chartRef.current.getContext('2d');
                            
                            const dailyStats = {};
                            healthLogs.forEach(l => {
                                if (!dailyStats[l.date]) dailyStats[l.date] = { intake: 0, burn: 0 };
                                if (l.type === 'food') dailyStats[l.date].intake += (parseFloat(l.data.kcal) || 0);
                                if (l.type === 'exercise') dailyStats[l.date].burn += (parseFloat(l.data.kcal_burn) || 0);
                            });
                            
                            const sortedDates = Object.keys(dailyStats).sort();
                            const deficits = sortedDates.map(d => (tdee + dailyStats[d].burn) - dailyStats[d].intake);
                            
                            let projWeight = healthProfile?.weight || 70;
                            const projWeights = sortedDates.map((d, i) => {
                                projWeight -= (deficits[i] / 7700);
                                return projWeight;
                            });

                            let chartInstance = new window.Chart(ctx, {
                                type: 'line',
                                data: {
                                    labels: sortedDates.length > 0 ? sortedDates : [todayStr],
                                    datasets: [{
                                        label: 'Projected Weight (kg)',
                                        data: projWeights.length > 0 ? projWeights : [healthProfile?.weight || 70],
                                        borderColor: '#3b82f6',
                                        tension: 0.3,
                                        yAxisID: 'y'
                                    }, {
                                        type: 'bar',
                                        label: 'Daily Deficit (kcal)',
                                        data: deficits.length > 0 ? deficits : [currentDeficit],
                                        backgroundColor: '#22c55e',
                                        yAxisID: 'y1'
                                    }]
                                },
                                options: {
                                    responsive: true,
                                    maintainAspectRatio: false,
                                    scales: {
                                        y: { type: 'linear', position: 'left', title: {display: true, text: 'Weight (kg)', color: 'white'}, ticks: {color: 'gray'} },
                                        y1: { type: 'linear', position: 'right', title: {display: true, text: 'Deficit (kcal)', color: 'white'}, ticks: {color: 'gray'}, grid: {drawOnChartArea: false} },
                                        x: { ticks: {color: 'gray'} }
                                    },
                                    plugins: { legend: { labels: {color: 'white'} } }
                                }
                            });
                            return () => chartInstance.destroy();
                        }
                    }, [activeTab, healthLogs, healthProfile]);

                    return (
                        <div className="h-full flex flex-col fade-in">
                            <div className="flex justify-between items-center mb-6 shrink-0">
                                <h2 className="text-2xl font-serif font-bold text-white tracking-widest uppercase drop-shadow-md">Health & Fitness Engine</h2>
                                <div className="flex gap-4">
                                    <button onClick={importBodyScan} className="glass-button px-4 py-2 rounded text-[10px] font-bold tracking-widest uppercase bg-purple-900/30 text-purple-400 border border-purple-500/30 hover:bg-purple-900/60 transition-colors">
                                        <i className="fas fa-camera mr-2"></i> Auto-Parse Scan
                                    </button>
                                    <div className="bg-black/40 border border-white/10 px-4 py-2 rounded">
                                        <span className="text-xs text-green-400 font-bold mr-2"><i className="fas fa-fire mr-1"></i> Net Deficit: {currentDeficit.toFixed(0)} kcal</span>
                                        <span className="text-xs text-blue-400 font-bold"><i className="fas fa-utensils mr-1"></i> Intake: {totalIntake.toFixed(0)} kcal</span>
                                    </div>
                                </div>
                            </div>

                            <div className="flex gap-6 border-b border-white/10 mb-6 shrink-0">
                                <button onClick={() => setActiveTab('dashboard')} className={`pb-2 text-xs font-bold uppercase tracking-widest transition-all ${activeTab === 'dashboard' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-gray-500 hover:text-gray-300'}`}>Insights & Dashboard</button>
                                <button onClick={() => setActiveTab('intake')} className={`pb-2 text-xs font-bold uppercase tracking-widest transition-all ${activeTab === 'intake' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-gray-500 hover:text-gray-300'}`}>Log & Intake</button>
                                <button onClick={() => setActiveTab('food_camera')} className={`pb-2 text-xs font-bold uppercase tracking-widest transition-all ${activeTab === 'food_camera' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-gray-500 hover:text-gray-300'}`}>AI Food Scan</button>
                                <button onClick={() => setActiveTab('planning')} className={`pb-2 text-xs font-bold uppercase tracking-widest transition-all ${activeTab === 'planning' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-gray-500 hover:text-gray-300'}`}>Plans & Programs</button>
                            </div>

                            {activeTab === 'dashboard' && (() => {
                                const latestScan = healthLogs.filter(l => l.type === 'body_scan').sort((a,b) => new Date(b.date) - new Date(a.date))[0];
                                return (
                                <div className="flex flex-col gap-6 overflow-y-auto">
                                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4 shrink-0">
                                        <div className="glass-panel p-4 flex flex-col items-center justify-center">
                                            <div className="text-[10px] text-gray-500 uppercase tracking-widest mb-1">Current Weight</div>
                                            <div className="text-3xl font-bold text-white">{healthProfile?.weight || '--'} kg</div>
                                        </div>
                                        <div className="glass-panel p-4 flex flex-col items-center justify-center">
                                            <div className="text-[10px] text-gray-500 uppercase tracking-widest mb-1">Target Daily Intake</div>
                                            <div className="text-3xl font-bold text-blue-400">{targetKcal.toFixed(0)} kcal</div>
                                        </div>
                                        <div className="glass-panel p-4 flex flex-col items-center justify-center">
                                            <div className="text-[10px] text-gray-500 uppercase tracking-widest mb-1">Today's Caloric Deficit</div>
                                            <div className="text-3xl font-bold text-green-400">{currentDeficit.toFixed(0)} kcal</div>
                                        </div>
                                        <div className="glass-panel p-4 flex flex-col items-center justify-center">
                                            <div className="text-[10px] text-gray-500 uppercase tracking-widest mb-1">Weekly Projected Change</div>
                                            <div className="text-3xl font-bold text-yellow-400">{((currentDeficit * 7) / 7700).toFixed(2)} kg</div>
                                        </div>
                                    </div>
                                    
                                    {latestScan && (
                                        <div className="glass-panel p-4 shrink-0 border-t-2 border-t-purple-500/50">
                                            <h3 className="text-[10px] text-gray-400 uppercase tracking-widest mb-4">Latest Body Scan ({latestScan.date})</h3>
                                            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                                                <div className="flex flex-col"><span className="text-xs text-gray-500 uppercase">Weight</span><span className="text-xl font-bold text-white">{latestScan.data.weight || '--'} kg</span></div>
                                                <div className="flex flex-col"><span className="text-xs text-gray-500 uppercase">Body Fat</span><span className="text-xl font-bold text-red-400">{latestScan.data.body_fat || '--'}%</span></div>
                                                <div className="flex flex-col"><span className="text-xs text-gray-500 uppercase">Muscle</span><span className="text-xl font-bold text-green-400">{latestScan.data.muscle_mass || '--'} kg</span></div>
                                                <div className="flex flex-col"><span className="text-xs text-gray-500 uppercase">Water</span><span className="text-xl font-bold text-blue-400">{latestScan.data.water || '--'}%</span></div>
                                                <div className="flex flex-col"><span className="text-xs text-gray-500 uppercase">Score</span><span className="text-xl font-bold text-yellow-400">{latestScan.data.body_score || '--'}</span></div>
                                            </div>
                                        </div>
                                    )}

                                    <div className="glass-panel p-4 flex-grow relative" style={{minHeight: '400px'}}>
                                        <h3 className="text-[10px] text-gray-400 uppercase tracking-widest mb-4">Weight & Deficit Projection</h3>
                                        <canvas ref={chartRef}></canvas>
                                    </div>
                                </div>
                                );
                            })()}

                            {activeTab === 'intake' && (
                                <div className="flex flex-col lg:flex-row gap-6 h-full overflow-hidden">
                                    <div className="w-full lg:w-1/2 flex flex-col gap-4 overflow-y-auto custom-scrollbar">
                                        
                                        {/* Advanced Nutrition Sub-Nav */}
                                        <div className="flex gap-2 glass-panel p-2 shrink-0">
                                            <button onClick={() => setIntakeTab('diary')} className={`flex-1 py-1.5 rounded text-[10px] font-bold tracking-widest uppercase transition ${intakeTab === 'diary' ? 'bg-blue-600 text-white' : 'bg-white/10 text-gray-400 hover:bg-white/20'}`}>Log Diary</button>
                                            <button onClick={() => setIntakeTab('ingredients')} className={`flex-1 py-1.5 rounded text-[10px] font-bold tracking-widest uppercase transition ${intakeTab === 'ingredients' ? 'bg-blue-600 text-white' : 'bg-white/10 text-gray-400 hover:bg-white/20'}`}>Ingredients DB</button>
                                            <button onClick={() => setIntakeTab('builder')} className={`flex-1 py-1.5 rounded text-[10px] font-bold tracking-widest uppercase transition ${intakeTab === 'builder' ? 'bg-blue-600 text-white' : 'bg-white/10 text-gray-400 hover:bg-white/20'}`}>Recipe Builder</button>
                                        </div>
                                        
                                        {intakeTab === 'diary' && (
                                            <div className="glass-panel p-4 flex flex-col gap-3 fade-in">
                                                <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest border-b border-white/10 pb-1">Log Intake (Amount in Grams)</h3>
                                                <div className="flex gap-2">
                                                    <select className="glass-input p-2 rounded text-xs flex-grow" value={diarySelect} onChange={e => {
                                                        setDiarySelect(e.target.value);
                                                        setDiaryIsRecipe(e.target.options[e.target.selectedIndex].dataset.type === 'recipe');
                                                    }}>
                                                        <option value="">Select Item...</option>
                                                        <optgroup label="Ingredients / Standard Foods">
                                                            {ingredients.map(i => <option key={`ing-${i.id}`} value={i.name} data-type="ing">{i.is_iranian ? '🍽️' : '🥩'} {i.name}</option>)}
                                                        </optgroup>
                                                        <optgroup label="Composite Recipes">
                                                            {compositeFoods.map(c => <option key={`rec-${c.id}`} value={c.name} data-type="recipe">🍲 {c.name}</option>)}
                                                        </optgroup>
                                                    </select>
                                                </div>
                                                <div className="flex gap-2">
                                                    <input type="number" placeholder="Amount (grams/ml)" className="glass-input p-2 rounded text-xs flex-grow" value={diaryAmount} onChange={e=>setDiaryAmount(e.target.value)} />
                                                    <button onClick={logDiaryEntry} className="glass-button px-6 py-2 rounded text-[11px] font-bold tracking-widest text-green-300 uppercase border border-green-500/30 bg-green-900/30 hover:bg-green-600 hover:text-white transition">Log</button>
                                                </div>
                                                
                                                <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest border-b border-white/10 pb-1 mt-4">Log Exercise</h3>
                                                <input type="text" placeholder="Activity Name..." className="glass-input p-2 rounded text-xs" value={exName} onChange={e=>setExName(e.target.value)} />
                                                <div className="flex gap-2">
                                                    <input type="number" placeholder="Duration (m)" className="glass-input p-2 rounded text-xs w-1/2" value={exDur} onChange={e=>setExDur(e.target.value)} />
                                                    <input type="number" placeholder="Kcal Burned" className="glass-input p-2 rounded text-xs w-1/2" value={exKcal} onChange={e=>setExKcal(e.target.value)} />
                                                </div>
                                                <button onClick={saveCustomEx} className="glass-button w-full py-2 rounded text-[11px] font-bold tracking-widest text-purple-300 uppercase shadow-lg border border-purple-500/30 bg-purple-900/30 hover:bg-purple-600 hover:text-white transition">Log Exercise</button>
                                            </div>
                                        )}
                                        
                                        {intakeTab === 'ingredients' && (
                                            <div className="glass-panel p-4 flex flex-col gap-3 fade-in">
                                                <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest border-b border-white/10 pb-1">Add New Ingredient to Database</h3>
                                                <input type="text" placeholder="Ingredient Name" className="glass-input p-2 rounded text-xs" value={ingName} onChange={e=>setIngName(e.target.value)} />
                                                <div className="grid grid-cols-2 gap-2">
                                                    <input type="number" placeholder="Kcal / 100g" className="glass-input p-2 rounded text-xs" value={ingKcal} onChange={e=>setIngKcal(e.target.value)} />
                                                    <input type="number" placeholder="Protein (g) / 100g" className="glass-input p-2 rounded text-xs" value={ingPro} onChange={e=>setIngPro(e.target.value)} />
                                                    <input type="number" placeholder="Fat (g) / 100g" className="glass-input p-2 rounded text-xs" value={ingFat} onChange={e=>setIngFat(e.target.value)} />
                                                    <input type="number" placeholder="Carbs (g) / 100g" className="glass-input p-2 rounded text-xs" value={ingCarbs} onChange={e=>setIngCarbs(e.target.value)} />
                                                </div>
                                                <label className="flex items-center gap-2 text-xs text-gray-300 cursor-pointer p-2 bg-black/40 rounded border border-white/10">
                                                    <input type="checkbox" className="w-4 h-4 accent-blue-500" checked={isIranian} onChange={e=>setIsIranian(e.target.checked)} />
                                                    Flag as Persian Culture Food 🍽️
                                                </label>
                                                <button onClick={saveIngredient} className="glass-button w-full py-2 rounded text-[11px] font-bold tracking-widest text-blue-300 uppercase border border-blue-500/30 bg-blue-900/30 hover:bg-blue-600 hover:text-white transition">Save Ingredient</button>
                                            </div>
                                        )}
                                        
                                        {intakeTab === 'builder' && (
                                            <div className="glass-panel p-4 flex flex-col gap-3 fade-in">
                                                <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest border-b border-white/10 pb-1">Composite Recipe Builder</h3>
                                                <input type="text" placeholder="Recipe Name (e.g., Kebab Koobideh)" className="glass-input p-2 rounded text-xs" value={recName} onChange={e=>setRecName(e.target.value)} />
                                                <div className="flex flex-col gap-1">
                                                    <label className="text-[10px] text-gray-400 uppercase tracking-widest">Instructions</label>
                                                    <textarea placeholder="Cooking instructions..." className="glass-input p-2 rounded text-xs h-20" value={recInstructions} onChange={e=>setRecInstructions(e.target.value)}></textarea>
                                                </div>
                                                <div className="grid grid-cols-3 gap-2">
                                                    <input type="number" placeholder="Prep Time (min)" className="glass-input p-2 rounded text-xs" value={recPrepTime} onChange={e=>setRecPrepTime(e.target.value)} />
                                                    <input type="number" placeholder="Cook Time (min)" className="glass-input p-2 rounded text-xs" value={recCookTime} onChange={e=>setRecCookTime(e.target.value)} />
                                                    <input type="number" placeholder="Servings" className="glass-input p-2 rounded text-xs" value={recServings} onChange={e=>setRecServings(e.target.value)} />
                                                </div>
                                                
                                                <div className="flex gap-2 p-2 bg-black/40 rounded border border-white/10 items-center">
                                                    <select className="glass-input p-2 rounded text-xs flex-grow" value={partSelect} onChange={e=>setPartSelect(e.target.value)}>
                                                        <option value="">Select Ingredient...</option>
                                                        {ingredients.map(i => <option key={i.id} value={i.id}>{i.name}</option>)}
                                                    </select>
                                                    <input type="number" placeholder="Grams" className="glass-input p-2 rounded text-xs w-20" value={partGrams} onChange={e=>setPartGrams(e.target.value)} />
                                                    <button onClick={() => {
                                                        if(!partSelect) return;
                                                        const ing = ingredients.find(i => i.id === parseInt(partSelect));
                                                        if(ing) setRecParts([...recParts, {ingredient_id: ing.id, name: ing.name, amount_grams: parseFloat(partGrams)||100}]);
                                                        setPartSelect(""); setPartGrams(100);
                                                    }} className="glass-button px-3 py-1.5 rounded text-xs text-white bg-blue-600 hover:bg-blue-500"><i className="fas fa-plus"></i></button>
                                                </div>
                                                
                                                <div className="flex flex-col gap-1 max-h-32 overflow-y-auto">
                                                    {recParts.map((p, idx) => (
                                                        <div key={idx} className="flex justify-between items-center text-xs p-2 bg-white/5 rounded border border-white/5">
                                                            <span className="text-gray-300">{p.name}</span>
                                                            <div className="flex items-center gap-3">
                                                                <span className="font-mono text-blue-400">{p.amount_grams}g</span>
                                                                <i onClick={() => setRecParts(recParts.filter((_, i) => i !== idx))} className="fas fa-times text-red-500 cursor-pointer"></i>
                                                            </div>
                                                        </div>
                                                    ))}
                                                    {recParts.length === 0 && <span className="text-xs text-gray-500 italic text-center py-2">No ingredients added yet.</span>}
                                                </div>
                                                
                                                <button onClick={saveRecipe} disabled={recParts.length === 0 || !recName} className="glass-button w-full py-2 rounded text-[11px] font-bold tracking-widest text-yellow-300 uppercase border border-yellow-500/30 bg-yellow-900/30 hover:bg-yellow-600 hover:text-white transition disabled:opacity-50">Save Recipe</button>
                                            </div>
                                        )}
                                    </div>
                                    
                                    <div className="flex-grow flex flex-col gap-4 overflow-hidden w-full lg:w-1/2">
                                        <div className="glass-panel flex-grow flex flex-col p-4 overflow-y-auto custom-scrollbar">
                                            <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-2 border-b border-white/10 pb-1">Today's Logs</h3>
                                            <div className="flex flex-col gap-2">
                                                {todayLogs.map((l, i) => (
                                                    <div key={i} className="flex justify-between items-center p-3 bg-white/5 border border-white/10 rounded">
                                                        <div className="flex items-center gap-3">
                                                            {l.type === 'food' ? <i className="fas fa-hamburger text-blue-400"></i> : <i className="fas fa-running text-purple-400"></i>}
                                                            <div className="flex flex-col">
                                                                <span className="text-sm font-bold text-white">{l.data.name}</span>
                                                                <span className="text-[10px] text-gray-500 uppercase tracking-widest">
                                                                    {l.type === 'food' ? `${l.data.amount_grams ? l.data.amount_grams + 'g • ' : ''}${l.data.protein ? Math.round(l.data.protein) + 'g Pro' : '0g Pro'}` : `${l.data.duration || 0} mins`}
                                                                </span>
                                                            </div>
                                                        </div>
                                                        <div className="flex items-center gap-3">
                                                            <div className={`font-mono font-bold ${l.type === 'food' ? 'text-blue-400' : 'text-purple-400'}`}>
                                                                {l.type === 'food' ? '+' : '-'}{Math.round(l.type === 'food' ? l.data.kcal : l.data.kcal_burn)}
                                                            </div>
                                                            <i onClick={() => backend.request(JSON.stringify({action: 'manage_health', sub: 'delete_log', id: l.id})).then(res=>setHealthLogs(JSON.parse(res).health_logs))} className="fas fa-trash text-red-500 opacity-50 hover:opacity-100 cursor-pointer"></i>
                                                        </div>
                                                    </div>
                                                ))}
                                                {todayLogs.length === 0 && <div className="text-center text-gray-500 py-8 text-sm uppercase tracking-widest">No entries today</div>}
                                            </div>
                                        </div>
                                        
                                        {intakeTab === 'ingredients' && (
                                            <div className="glass-panel h-1/2 flex flex-col p-4 overflow-y-auto custom-scrollbar">
                                                <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-2 border-b border-white/10 pb-1">Database Preview ({ingredients.length})</h3>
                                                <div className="flex flex-col gap-1">
                                                    {ingredients.map(i => (
                                                        <div key={i.id} className="flex justify-between items-center text-xs p-2 bg-black/40 rounded border border-white/5">
                                                            <span>{i.is_iranian ? '🍽️' : '🥩'} {i.name}</span>
                                                            <div className="flex items-center gap-3">
                                                                <span className="text-blue-400 font-mono">{i.kcal} kcal</span>
                                                                <i onClick={() => backend.request(JSON.stringify({action: 'manage_nutrition', sub: 'delete_ingredient', id: i.id})).then(res=>{const d=JSON.parse(res);setIngredients(d.ingredients);setCompositeFoods(d.composite_foods);})} className="fas fa-trash text-red-500 cursor-pointer opacity-50 hover:opacity-100"></i>
                                                            </div>
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        )}
                                        
                                        {intakeTab === 'builder' && (
                                            <div className="glass-panel h-1/2 flex flex-col p-4 overflow-y-auto custom-scrollbar">
                                                <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-2 border-b border-white/10 pb-1">Saved Recipes ({compositeFoods.length})</h3>
                                                <div className="flex flex-col gap-2">
                                                    {compositeFoods.map(c => (
                                                        <div key={c.id} className="flex flex-col p-3 bg-black/40 rounded border border-white/5 gap-2">
                                                            <div className="flex justify-between items-center border-b border-white/5 pb-1">
                                                                <span className="font-bold text-white text-sm">🍲 {c.name}</span>
                                                                <div className="flex items-center gap-3">
                                                                    <span className="text-xs text-blue-400 font-mono font-bold">{Math.round(c.kcal)} kcal | {Math.round(c.protein)}g Pro | {Math.round(c.fat)}g Fat | {Math.round(c.carbs)}g Carb | {c.servings} servings</span>
                                                                    <i onClick={() => backend.request(JSON.stringify({action: 'manage_nutrition', sub: 'delete_composite', id: c.id})).then(res=>{const d=JSON.parse(res);setIngredients(d.ingredients);setCompositeFoods(d.composite_foods);})} className="fas fa-trash text-red-500 cursor-pointer opacity-50 hover:opacity-100"></i>
                                                                </div>
                                                            </div>
                                                            {c.instructions && (
                                                                <div className="text-[9px] text-gray-400 italic mb-1 px-2 bg-black/30 rounded p-1">{c.instructions}</div>
                                                            )}
                                                            <div className="flex flex-wrap gap-1">
                                                                {c.parts.map((p, idx) => (
                                                                    <span key={idx} className="text-[9px] bg-white/10 text-gray-300 px-2 py-0.5 rounded-full">{p.amount_grams}g {p.name}</span>
                                                                ))}
                                                            </div>
                                                            <div className="text-[9px] text-gray-500 flex gap-4">
                                                                {c.prep_time_min > 0 && <span>⏱️ Prep: {c.prep_time_min}min</span>}
                                                                {c.cook_time_min > 0 && <span>🔥 Cook: {c.cook_time_min}min</span>}
                                                            </div>
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            )}

                             <HealthFoodCamera active={activeTab === 'food_camera'} backend={backend} logEntry={logEntry} todayFood={todayFood} />

                             {activeTab === 'planning' && (
                                <div className="flex flex-col lg:flex-row gap-6 h-full overflow-hidden">
                                    <div className="w-full lg:w-1/3 flex flex-col gap-4">
                                        <div className="glass-panel p-4 flex flex-col gap-3">
                                            <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest border-b border-white/10 pb-1">Create Health Plan</h3>
                                            <select className="glass-input p-2 rounded text-xs" value={planType} onChange={e=>setPlanType(e.target.value)}>
                                                <option>Diet</option>
                                                <option>Exercise</option>
                                            </select>
                                            <input type="text" placeholder="Plan Title..." className="glass-input p-2 rounded text-xs font-bold" value={planTitle} onChange={e=>setPlanTitle(e.target.value)} />
                                            <textarea placeholder="Write schedule, macros, or sets/reps here..." className="glass-input p-2 rounded text-xs h-40" value={planDetails} onChange={e=>setPlanDetails(e.target.value)}></textarea>
                                            <button onClick={savePlan} className="glass-button w-full py-2 rounded text-[11px] font-bold tracking-widest text-green-300 uppercase shadow-lg border-green-500/30">Save Plan</button>
                                        </div>
                                    </div>
                                    <div className="glass-panel flex-grow p-4 overflow-y-auto w-full lg:w-2/3 flex flex-col gap-4">
                                        <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest border-b border-white/10 pb-1">Saved Plans</h3>
                                        {healthPlans && healthPlans.map(p => (
                                            <div key={p.id} className="bg-white/5 border border-white/10 rounded-lg p-4 relative group">
                                                <div className="flex items-center gap-2 mb-2">
                                                    <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded ${p.type === 'Diet' ? 'bg-blue-900/50 text-blue-400' : 'bg-purple-900/50 text-purple-400'}`}>{p.type}</span>
                                                    <span className="font-bold text-white text-lg">{p.title}</span>
                                                    <i onClick={() => { backend.request(JSON.stringify({action: 'manage_health', sub: 'delete_plan', id: p.id})); }} className="fas fa-trash text-red-500 absolute top-4 right-4 opacity-0 group-hover:opacity-100 cursor-pointer hover:scale-110 transition"></i>
                                                </div>
                                                <pre className="text-sm text-gray-300 font-mono whitespace-pre-wrap">{p.details}</pre>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    );
                };
