const NotesView = ({ notes, backend, refreshNotes, flatGoals, courseColors }) => {
            const [activeNoteId, setActiveNoteId] = useState(null);
            const [title, setTitle] = useState("");
            const [content, setContent] = useState("");
            const [course, setCourse] = useState("");
            const [folder, setFolder] = useState("Uncategorized");
            const [color, setColor] = useState("#3b82f6");
            const [isFullscreen, setIsFullscreen] = useState(false);
            const textareaRef = useRef(null);

            useEffect(() => { 
                if (course && courseColors && courseColors[course]) setColor(courseColors[course]); 
            }, [course, courseColors]);

            const handleSave = () => {
                backend.request(JSON.stringify({action: 'manage_note', sub: 'save', id: activeNoteId, title: title || "Untitled Note", content, course: course || "General", folder: folder, color: color})).then(res => {
                    refreshNotes(JSON.parse(res).notes);
                });
            };

            const selectNote = (n) => { setActiveNoteId(n.id); setTitle(n.title); setContent(n.content); setCourse(n.course); setFolder(n.folder); setColor(n.color); setIsFullscreen(false); };
            const newNote = () => { setActiveNoteId(null); setTitle(""); setContent(""); setCourse(""); setFolder("Uncategorized"); setColor("#3b82f6"); setIsFullscreen(false); };

            const wrapText = (prefix, suffix = '') => {
                const el = textareaRef.current;
                if (!el) {
                    setContent(prev => prev + prefix + suffix);
                    return;
                }
                const start = el.selectionStart;
                const end = el.selectionEnd;
                const text = content || "";
                const selectedText = text.substring(start, end);
                const newText = text.substring(0, start) + prefix + selectedText + suffix + text.substring(end);
                setContent(newText);
                setTimeout(() => {
                    el.focus();
                    el.setSelectionRange(start + prefix.length, end + prefix.length);
                }, 0);
            };

            const exportFile = (type) => {
                let data, mime, ext;
                const parsedHTML = marked.parse(content || "*Nothing to preview.*");
                if (type === 'md') {
                    data = content; mime = "text/markdown"; ext = "md";
                } else if (type === 'html') {
                    data = `<!DOCTYPE html><html><head><title>${title}</title><meta charset="utf-8"><style>body{font-family:sans-serif;padding:2rem;color:#333;line-height:1.6;} blockquote{border-left:4px solid #ccc;padding-left:1rem;margin-left:0;} code{background:#eee;padding:0.2rem;border-radius:4px;} pre code{background:none;padding:0;}</style></head><body>${parsedHTML}</body></html>`;
                    mime = "text/html"; ext = "html";
                } else if (type === 'pdf') {
                    const win = window.open('', '', 'width=800,height=600');
                    win.document.write(`<!DOCTYPE html><html><head><title>${title}</title><style>body{font-family:sans-serif;padding:2rem;color:#000;line-height:1.6;} blockquote{border-left:4px solid #ccc;padding-left:1rem;margin-left:0;} code{background:#eee;padding:0.2rem;border-radius:4px;} pre code{background:none;padding:0;} @media print{ body{background:#fff;} }</style></head><body>${parsedHTML}</body></html>`);
                    win.document.close();
                    win.focus();
                    setTimeout(() => { win.print(); win.close(); }, 250);
                    return;
                }
                
                const blob = new Blob([data], {type: mime});
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `${title || 'Export'}.${ext}`;
                a.click();
                URL.revokeObjectURL(url);
            };

            return (
                <div className={`flex flex-col fade-in transition-all duration-300 ${isFullscreen ? 'fixed inset-0 z-[100] bg-[#050505] p-6' : 'h-full'}`}>
                    {!isFullscreen && (
                        <div className="flex justify-between items-center mb-6 shrink-0">
                            <h2 className="text-2xl font-serif font-bold text-white tracking-widest uppercase drop-shadow-md">Sophisticated Notes</h2>
                        </div>
                    )}
                    
                    <div className="flex flex-col md:flex-row gap-4 flex-grow overflow-hidden">
                        
                        {!isFullscreen && (
                            <div className="w-full md:w-1/4 glass-panel p-4 flex flex-col gap-2 overflow-y-auto">
                                <button onClick={newNote} className="glass-button w-full py-2 rounded text-[11px] font-bold tracking-widest text-green-300 uppercase shadow-lg mb-2 border border-green-500/30">+ New Note</button>
                                {notes && notes.map(n => (
                                    <div key={n.id} onClick={() => selectNote(n)} className={`p-3 rounded cursor-pointer border text-sm transition-all group relative ${activeNoteId === n.id ? 'bg-blue-600/30 border-blue-400 text-white' : 'bg-white/5 border-white/10 hover:bg-white/10 text-gray-300'}`}>
                                        <div className="flex items-center gap-2 mb-1">
                                            <div className="w-2 h-2 rounded-full" style={{backgroundColor: courseColors && courseColors[n.course] ? courseColors[n.course] : n.color}}></div>
                                            <div className="text-[9px] font-bold uppercase tracking-widest text-gray-500">{n.folder}</div>
                                        </div>
                                        <div className="font-bold truncate">{n.title}</div>
                                        <i onClick={(e) => {e.stopPropagation(); backend.request(JSON.stringify({action: 'manage_note', sub: 'delete', id: n.id})).then(res => refreshNotes(JSON.parse(res).notes));}} className="fas fa-trash text-red-500 absolute top-3 right-3 opacity-0 group-hover:opacity-100 hover:scale-110 transition"></i>
                                    </div>
                                ))}
                            </div>
                        )}

                        <div className={`glass-panel p-0 flex flex-col overflow-hidden ${isFullscreen ? 'w-1/2' : 'w-full md:w-1/2'}`}>
                            <div className="flex flex-col gap-2 p-3 border-b border-white/10 bg-black/40 shrink-0">
                                
                                {/* Meta Bar */}
                                <div className="flex flex-wrap gap-2 items-center">
                                    <input type="text" placeholder="Title..." className="glass-input px-3 py-1.5 rounded w-full sm:w-auto flex-grow font-bold text-white text-sm" value={title} onChange={e=>setTitle(e.target.value)} />
                                    <select className="glass-input px-2 py-1.5 rounded text-xs w-32" value={course} onChange={e=>setCourse(e.target.value)}><option value="">Goal / Course...</option>{flatGoals.map(g=><option key={g} value={g}>{g}</option>)}</select>
                                    <input type="text" placeholder="Folder..." className="glass-input px-2 py-1.5 rounded text-xs w-24" value={folder} onChange={e=>setFolder(e.target.value)} />
                                    <input type="color" value={color} onChange={e=>setColor(e.target.value)} className="w-7 h-7 rounded cursor-pointer border-0 p-0" />
                                    <button onClick={handleSave} className="glass-button px-6 py-1.5 rounded font-bold text-white tracking-widest uppercase bg-blue-600/30 border-blue-500/50 hover:bg-blue-600 transition text-xs">Save</button>
                                    <button onClick={() => setIsFullscreen(!isFullscreen)} className="glass-button w-8 h-8 rounded flex items-center justify-center text-gray-300 hover:text-white transition" title="Toggle Fullscreen">
                                        <i className={`fas ${isFullscreen ? 'fa-compress' : 'fa-expand'}`}></i>
                                    </button>
                                </div>

                                {/* Sophisticated Toolbar */}
                                <div className="flex flex-wrap gap-1 items-center bg-black/50 p-1.5 rounded-lg border border-white/5 text-gray-300">
                                    <button onClick={() => wrapText('# ', '')} className="hover:bg-white/20 px-2 py-1 rounded text-xs font-bold transition">H1</button>
                                    <button onClick={() => wrapText('## ', '')} className="hover:bg-white/20 px-2 py-1 rounded text-xs font-bold transition">H2</button>
                                    <button onClick={() => wrapText('### ', '')} className="hover:bg-white/20 px-2 py-1 rounded text-xs font-bold transition">H3</button>
                                    <div className="w-px h-4 bg-white/20 mx-1"></div>
                                    <button onClick={() => wrapText('**', '**')} className="hover:bg-white/20 w-7 h-7 rounded transition flex items-center justify-center"><i className="fas fa-bold"></i></button>
                                    <button onClick={() => wrapText('*', '*')} className="hover:bg-white/20 w-7 h-7 rounded transition flex items-center justify-center"><i className="fas fa-italic"></i></button>
                                    <button onClick={() => wrapText('<u>', '</u>')} className="hover:bg-white/20 w-7 h-7 rounded transition flex items-center justify-center"><i className="fas fa-underline"></i></button>
                                    <button onClick={() => wrapText('~~', '~~')} className="hover:bg-white/20 w-7 h-7 rounded transition flex items-center justify-center"><i className="fas fa-strikethrough"></i></button>
                                    <div className="w-px h-4 bg-white/20 mx-1"></div>
                                    <button onClick={() => wrapText('<mark style="background-color: yellow; color: black; padding: 0 4px; border-radius: 2px;">', '</mark>')} className="hover:bg-yellow-500/30 text-yellow-400 w-7 h-7 rounded transition flex items-center justify-center" title="Highlight"><i className="fas fa-highlighter"></i></button>
                                    <button onClick={() => wrapText('<span style="color: #60a5fa;">', '</span>')} className="hover:bg-blue-500/30 text-blue-400 w-7 h-7 rounded transition flex items-center justify-center" title="Blue Text"><i className="fas fa-palette"></i></button>
                                    <button onClick={() => wrapText('<span style="color: #f87171;">', '</span>')} className="hover:bg-red-500/30 text-red-400 w-7 h-7 rounded transition flex items-center justify-center" title="Red Text"><i className="fas fa-palette"></i></button>
                                    <button onClick={() => wrapText('<span style="font-family: \'Courier New\', Courier, monospace;">', '</span>')} className="hover:bg-white/20 px-2 py-1 rounded text-xs font-serif transition" title="Font Change">Font</button>
                                    <div className="w-px h-4 bg-white/20 mx-1"></div>
                                    <button onClick={() => wrapText('![alt text](', ')')} className="hover:bg-white/20 w-7 h-7 rounded transition flex items-center justify-center" title="Add Image"><i className="fas fa-image"></i></button>
                                    <button onClick={() => wrapText('\n```\n', '\n```\n')} className="hover:bg-white/20 w-7 h-7 rounded transition flex items-center justify-center" title="Code Block"><i className="fas fa-code"></i></button>
                                    <div className="w-px h-4 bg-white/20 mx-1"></div>
                                    <button onClick={() => wrapText('\n<div style="background-color: rgba(59, 130, 246, 0.2); border-left: 4px solid #3b82f6; padding: 10px; margin: 10px 0; border-radius: 4px;">\n💡 <b>Info:</b> ', '\n</div>\n')} className="hover:bg-blue-900/50 text-blue-400 px-2 py-1 rounded text-xs font-bold transition">Info Box</button>
                                    <button onClick={() => wrapText('\n<div style="background-color: rgba(245, 158, 11, 0.2); border-left: 4px solid #f59e0b; padding: 10px; margin: 10px 0; border-radius: 4px;">\n⚠️ <b>Warning:</b> ', '\n</div>\n')} className="hover:bg-yellow-900/50 text-yellow-500 px-2 py-1 rounded text-xs font-bold transition">Warn Box</button>
                                    <button onClick={() => wrapText('\n<div style="background-color: rgba(16, 185, 129, 0.2); border-left: 4px solid #10b981; padding: 10px; margin: 10px 0; border-radius: 4px;">\n✅ <b>Success:</b> ', '\n</div>\n')} className="hover:bg-green-900/50 text-green-400 px-2 py-1 rounded text-xs font-bold transition">OK Box</button>
                                </div>

                            </div>
                            <textarea ref={textareaRef} className="w-full flex-grow bg-transparent text-gray-200 p-6 outline-none resize-none font-mono text-sm leading-relaxed custom-scrollbar" value={content} onChange={e=>setContent(e.target.value)} placeholder="Type sophisticated markdown here... Use the toolbar for advanced styling!"></textarea>
                        </div>

                        <div className={`glass-panel-darker p-0 flex flex-col overflow-hidden ${isFullscreen ? 'w-1/2' : 'w-full md:w-1/4'}`}>
                            <div className="p-3 border-b border-white/10 bg-black/60 flex justify-between items-center shrink-0">
                                <span className="text-xs font-mono text-gray-400 font-bold tracking-widest uppercase">Live Render</span>
                                <div className="flex gap-2">
                                    <button onClick={() => exportFile('md')} className="text-[10px] bg-white/10 hover:bg-white/20 px-2 py-1 rounded transition uppercase tracking-wider text-gray-300">.MD</button>
                                    <button onClick={() => exportFile('html')} className="text-[10px] bg-white/10 hover:bg-white/20 px-2 py-1 rounded transition uppercase tracking-wider text-gray-300">.HTML</button>
                                    <button onClick={() => exportFile('pdf')} className="text-[10px] bg-red-600/50 hover:bg-red-600 px-2 py-1 rounded transition uppercase tracking-wider text-white border border-red-500/50">PDF</button>
                                </div>
                            </div>
                            <div className="w-full flex-grow p-6 overflow-y-auto text-gray-200 prose prose-invert max-w-none custom-scrollbar" dangerouslySetInnerHTML={{__html: marked.parse(content || "*Nothing to preview.*")}}></div>
                        </div>
                    </div>
                </div>
            );
        };
