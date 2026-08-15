        // ==========================================
        // SOPHISTICATED PDF ENGINE WITH CONTINUOUS SCROLL
        // ==========================================
        const PdfPage = ({ pageNum, backend, refreshKey, onAnnotate, onRefreshMeta, zoomLevel, activeFile }) => {
            const [pageData, setPageData] = useState(null);
            const [pixDim, setPixDim] = useState({w: 1, h: 1, renderZoom: 3.0});
            const [isIntersecting, setIsIntersecting] = useState(false);
            const containerRef = useRef(null);
            const imgRef = useRef(null);

            const [drawing, setDrawing] = useState(false);
            const [startPos, setStartPos] = useState(null);
            const [currPos, setCurrPos] = useState(null);

            useEffect(() => {
                const observer = new IntersectionObserver(([entry]) => {
                    if (entry.isIntersecting) setIsIntersecting(true);
                }, { rootMargin: "1200px" });
                if (containerRef.current) observer.observe(containerRef.current);
                return () => observer.disconnect();
            }, []);

            const fetchPage = () => {
                const renderZoom = 3.0; // High DPI for crystal clear text
                backend.request(JSON.stringify({action: 'lib_page', page: pageNum, zoom: renderZoom})).then(res => {
                    const data = JSON.parse(res);
                    if (data.b64) {
                        setPageData(`data:image/png;base64,${data.b64}`);
                        setPixDim({ w: data.width, h: data.height, renderZoom });
                        if (onRefreshMeta) onRefreshMeta(pageNum, data.annots || []);
                    }
                });
            };

            useEffect(() => {
                setIsIntersecting(false); 
                setPageData(null);
            }, [activeFile]);

            useEffect(() => {
                if (isIntersecting) fetchPage();
            }, [isIntersecting, refreshKey, activeFile]);

            const handleMouseDown = (e) => {
                if (!imgRef.current) return;
                const rect = imgRef.current.getBoundingClientRect();
                const x = e.clientX - rect.left; const y = e.clientY - rect.top;
                setStartPos({x, y}); setCurrPos({x, y}); setDrawing(true);
            };

            const handleMouseMove = (e) => {
                if (!drawing || !imgRef.current) return;
                const rect = imgRef.current.getBoundingClientRect();
                setCurrPos({
                    x: Math.max(0, Math.min(e.clientX - rect.left, rect.width)), 
                    y: Math.max(0, Math.min(e.clientY - rect.top, rect.height))
                });
            };

            const handleMouseUp = () => {
                if (!drawing) return;
                setDrawing(false);
                if (!startPos || !currPos) return;
                
                const w = Math.abs(currPos.x - startPos.x); const h = Math.abs(currPos.y - startPos.y);
                if (w < 5 || h < 5) return;

                const rect = imgRef.current.getBoundingClientRect();
                const ratioX0 = Math.min(startPos.x, currPos.x) / rect.width;
                const ratioY0 = Math.min(startPos.y, currPos.y) / rect.height;
                const ratioX1 = Math.max(startPos.x, currPos.x) / rect.width;
                const ratioY1 = Math.max(startPos.y, currPos.y) / rect.height;

                // Mathematical scaling down to exact original PDF Points
                const x0 = ratioX0 * (pixDim.w / pixDim.renderZoom);
                const y0 = ratioY0 * (pixDim.h / pixDim.renderZoom);
                const x1 = ratioX1 * (pixDim.w / pixDim.renderZoom);
                const y1 = ratioY1 * (pixDim.h / pixDim.renderZoom);

                if (onAnnotate) onAnnotate(pageNum, [x0, y0, x1, y1]);
            };

            return (
                <div ref={containerRef} style={{ width: `${zoomLevel * 100}%` }} className="mb-6 relative inline-block mx-auto min-h-[600px] bg-white/5 transition-all duration-200" onMouseDown={handleMouseDown} onMouseMove={handleMouseMove} onMouseUp={handleMouseUp} onMouseLeave={handleMouseUp}>
                    {pageData ? (
                        <img ref={imgRef} src={pageData} alt={`Page ${pageNum+1}`} className="w-full h-auto block shadow-2xl rounded" />
                    ) : (
                        <div className="flex flex-col items-center justify-center h-[800px] text-gray-500 font-mono text-sm tracking-widest">
                            <i className="fas fa-spinner fa-spin text-3xl mb-4"></i> Rendering High-DPI Page {pageNum + 1}...
                        </div>
                    )}
                    {drawing && startPos && currPos && (
                        <div className="absolute border-2 border-blue-500 bg-blue-500/20 pointer-events-none" style={{
                            left: Math.min(startPos.x, currPos.x), top: Math.min(startPos.y, currPos.y),
                            width: Math.abs(currPos.x - startPos.x), height: Math.abs(currPos.y - startPos.y)
                        }}></div>
                    )}
                </div>
            );
        };

        const PDFLibraryView = ({ backend }) => {
            const [files, setFiles] = useState([]);
            const [activeFile, setActiveFile] = useState(null);
            const [totalPages, setTotalPages] = useState(0);
            const [tool, setTool] = useState("Highlight");
            const [zoomLevel, setZoomLevel] = useState(1.0);
            const [isFullscreen, setIsFullscreen] = useState(false);
            const [currentPageDisplay, setCurrentPageDisplay] = useState(1);
            
            const [pageMeta, setPageMeta] = useState({});
            const [refreshKeys, setRefreshKeys] = useState({});

            // Markdown Note Modal State
            const [showNoteModal, setShowNoteModal] = useState(false);
            const [pendingAnnot, setPendingAnnot] = useState(null);
            const [noteContent, setNoteContent] = useState("");
            const [notePreview, setNotePreview] = useState(false);
            const noteTextareaRef = useRef(null);

            const fetchFiles = () => {
                backend.request(JSON.stringify({action: 'lib_list'})).then(res => setFiles(JSON.parse(res).files || []));
            };

            useEffect(() => { if(backend) fetchFiles(); }, [backend]);

            const loadPdf = (f) => {
                backend.request(JSON.stringify({action: 'lib_open', filename: f})).then(res => {
                    const data = JSON.parse(res);
                    if (data.status === 'ok') {
                        setActiveFile(f); 
                        setTotalPages(data.total_pages); 
                        setPageMeta({});
                        setRefreshKeys({});
                    } else alert(data.error);
                });
            };

            const handleAnnotate = (page, rect) => {
                if (tool === 'Note') {
                    setPendingAnnot({ page, rect });
                    setNoteContent("");
                    setNotePreview(false);
                    setShowNoteModal(true);
                } else {
                    backend.request(JSON.stringify({action: 'lib_annot', page, rect, tool, text: ""})).then(() => {
                        setRefreshKeys(prev => ({...prev, [page]: (prev[page] || 0) + 1}));
                    });
                }
            };

            const saveMarkdownNote = () => {
                if (!pendingAnnot || !noteContent) { setShowNoteModal(false); return; }
                backend.request(JSON.stringify({action: 'lib_annot', page: pendingAnnot.page, rect: pendingAnnot.rect, tool: 'Note', text: noteContent})).then(() => {
                    setRefreshKeys(prev => ({...prev, [pendingAnnot.page]: (prev[pendingAnnot.page] || 0) + 1}));
                    setShowNoteModal(false);
                });
            };

            const onRefreshMeta = (page, annots) => {
                setPageMeta(prev => ({...prev, [page]: annots}));
            };

            const wrapText = (prefix, suffix = '') => {
                const el = noteTextareaRef.current;
                if (!el) { setNoteContent(prev => prev + prefix + suffix); return; }
                const start = el.selectionStart; const end = el.selectionEnd;
                const text = noteContent || ""; const selectedText = text.substring(start, end);
                const newText = text.substring(0, start) + prefix + selectedText + suffix + text.substring(end);
                setNoteContent(newText);
                setTimeout(() => { el.focus(); el.setSelectionRange(start + prefix.length, end + prefix.length); }, 0);
            };

            const handleScroll = (e) => {
                const container = e.target;
                const scrollPosition = container.scrollTop;
                const avgPageHeight = container.scrollHeight / totalPages;
                const current = Math.floor(scrollPosition / avgPageHeight);
                setCurrentPageDisplay(Math.max(1, Math.min(totalPages, current + 1)));
            };

            const allAnnots = Object.values(pageMeta).flat();

            return (
                <div className={`flex flex-col fade-in transition-all duration-300 ${isFullscreen ? 'fixed inset-0 z-[100] bg-[#050505] p-6' : 'h-full'}`}>
                    {!isFullscreen && <div className="flex justify-between items-center mb-6 shrink-0"><h2 className="text-2xl font-serif font-bold text-white tracking-widest uppercase drop-shadow-md">PDF Library & Meta-Annotation</h2></div>}
                    <div className="flex gap-4 flex-grow overflow-hidden">
                        {!isFullscreen && (
                            <div className="w-1/4 glass-panel p-4 flex flex-col gap-3 shrink-0 overflow-y-auto custom-scrollbar">
                                <h3 className="text-xs font-bold text-gray-400 uppercase tracking-widest border-b border-white/10 pb-2">Synced Documents</h3>
                                <button onClick={fetchFiles} className="glass-button w-full py-2 rounded text-[10px] font-bold tracking-widest text-blue-300 uppercase shadow-lg mb-2 border border-blue-500/30"><i className="fas fa-sync mr-1"></i> Refresh Folder</button>
                                {files.length === 0 && <div className="text-[10px] text-gray-500 italic mt-2">Place PDFs in ~/MindPalace_Library</div>}
                                {files.map(f => (
                                    <div key={f.name} onClick={() => loadPdf(f.name)} className={`p-3 text-xs rounded cursor-pointer border truncate transition-all ${activeFile === f.name ? 'bg-blue-600/30 border-blue-400 text-white shadow-[0_0_10px_rgba(59,130,246,0.5)]' : 'bg-white/5 border-white/10 hover:bg-white/10 text-gray-300'}`}>{f.name}</div>
                                ))}
                            </div>
                        )}
                        <div className={`glass-panel p-0 flex flex-col ${isFullscreen ? 'w-full' : 'w-2/4'} overflow-hidden relative`}>
                            <div className="flex flex-wrap gap-2 p-3 border-b border-white/10 bg-black/40 items-center justify-between shrink-0">
                                <div className="flex gap-2">
                                    {['Highlight', 'Underline', 'Note'].map(t => (
                                        <button key={t} onClick={() => setTool(t)} className={`px-4 py-1.5 rounded text-[11px] font-bold tracking-widest uppercase transition ${tool === t ? 'bg-blue-600 text-white shadow-lg' : 'bg-white/10 text-gray-300 hover:bg-white/20'}`}>{t}</button>
                                    ))}
                                    <div className="w-px h-6 bg-white/20 mx-2"></div>
                                    <button onClick={() => setZoomLevel(z => Math.max(0.2, z - 0.2))} className="px-3 py-1.5 rounded bg-white/10 hover:bg-white/20 text-white text-xs"><i className="fas fa-search-minus"></i></button>
                                    <button onClick={() => setZoomLevel(z => Math.min(3.0, z + 0.2))} className="px-3 py-1.5 rounded bg-white/10 hover:bg-white/20 text-white text-xs"><i className="fas fa-search-plus"></i></button>
                                </div>
                                <div className="flex gap-2 items-center">
                                    <span className="text-[10px] font-bold text-blue-400 border border-blue-500/30 px-3 py-1 rounded bg-black/50">Pg {currentPageDisplay} of {totalPages}</span>
                                    
                                    {activeFile && (
                                        <button onClick={() => backend.request(JSON.stringify({action: 'lib_open_native', filename: activeFile}))} className="px-3 py-1.5 rounded bg-purple-600/50 hover:bg-purple-600 text-white text-[10px] font-bold tracking-widest uppercase border border-purple-500/50 transition shadow-lg ml-2">
                                            <i className="fas fa-external-link-alt mr-1"></i> Native Editor
                                        </button>
                                    )}

                                    <button onClick={() => setIsFullscreen(!isFullscreen)} className="px-3 py-1.5 rounded bg-white/10 hover:bg-white/20 text-white text-xs ml-2"><i className={`fas ${isFullscreen ? 'fa-compress' : 'fa-expand'}`}></i></button>
                                </div>
                            </div>
                            
                            {/* INFINITE SCROLL CONTAINER */}
                            <div className="flex-grow overflow-auto bg-black/60 flex flex-col items-center custom-scrollbar relative p-4 text-center" onScroll={handleScroll}>
                                {activeFile ? (
                                    Array.from({ length: totalPages }).map((_, idx) => (
                                        <PdfPage 
                                            key={`${activeFile}-${idx}`} 
                                            pageNum={idx} 
                                            zoomLevel={zoomLevel} 
                                            backend={backend} 
                                            tool={tool} 
                                            activeFile={activeFile}
                                            refreshKey={refreshKeys[idx] || 0}
                                            onAnnotate={handleAnnotate}
                                            onRefreshMeta={onRefreshMeta}
                                        />
                                    ))
                                ) : (
                                    <div className="text-gray-500 font-bold uppercase tracking-widest m-auto flex flex-col items-center"><i className="fas fa-book-reader text-5xl mb-4 opacity-50"></i>Select a PDF from Library</div>
                                )}
                            </div>
                        </div>
                        
                        {!isFullscreen && (
                            <div className="w-1/4 glass-panel p-4 flex flex-col gap-3 shrink-0 overflow-y-auto custom-scrollbar">
                                <h3 className="text-xs font-bold text-gray-400 uppercase tracking-widest border-b border-white/10 pb-2">All Document Annotations</h3>
                                {allAnnots.length === 0 ? <div className="text-[10px] text-gray-500 italic mt-2">No annotations across the document. Drag to draw.</div> : 
                                    allAnnots.map((a, i) => (
                                        <div key={i} className="bg-white/5 p-3 rounded border border-white/10 text-xs hover:bg-white/10 transition">
                                            <div className="flex justify-between text-[10px] text-gray-400 font-bold uppercase tracking-wider mb-2 border-b border-white/5 pb-1">
                                                <span className={a.subject === 'Highlight' ? 'text-yellow-400' : a.subject === 'Underline' ? 'text-blue-400' : 'text-green-400'}><i className={`fas fa-${a.subject === 'Note' ? 'comment' : 'marker'} mr-1`}></i> {a.subject}</span>
                                                <span className="opacity-70 truncate max-w-[80px]" title={a.title}>{a.title}</span>
                                            </div>
                                            <div className="text-gray-200 text-xs leading-relaxed custom-scrollbar overflow-x-hidden md-preview max-w-none" dangerouslySetInnerHTML={{__html: marked.parse(a.content || "")}}></div>
                                        </div>
                                    ))
                                }
                            </div>
                        )}
                    </div>

                    {/* Markdown Annotation Modal */}
                    {showNoteModal && (
                        <div className="fixed inset-0 bg-black/90 z-[150] flex items-center justify-center p-4 backdrop-blur-md">
                            <div className="glass-panel p-6 w-full max-w-4xl h-[80vh] flex flex-col gap-4 fade-in border border-blue-500/50">
                                <div className="flex justify-between items-center shrink-0">
                                    <h3 className="text-white font-bold text-xl tracking-widest uppercase"><i className="fas fa-edit text-blue-400 mr-2"></i> Sophisticated Annotation</h3>
                                    <button onClick={() => setShowNoteModal(false)} className="text-gray-400 hover:text-white"><i className="fas fa-times text-xl"></i></button>
                                </div>

                                <div className="flex flex-wrap gap-1 items-center bg-black/50 p-2 rounded-lg border border-white/10 text-gray-300 shrink-0">
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
                                    <div className="w-px h-4 bg-white/20 mx-1"></div>
                                    <button onClick={() => wrapText('![alt text](', ')')} className="hover:bg-white/20 w-7 h-7 rounded transition flex items-center justify-center" title="Add Image"><i className="fas fa-image"></i></button>
                                    <button onClick={() => wrapText('\n```\n', '\n```\n')} className="hover:bg-white/20 w-7 h-7 rounded transition flex items-center justify-center" title="Code Block"><i className="fas fa-code"></i></button>
                                    <div className="w-px h-4 bg-white/20 mx-1"></div>
                                    <button onClick={() => wrapText('\n<div style="background-color: rgba(59, 130, 246, 0.2); border-left: 4px solid #3b82f6; padding: 10px; margin: 10px 0; border-radius: 4px;">\n💡 <b>Info:</b> ', '\n</div>\n')} className="hover:bg-blue-900/50 text-blue-400 px-2 py-1 rounded text-xs font-bold transition">Info Box</button>
                                    <button onClick={() => wrapText('\n<div style="background-color: rgba(245, 158, 11, 0.2); border-left: 4px solid #f59e0b; padding: 10px; margin: 10px 0; border-radius: 4px;">\n⚠️ <b>Warning:</b> ', '\n</div>\n')} className="hover:bg-yellow-900/50 text-yellow-500 px-2 py-1 rounded text-xs font-bold transition">Warn Box</button>
                                    <button onClick={() => wrapText('\n<div style="background-color: rgba(16, 185, 129, 0.2); border-left: 4px solid #10b981; padding: 10px; margin: 10px 0; border-radius: 4px;">\n✅ <b>Success:</b> ', '\n</div>\n')} className="hover:bg-green-900/50 text-green-400 px-2 py-1 rounded text-xs font-bold transition">OK Box</button>
                                    <div className="ml-auto flex gap-2">
                                        <button onClick={() => setNotePreview(false)} className={`px-3 py-1 rounded text-xs font-bold transition ${!notePreview ? 'bg-blue-600 text-white' : 'bg-white/10 text-gray-300'}`}>Edit</button>
                                        <button onClick={() => setNotePreview(true)} className={`px-3 py-1 rounded text-xs font-bold transition ${notePreview ? 'bg-blue-600 text-white' : 'bg-white/10 text-gray-300'}`}>Preview</button>
                                    </div>
                                </div>

                                <div className="flex-grow overflow-hidden flex bg-black/40 rounded-xl border border-white/5">
                                    {!notePreview ? (
                                        <textarea ref={noteTextareaRef} className="w-full h-full bg-transparent text-gray-200 p-6 outline-none resize-none font-mono text-sm leading-relaxed custom-scrollbar" value={noteContent} onChange={e=>setNoteContent(e.target.value)} placeholder="Type sophisticated markdown note here... it will be permanently bound to this PDF region!" autoFocus></textarea>
                                    ) : (
                                        <div className="w-full h-full p-6 overflow-y-auto text-gray-200 md-preview max-w-none custom-scrollbar" dangerouslySetInnerHTML={{__html: marked.parse(noteContent || "*Nothing to preview.*")}}></div>
                                    )}
                                </div>

                                <div className="flex gap-4 shrink-0">
                                    <button onClick={() => setShowNoteModal(false)} className="glass-button px-6 py-3 rounded-lg text-xs font-bold tracking-widest uppercase w-1/3 bg-red-600/30 text-red-300 border-red-500/30">Cancel</button>
                                    <button onClick={saveMarkdownNote} className="glass-button px-6 py-3 rounded-lg text-xs font-bold tracking-widest uppercase w-2/3 bg-blue-600/30 hover:bg-blue-600 text-white border border-blue-500/50 transition">Inject Markdown into PDF</button>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            );
        };
