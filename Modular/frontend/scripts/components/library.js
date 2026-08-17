        // ==========================================

            const QuizEngineView = ({ quizzes, backend, refreshQuizzes, flatGoals, courseColors }) => {
            const [activeTab, setActiveTab] = useState('library'); const [qTitle, setQTitle] = useState(""); const [qCourse, setQCourse] = useState(""); const [qFolder, setQFolder] = useState("Uncategorized"); const [qColor, setQColor] = useState("#3b82f6"); const [qJson, setQJson] = useState('[\n  {"q": "Difference between Process and Thread?", "opts": ["Memory Isolation", "No Difference"], "ans": 0}\n]'); const [activeQuiz, setActiveQuiz] = useState(null); const [qIndex, setQIndex] = useState(0); const [score, setScore] = useState(0); const [selectedOpt, setSelectedOpt] = useState(null);

            useEffect(() => { if (qCourse && courseColors && courseColors[qCourse]) setQColor(courseColors[qCourse]); }, [qCourse, courseColors]);

            const parsedQuiz = useMemo(() => { if (!activeQuiz) return null; try { return JSON.parse(activeQuiz.json); } catch { return []; } }, [activeQuiz]);
            const addQuiz = () => { backend.request(JSON.stringify({action: 'manage_quiz', sub: 'add', title: qTitle || "New Quiz", course: qCourse || "General", folder: qFolder, color: qColor, json: qJson})).then(res => { refreshQuizzes(JSON.parse(res).quizzes); setQTitle(""); }); };
            const handleNext = () => { if (selectedOpt === parsedQuiz[qIndex].ans) setScore(s => s + 1); setQIndex(i => i + 1); setSelectedOpt(null); };

            return (
                <div className="flex flex-col h-full fade-in bg-gray-900/50">
                    <div className="flex justify-between items-center mb-6 shrink-0"><h2 className="text-2xl font-serif font-bold text-white tracking-widest uppercase drop-shadow-md">Quiz Engine</h2></div>
                    <div className="flex gap-6 border-b border-white/10 mb-6 shrink-0">
                        <button onClick={() => setActiveTab('library')} className={`pb-2 text-xs font-bold uppercase tracking-widest transition-all ${activeTab === 'library' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-gray-500 hover:text-gray-300'}`}>Library & Import</button>
                        <button onClick={() => setActiveTab('study')} className={`pb-2 text-xs font-bold uppercase tracking-widest transition-all ${activeTab === 'study' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-gray-500 hover:text-gray-300'}`}>Active Quiz</button>
                    </div>

                    {activeTab === 'library' && (
                        <div className="flex flex-col lg:flex-row gap-6 h-full overflow-hidden">
                            <div className="w-full lg:w-1/2 flex flex-col gap-4">
                                <div className="glass-panel p-4 flex flex-col gap-2">
                                    <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-2 border-b border-white/10 pb-1">Import JSON Quiz</h3>
                                    <div className="flex gap-2">
                                        <select className="glass-input p-2 rounded text-xs flex-grow" value={qCourse} onChange={e=>setQCourse(e.target.value)}><option value="">Goal / Course...</option>{flatGoals.map(c=><option key={c} value={c}>{c}</option>)}</select>
                                        <input type="text" placeholder="Folder..." value={qFolder} onChange={e=>setQFolder(e.target.value)} className="glass-input p-2 rounded text-xs w-32" />
                                        <input type="color" value={qColor} onChange={e=>setQColor(e.target.value)} className="w-8 h-8 rounded cursor-pointer border-0 p-0" />
                                    </div>
                                    <input type="text" placeholder="Quiz Title" value={qTitle} onChange={e=>setQTitle(e.target.value)} className="glass-input p-2 rounded text-xs" />
                                    <textarea value={qJson} onChange={e=>setQJson(e.target.value)} className="glass-input p-2 rounded text-xs font-mono h-24"></textarea>
                                    <button onClick={addQuiz} className="glass-button w-full py-2 rounded text-[11px] font-bold tracking-widest text-green-300 uppercase shadow-lg">Save JSON Quiz</button>
                                </div>
                            </div>
                            <div className="glass-panel flex-grow flex flex-col p-4 overflow-y-auto w-full lg:w-1/2">
                                <h3 className="text-gray-300 text-[10px] font-bold tracking-widest uppercase mb-4 border-b border-white/10 pb-1">SAVED QUIZZES</h3>
                                <div className="flex flex-col gap-2">
                                {quizzes && quizzes.map(q => (
                                        <div key={q.id} className="flex items-center gap-3 p-3 bg-white/5 hover:bg-white/10 rounded cursor-pointer border border-white/10 transition group" onClick={() => {setActiveQuiz(q); setQIndex(0); setScore(0); setActiveTab('study');}}>
                                            <div className="w-3 h-3 rounded-full" style={{backgroundColor: courseColors[q.course] || q.color}}></div>
                                            <div className="flex flex-col flex-grow">
                                                <span className="text-[10px] text-gray-500 font-bold tracking-wider uppercase">{q.folder} / {q.course}</span>
                                                <span className="text-sm font-bold text-gray-200">{q.title}</span>
                                            </div>
                                            <i onClick={(e) => {e.stopPropagation(); backend.request(JSON.stringify({action: 'manage_quiz', sub: 'delete', id: q.id})).then(res => refreshQuizzes(JSON.parse(res).quizzes));}} className="fas fa-trash text-red-500 opacity-0 group-hover:opacity-100 hover:scale-110 transition"></i>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    )}

                    {activeTab === 'study' && (
                        <div className="flex-grow glass-panel p-8 flex flex-col justify-center items-center text-center overflow-y-auto relative">
                            {parsedQuiz ? (
                                qIndex < parsedQuiz.length ? (
                                    <div className="w-full max-w-lg">
                                        <div className="absolute top-4 left-4 text-xs font-mono text-gray-500">Q {qIndex + 1}/{parsedQuiz.length}</div>
                                        <h3 className="text-xl font-serif text-white mb-8 leading-relaxed">{parsedQuiz[qIndex].q}</h3>
                                        <div className="flex flex-col gap-3 w-full text-left">
                                            {parsedQuiz[qIndex].opts.map((opt, i) => (
                                                <label key={i} className={`flex items-center gap-3 p-4 rounded-lg border transition cursor-pointer ${selectedOpt === i ? 'bg-blue-600/30 border-blue-400' : 'border-white/10 bg-black/30 hover:bg-white/10'}`}>
                                                    <input type="radio" name="quiz_opt" checked={selectedOpt === i} onChange={() => setSelectedOpt(i)} className="w-4 h-4 accent-blue-500" />
                                                    <span className="text-sm text-gray-200">{opt}</span>
                                                </label>
                                            ))}
                                        </div>
                                        <button onClick={handleNext} disabled={selectedOpt === null} className="mt-8 glass-button px-8 py-3 rounded text-[11px] font-bold tracking-widest text-white uppercase bg-blue-600/30 border-blue-500/50 hover:bg-blue-600 disabled:opacity-50 transition">NEXT</button>
                                    </div>
                                ) : (
                                    <div className="flex flex-col items-center">
                                        <h2 className="text-3xl font-bold text-white mb-4">Quiz Complete!</h2>
                                        <p className="text-xl text-green-400 font-mono">Score: {score} / {parsedQuiz.length}</p>
                                        <button onClick={() => {setQIndex(0); setScore(0);}} className="mt-8 glass-button px-8 py-3 rounded text-[11px] font-bold tracking-widest text-white uppercase bg-blue-600/30 border-blue-500/50 hover:bg-blue-600">Restart Quiz</button>
                                    </div>
                                )
                            ) : (
                                <div className="text-gray-500 font-bold uppercase tracking-widest flex flex-col items-center gap-4"><i className="fas fa-book-open text-4xl opacity-50"></i>Select a Quiz from the Library</div>
                            )}
                        </div>
                    )}
                </div>
            );
        };
const FlashcardsView = ({ flashcards, backend, refreshCards, flatGoals, courseColors }) => {
            const [activeTab, setActiveTab] = useState('library'); 
            const [isFlipped, setIsFlipped] = useState(false); 
            const [currentIndex, setCurrentIndex] = useState(0);
            const [f, setF] = useState(""); 
            const [b, setB] = useState(""); 
            const [c, setC] = useState(""); 
            const [folder, setFolder] = useState("Uncategorized"); 
            const [color, setColor] = useState("#3b82f6");
            
            const activeDeckCards = flashcards; 
            const card = activeDeckCards && activeDeckCards.length > 0 ? activeDeckCards[currentIndex] : null;

            useEffect(() => { 
                if (c && courseColors && courseColors[c]) setColor(courseColors[c]); 
            }, [c, courseColors]);

            const addCard = () => { 
                backend.request(JSON.stringify({action: 'manage_flashcard', sub: 'add', front: f, back: b, deck: "Main", course: c || "General", folder: folder, color: color})).then(res => { 
                    refreshCards(JSON.parse(res).flashcards); setF(""); setB(""); 
                }); 
            };
            const nextCard = () => { 
                setIsFlipped(false); setTimeout(() => setCurrentIndex((currentIndex + 1) % activeDeckCards.length), 300); 
            };
            const delCard = (id) => { 
                backend.request(JSON.stringify({action: 'manage_flashcard', sub: 'delete', id: id})).then(res => { 
                    refreshCards(JSON.parse(res).flashcards); setIsFlipped(false); setCurrentIndex(0); 
                }); 
            };

            return (
                <div className="flex flex-col h-full fade-in bg-gray-900/50">
                    <div className="flex justify-between items-center mb-6 shrink-0">
                        <h2 className="text-2xl font-serif font-bold text-white tracking-widest uppercase drop-shadow-md">Flashcards</h2>
                    </div>
                    <div className="flex gap-6 border-b border-white/10 mb-6 shrink-0">
                        <button onClick={() => setActiveTab('library')} className={`pb-2 text-xs font-bold uppercase tracking-widest transition-all ${activeTab === 'library' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-gray-500 hover:text-gray-300'}`}>Library & Create</button>
                        <button onClick={() => setActiveTab('study')} className={`pb-2 text-xs font-bold uppercase tracking-widest transition-all ${activeTab === 'study' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-gray-500 hover:text-gray-300'}`}>Review Mode</button>
                    </div>

                    {activeTab === 'library' && (
                        <div className="flex flex-col gap-6 h-full overflow-hidden">
                            <div className="glass-panel p-4 rounded-xl flex flex-col gap-3 shrink-0">
                                <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest border-b border-white/10 pb-1">Create Flashcard</h3>
                                <div className="flex flex-wrap sm:flex-nowrap gap-2">
                                    <select className="glass-input px-3 py-2 rounded text-xs font-bold w-full sm:w-48" value={c} onChange={e=>setC(e.target.value)}>
                                        <option value="">Goal / Course...</option>
                                        {flatGoals.map(g=><option key={g} value={g}>{g}</option>)}
                                    </select>
                                    <input type="text" placeholder="Folder..." value={folder} onChange={e=>setFolder(e.target.value)} className="glass-input px-3 py-2 rounded text-xs font-bold w-32" />
                                    <input type="color" value={color} onChange={e=>setColor(e.target.value)} className="w-8 h-8 rounded cursor-pointer border-0 p-0 self-center" />
                                </div>
                                <div className="flex flex-wrap sm:flex-nowrap gap-2">
                                    <input type="text" placeholder="FRONT..." className="glass-input flex-grow px-4 py-2 rounded text-sm min-w-[150px]" value={f} onChange={e=>setF(e.target.value)} />
                                    <input type="text" placeholder="BACK..." className="glass-input flex-grow px-4 py-2 rounded text-sm min-w-[150px]" value={b} onChange={e=>setB(e.target.value)} />
                                    <button onClick={addCard} className="glass-button px-6 py-2 rounded text-xs font-bold tracking-widest text-white uppercase bg-blue-600/30 border-blue-500/50 w-full sm:w-auto">ADD</button>
                                </div>
                            </div>
                            
                            <div className="glass-panel flex-grow p-4 overflow-y-auto">
                                <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-4 border-b border-white/10 pb-1">ALL CARDS</h3>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                    {flashcards && flashcards.map(cardItem => (
                                        <div key={cardItem.id} className="flex flex-col p-3 bg-white/5 border border-white/10 rounded group relative">
                                            <div className="flex items-center gap-2 mb-2">
                                                <div className="w-2 h-2 rounded-full" style={{backgroundColor: courseColors && courseColors[cardItem.course] ? courseColors[cardItem.course] : cardItem.color}}></div>
                                                <span className="text-[9px] text-gray-500 font-bold uppercase tracking-wider">{cardItem.folder} / {cardItem.course}</span>
                                                <i onClick={() => delCard(cardItem.id)} className="fas fa-trash text-red-500 ml-auto opacity-0 group-hover:opacity-100 cursor-pointer hover:scale-110 transition"></i>
                                            </div>
                                            <div className="text-xs font-bold text-white truncate mb-1">F: {cardItem.front}</div>
                                            <div className="text-[10px] text-gray-400 truncate">B: {cardItem.back}</div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    )}

                    {activeTab === 'study' && (
                        <div className="flex-grow flex flex-col items-center justify-center perspective-1000 p-4 relative">
                            {card ? (
                                <div className={`relative w-full max-w-2xl h-64 sm:h-80 cursor-pointer transition-all duration-700 transform-style-3d ${isFlipped ? 'rotate-y-180' : ''}`} onClick={() => setIsFlipped(!isFlipped)}>
                                    <div className="absolute inset-0 glass-panel rounded-2xl flex flex-col justify-center items-center p-8 backface-hidden shadow-[0_20px_50px_rgba(0,0,0,0.5)] border-t-2" style={{borderTopColor: courseColors && courseColors[card.course] ? courseColors[card.course] : card.color}}>
                                        <span className="absolute top-4 left-4 text-[10px] font-bold tracking-widest text-gray-500 uppercase">{card.folder} / {card.course}</span>
                                        <span className="absolute bottom-4 left-4 text-[10px] font-bold tracking-widest text-gray-600 uppercase">FRONT</span>
                                        <h2 className="text-xl sm:text-3xl font-serif text-white tracking-wider text-center">{card.front}</h2>
                                    </div>
                                    <div className="absolute inset-0 glass-panel-darker rounded-2xl flex flex-col justify-center items-center p-8 backface-hidden rotate-y-180 shadow-[0_20px_50px_rgba(0,0,0,0.5)] border-b-2 border-b-green-500/30 overflow-y-auto">
                                        <span className="absolute bottom-4 right-4 text-[10px] font-bold tracking-widest text-gray-600 uppercase">BACK</span>
                                        <p className="text-sm sm:text-lg text-gray-200 text-center leading-relaxed mt-4">{card.back}</p>
                                    </div>
                                </div>
                            ) : (
                                <div className="text-gray-500 font-bold uppercase flex flex-col items-center gap-4 tracking-widest"><i className="fas fa-layer-group text-4xl opacity-50"></i>No Flashcards Built Yet</div>
                            )}
                            {card && (
                                <div className="flex gap-4 mt-12 shrink-0">
                                    <button onClick={() => setIsFlipped(!isFlipped)} className="glass-button px-8 py-3 rounded-lg text-xs font-bold tracking-widest text-gray-300 uppercase shadow-lg transition">FLIP</button>
                                    <button onClick={nextCard} className="glass-button px-8 py-3 rounded-lg text-xs font-bold tracking-widest text-white uppercase bg-blue-600/30 border-blue-500/50 hover:bg-blue-600 shadow-lg transition">NEXT</button>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            );
        };
