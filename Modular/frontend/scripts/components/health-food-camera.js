        const HealthFoodCamera = ({ active, backend, logEntry, todayFood }) => {
            const [foodDetections, setFoodDetections] = useState([]);
            const [foodCameraActive, setFoodCameraActive] = useState(false);
            const [foodAnnotatedImage, setFoodAnnotatedImage] = useState("");
            const [foodScanError, setFoodScanError] = useState("");

            useEffect(() => {
                if (!foodCameraActive || !backend) return;

                let cancelled = false;
                const scan = () => {
                    backend.request(JSON.stringify({action: 'detect_food', use_vision_feed: true})).then(res => {
                        if (cancelled) return;
                        const data = JSON.parse(res);
                        if (data.error) {
                            setFoodScanError(data.error);
                            return;
                        }
                        setFoodScanError("");
                        setFoodDetections(data.detections || []);
                        if (data.annotated_image) {
                            setFoodAnnotatedImage(`data:image/jpeg;base64,${data.annotated_image}`);
                        }
                    });
                };

                scan();
                const intervalId = setInterval(scan, 1500);
                return () => {
                    cancelled = true;
                    clearInterval(intervalId);
                };
            }, [foodCameraActive, backend]);

            if (!active) return null;

            return (
                <div className="flex flex-col lg:flex-row gap-6 h-full overflow-hidden">
                    <div className="w-full lg:w-1/2 flex flex-col gap-4">
                        <div className="glass-panel p-4 flex flex-col gap-4">
                            <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest border-b border-white/10 pb-1">AI Food Camera</h3>
                            <p className="text-xs text-gray-400">Point camera at food to detect items and estimate calories</p>
                            
                            {!foodCameraActive ? (
                                <button onClick={() => setFoodCameraActive(true)} className="glass-button w-full py-3 rounded text-[11px] font-bold tracking-widest text-green-300 uppercase border border-green-500/30 bg-green-900/30 hover:bg-green-600 hover:text-white transition">
                                    <i className="fas fa-camera mr-2"></i> Start Food Scan
                                </button>
                            ) : (
                                <div className="flex flex-col gap-2">
                                    <div className="relative aspect-video bg-black/50 rounded-lg overflow-hidden border border-white/10">
                                        <img src={foodAnnotatedImage || "http://127.0.0.1:5050/video_feed"} className="w-full h-full object-cover" />
                                        {!foodAnnotatedImage && <div className="absolute inset-0 flex items-center justify-center bg-black/30"><span className="text-white font-bold">Warming up camera...</span></div>}
                                    </div>
                                    <div className="flex gap-2">
                                        <button onClick={() => { setFoodCameraActive(false); setFoodAnnotatedImage(""); }} className="glass-button w-full py-2 rounded text-[11px] font-bold tracking-widest text-red-300 uppercase border border-red-500/30 bg-red-900/30 hover:bg-red-600 hover:text-white transition">
                                            <i className="fas fa-stop mr-2"></i> Stop Camera
                                        </button>
                                    </div>
                                </div>
                            )}
                            {foodScanError && <div className="text-xs text-red-400 bg-red-950/40 border border-red-500/30 rounded p-2">{foodScanError}</div>}
                        </div>
                        
                        <div className="glass-panel p-4 flex flex-col gap-3">
                            <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest border-b border-white/10 pb-1">Detected Foods</h3>
                            {foodDetections.length === 0 ? (
                                <div className="text-center text-gray-500 py-8 text-xs">No food detected yet</div>
                            ) : (
                                <div className="flex flex-col gap-2 max-h-60 overflow-y-auto">
                                    {foodDetections.map((det, idx) => (
                                        <div key={idx} className="bg-black/30 p-3 rounded border border-white/5 flex flex-col gap-1">
                                            <div className="flex justify-between items-center">
                                                <span className="font-bold text-white text-sm">{det.food_type}</span>
                                                <span className="text-xs text-green-400 font-mono">{Math.round(det.confidence * 100)}%</span>
                                            </div>
                                            <div className="flex gap-4 text-[10px] text-gray-400">
                                                <span><i className="fas fa-fire mr-1"></i> ~{det.estimated_calories} kcal</span>
                                                <span><i className="fas fa-weight mr-1"></i> ~{det.estimated_weight_grams}g</span>
                                            </div>
                                            <div className="flex gap-2">
                                                <button onClick={() => { logEntry('food', {name: det.food_type, amount_grams: det.estimated_weight_grams || 100, kcal: det.estimated_calories, protein: 0}); }} className="glass-button px-3 py-1.5 rounded text-[10px] font-bold text-green-300 uppercase border border-green-500/30 bg-green-900/30 hover:bg-green-600 hover:text-white text-xs">Log Meal</button>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                    
                    <div className="glass-panel flex-grow p-4 overflow-y-auto w-full lg:w-1/2 flex flex-col gap-4">
                        <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest border-b border-white/10 pb-1">Today's Logged Meals</h3>
                        <div className="flex flex-col gap-2">
                            {todayFood.map((l, i) => (
                                <div key={i} className="flex justify-between items-center p-3 bg-white/5 border border-white/10 rounded">
                                    <div className="flex items-center gap-3">
                                        <i className="fas fa-hamburger text-blue-400"></i>
                                        <div className="flex flex-col">
                                            <span className="text-sm font-bold text-white">{l.data.name}</span>
                                            <span className="text-[10px] text-gray-500 uppercase tracking-widest">{l.data.amount_grams ? l.data.amount_grams + 'g' : ''} • {l.data.protein ? Math.round(l.data.protein) + 'g Pro' : '0g Pro'}</span>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-3">
                                        <div className="font-mono font-bold text-blue-400">+{Math.round(l.data.kcal)} kcal</div>
                                    </div>
                                </div>
                            ))}
                            {todayFood.length === 0 && <div className="text-center text-gray-500 py-8 text-sm uppercase tracking-widest">No meals logged today</div>}
                        </div>
                    </div>
                </div>
            );
        };
