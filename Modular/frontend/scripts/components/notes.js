const NotesView = ({ notes, backend, refreshNotes, flatGoals, courseColors }) => {
    const [activeNoteId, setActiveNoteId] = useState(null);
    const [title, setTitle] = useState("");
    const [content, setContent] = useState("");
    const [course, setCourse] = useState("");
    const [folder, setFolder] = useState("Uncategorized");
    const [color, setColor] = useState("#3b82f6");
    const [isFullscreen, setIsFullscreen] = useState(false);
    const [splitRatio, setSplitRatio] = useState(50);
    const [isDragging, setIsDragging] = useState(false);
    const [showPreview, setShowPreview] = useState(true);
    const containerRef = useRef(null);
    const textareaRef = useRef(null);

    useEffect(() => {
        if (course && courseColors && courseColors[course]) setColor(courseColors[course]);
    }, [course, courseColors]);

    useEffect(() => {
        if (typeof marked !== 'undefined') {
            marked.setOptions({
                breaks: true,
                gfm: true,
                headerIds: false,
                mangle: false
            });
        }
    }, []);

    const handleSave = () => {
        backend.request(JSON.stringify({action: 'manage_note', sub: 'save', id: activeNoteId, title: title || "Untitled Note", content, course: course || "General", folder: folder, color: color})).then(res => {
            refreshNotes(JSON.parse(res).notes);
        });
    };

    const selectNote = (n) => { setActiveNoteId(n.id); setTitle(n.title); setContent(n.content || ""); setCourse(n.course); setFolder(n.folder); setColor(n.color); setIsFullscreen(false); };
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

    const renderMarkdown = (text) => {
        if (typeof marked !== 'undefined' && marked.parse) {
            try {
                const html = marked.parse(text || "");
                return html;
            } catch(e) {
                console.error('marked.parse error:', e);
                return (text || "").replace(/\n/g, '<br>');
            }
        }
        return (text || "").replace(/\n/g, '<br>');
    };

    const handleSplitDrag = (e) => {
        if (!isDragging || !containerRef.current) return;
        const rect = containerRef.current.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const pct = Math.max(20, Math.min(80, (x / rect.width) * 100));
        setSplitRatio(pct);
    };

    useEffect(() => {
        if (isDragging) {
            const onUp = () => setIsDragging(false);
            window.addEventListener('mousemove', handleSplitDrag);
            window.addEventListener('mouseup', onUp);
            return () => { window.removeEventListener('mousemove', handleSplitDrag); window.removeEventListener('mouseup', onUp); };
        }
    }, [isDragging]);

    const exportFile = (type) => {
        const parsedHTML = renderMarkdown(content);
        const fullHTML = `<!DOCTYPE html><html><head><title>${title || 'Note'}</title><meta charset="utf-8">
<style>
body{font-family:'Segoe UI',system-ui,-apple-system,sans-serif;padding:2rem 4rem;color:#1a1a1a;line-height:1.8;max-width:900px;margin:0 auto;background:#fafafa;}
h1,h2,h3,h4{color:#111;margin-top:2em;margin-bottom:0.5em;border-bottom:1px solid #eee;padding-bottom:0.3em;}
h1{font-size:2em;} h2{font-size:1.5em;} h3{font-size:1.25em;}
blockquote{border-left:4px solid #3b82f6;padding:0.5rem 1rem;margin:1rem 0;background:#f0f7ff;color:#333;border-radius:0 4px 4px 0;}
code{background:#f0f0f0;padding:0.15rem 0.4rem;border-radius:3px;font-size:0.9em;font-family:'Fira Code',monospace;}
pre{background:#1e1e1e;color:#d4d4d4;padding:1rem;border-radius:6px;overflow-x:auto;}
pre code{background:none;padding:0;color:inherit;}
table{border-collapse:collapse;width:100%;margin:1rem 0;}
th,td{border:1px solid #ddd;padding:0.5rem 0.75rem;text-align:left;}
th{background:#f5f5f5;font-weight:600;}
img{max-width:100%;border-radius:6px;}
mark{background:#fef08a;padding:0 3px;border-radius:2px;}
a{color:#3b82f6;text-decoration:none;} a:hover{text-decoration:underline;}
hr{border:none;border-top:1px solid #ddd;margin:2rem 0;}
@media print{body{background:#fff;padding:1rem;} pre{white-space:pre-wrap;word-wrap:break-word;}}
</style></head><body>${parsedHTML}</body></html>`;

        if (type === 'md') {
            const blob = new Blob([content || ""], {type: "text/markdown"});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url; a.download = `${title || 'Export'}.md`; a.click();
            URL.revokeObjectURL(url);
        } else if (type === 'html') {
            const blob = new Blob([fullHTML], {type: "text/html"});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url; a.download = `${title || 'Export'}.html`; a.click();
            URL.revokeObjectURL(url);
        } else if (type === 'pdf') {
            const win = window.open('', '_blank', 'width=900,height=700');
            if (win) {
                win.document.write(fullHTML);
                win.document.close();
                win.focus();
                setTimeout(() => { win.print(); }, 500);
            }
        }
    };

    return (
        <div className={`flex flex-col fade-in transition-all duration-300 ${isFullscreen ? 'fixed inset-0 z-[100] bg-gray-900/50 p-6' : 'h-full bg-gray-900/50'}`}>
            {!isFullscreen && (
                <div className="flex justify-between items-center mb-6 shrink-0">
                    <h2 className="text-2xl font-serif font-bold text-white tracking-widest uppercase drop-shadow-md">Sophisticated Notes</h2>
                </div>
            )}

            <div className="flex flex-col md:flex-row gap-4 flex-grow overflow-hidden">

                {!isFullscreen && (
                    <div className="w-full md:w-56 glass-panel p-4 flex flex-col gap-2 overflow-y-auto shrink-0">
                        <button onClick={newNote} className="glass-button w-full py-2 rounded text-[11px] font-bold tracking-widest text-green-300 uppercase shadow-lg mb-2 border border-green-500/30">+ New Note</button>
                        {notes && notes.map(n => (
                            <div key={n.id} onClick={() => selectNote(n)} className={`p-3 rounded cursor-pointer border text-sm transition-all group relative ${activeNoteId === n.id ? 'bg-blue-600/30 border-blue-400 text-white' : 'bg-white/5 border-white/10 hover:bg-white/10 text-gray-300'}`}>
                                <div className="flex items-center gap-2 mb-1">
                                    <div className="w-2 h-2 rounded-full shrink-0" style={{backgroundColor: courseColors && courseColors[n.course] ? courseColors[n.course] : n.color}}></div>
                                    <div className="text-[9px] font-bold uppercase tracking-widest text-gray-500 truncate">{n.folder}</div>
                                </div>
                                <div className="font-bold truncate">{n.title}</div>
                                <i onClick={(e) => {e.stopPropagation(); backend.request(JSON.stringify({action: 'manage_note', sub: 'delete', id: n.id})).then(res => refreshNotes(JSON.parse(res).notes));}} className="fas fa-trash text-red-500 absolute top-3 right-3 opacity-0 group-hover:opacity-100 hover:scale-110 transition"></i>
                            </div>
                        ))}
                    </div>
                )}

                <div ref={containerRef} className="glass-panel p-0 flex flex-col overflow-hidden flex-grow min-w-0" style={{display:'flex', flexDirection:'row'}}>
                    {/* Editor Pane */}
                    <div className="flex flex-col overflow-hidden" style={{width: showPreview ? `${splitRatio}%` : '100%', minWidth: showPreview ? '200px' : 'auto'}}>
                        <div className="flex flex-col gap-2 p-3 border-b border-white/10 bg-black/40 shrink-0">
                            <div className="flex flex-wrap gap-2 items-center">
                                <input type="text" placeholder="Title..." className="glass-input px-3 py-1.5 rounded w-full sm:w-auto flex-grow font-bold text-white text-sm" value={title} onChange={e=>setTitle(e.target.value)} />
                                <select className="glass-input px-2 py-1.5 rounded text-xs w-32" value={course} onChange={e=>setCourse(e.target.value)}><option value="">Goal / Course...</option>{flatGoals.map(g=><option key={g} value={g}>{g}</option>)}</select>
                                <input type="text" placeholder="Folder..." className="glass-input px-2 py-1.5 rounded text-xs w-24" value={folder} onChange={e=>setFolder(e.target.value)} />
                                <input type="color" value={color} onChange={e=>setColor(e.target.value)} className="w-7 h-7 rounded cursor-pointer border-0 p-0" />
                                <button onClick={handleSave} className="glass-button px-6 py-1.5 rounded font-bold text-white tracking-widest uppercase bg-blue-600/30 border-blue-500/50 hover:bg-blue-600 transition text-xs">Save</button>
                                <button onClick={() => setIsFullscreen(!isFullscreen)} className="glass-button w-8 h-8 rounded flex items-center justify-center text-gray-300 hover:text-white transition" title="Toggle Fullscreen">
                                    <i className={`fas ${isFullscreen ? 'fa-compress' : 'fa-expand'}`}></i>
                                </button>
                                <button onClick={() => setShowPreview(!showPreview)} className={`glass-button w-8 h-8 rounded flex items-center justify-center transition ${showPreview ? 'text-blue-400' : 'text-gray-500'}`} title="Toggle Preview">
                                    <i className="fas fa-columns"></i>
                                </button>
                            </div>

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
                                <button onClick={() => wrapText('`', '`')} className="hover:bg-white/20 w-7 h-7 rounded transition flex items-center justify-center" title="Inline Code"><i className="fas fa-code"></i></button>
                                <button onClick={() => wrapText('\n```\n', '\n```\n')} className="hover:bg-white/20 px-2 py-1 rounded text-xs font-mono transition" title="Code Block">{ }</button>
                                <button onClick={() => wrapText('> ', '')} className="hover:bg-white/20 w-7 h-7 rounded transition flex items-center justify-center" title="Blockquote"><i className="fas fa-quote-right"></i></button>
                                <button onClick={() => wrapText('- ', '')} className="hover:bg-white/20 w-7 h-7 rounded transition flex items-center justify-center" title="List"><i className="fas fa-list-ul"></i></button>
                                <button onClick={() => wrapText('1. ', '')} className="hover:bg-white/20 w-7 h-7 rounded transition flex items-center justify-center" title="Numbered List"><i className="fas fa-list-ol"></i></button>
                                <div className="w-px h-4 bg-white/20 mx-1"></div>
                                <button onClick={() => wrapText('![alt](', ')')} className="hover:bg-white/20 w-7 h-7 rounded transition flex items-center justify-center" title="Image"><i className="fas fa-image"></i></button>
                                <button onClick={() => wrapText('[text](', ')')} className="hover:bg-white/20 w-7 h-7 rounded transition flex items-center justify-center" title="Link"><i className="fas fa-link"></i></button>
                                <button onClick={() => wrapText('\n---\n', '')} className="hover:bg-white/20 w-7 h-7 rounded transition flex items-center justify-center" title="Horizontal Rule"><i className="fas fa-minus"></i></button>
                                <div className="w-px h-4 bg-white/20 mx-1"></div>
                                <button onClick={() => wrapText('\n| Col1 | Col2 |\n|------|------|\n| ', ' | data |\n')} className="hover:bg-white/20 w-7 h-7 rounded transition flex items-center justify-center" title="Table"><i className="fas fa-table"></i></button>
                                <button onClick={() => wrapText('<mark>', '</mark>')} className="hover:bg-yellow-500/30 text-yellow-400 w-7 h-7 rounded transition flex items-center justify-center" title="Highlight"><i className="fas fa-highlighter"></i></button>
                                <button onClick={() => wrapText('\n> [!NOTE]\n> ', '\n')} className="hover:bg-blue-900/50 text-blue-400 px-2 py-1 rounded text-[10px] font-bold transition">Note</button>
                                <button onClick={() => wrapText('\n> [!WARNING]\n> ', '\n')} className="hover:bg-yellow-900/50 text-yellow-500 px-2 py-1 rounded text-[10px] font-bold transition">Warn</button>
                                <button onClick={() => wrapText('\n> [!TIP]\n> ', '\n')} className="hover:bg-green-900/50 text-green-400 px-2 py-1 rounded text-[10px] font-bold transition">Tip</button>
                            </div>
                        </div>
                        <textarea ref={textareaRef} className="w-full flex-grow bg-transparent text-gray-200 p-6 outline-none resize-none font-mono text-sm leading-relaxed custom-scrollbar" value={content} onChange={e=>setContent(e.target.value)} placeholder="Type sophisticated markdown here... Use the toolbar for advanced styling!"></textarea>
                    </div>

                    {/* Resizable Divider */}
                    {showPreview && (
                        <div className="w-1 bg-white/10 hover:bg-blue-500/50 cursor-col-resize shrink-0 transition-colors relative group" onMouseDown={() => setIsDragging(true)}>
                            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-1 h-8 bg-white/30 rounded-full group-hover:bg-blue-400 transition"></div>
                        </div>
                    )}

                    {/* Preview Pane */}
                    {showPreview && (
                        <div className="glass-panel-darker p-0 flex flex-col overflow-hidden" style={{width: `${100 - splitRatio}%`, minWidth: '200px'}}>
                            <div className="p-3 border-b border-white/10 bg-black/60 flex justify-between items-center shrink-0">
                                <span className="text-xs font-mono text-gray-400 font-bold tracking-widest uppercase">Live Preview</span>
                                <div className="flex gap-1">
                                    <button onClick={() => exportFile('md')} className="text-[10px] bg-white/10 hover:bg-white/20 px-2 py-1 rounded transition uppercase tracking-wider text-gray-300">.MD</button>
                                    <button onClick={() => exportFile('html')} className="text-[10px] bg-white/10 hover:bg-white/20 px-2 py-1 rounded transition uppercase tracking-wider text-gray-300">.HTML</button>
                                    <button onClick={() => exportFile('pdf')} className="text-[10px] bg-red-600/50 hover:bg-red-600 px-2 py-1 rounded transition uppercase tracking-wider text-white border border-red-500/50">PDF</button>
                                </div>
                            </div>
                            <div className="w-full flex-grow p-6 overflow-y-auto text-gray-200 md-preview max-w-none custom-scrollbar leading-relaxed" dangerouslySetInnerHTML={{__html: renderMarkdown(content)}}></div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};
