const { useState, useEffect, useRef } = React;

function MarkdownEditorView({ backend, flatGoals, courseColors }) {
  const [content, setContent] = useState('');
  const [previewMode, setPreviewMode] = useState('split');
  const [fileName, setFileName] = useState('untitled.md');
  const [status, setStatus] = useState('Ready');
  const editorRef = useRef(null);
  const previewRef = useRef(null);

  useEffect(() => {
    if (window.markdownit) {
      window.md = window.markdownit({
        html: true,
        linkify: true,
        typographer: true,
        breaks: true,
      });
      window.md.use(window.markdownitFootnote);
      window.md.use(window.markdownitTable);
    }
  }, []);

  const renderPreview = () => {
    if (!window.md || !previewRef.current) return;
    try {
      const html = window.md.render(content);
      previewRef.current.innerHTML = `
        <style>
          body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #e8e8e8; padding: 20px; }
          h1, h2, h3, h4 { color: #fff; margin-top: 1.5em; }
          code { background: #2a2a2a; padding: 0.2em 0.4em; border-radius: 4px; font-family: 'Fira Code', monospace; }
          pre { background: #1a1a1a; padding: 1em; border-radius: 8px; overflow-x: auto; }
          pre code { background: none; padding: 0; }
          blockquote { border-left: 3px solid #3b82f6; padding-left: 1em; color: #9ca3af; margin: 1em 0; }
          table { border-collapse: collapse; width: 100%; margin: 1em 0; }
          th, td { border: 1px solid #333; padding: 0.5em; text-align: left; }
          th { background: #2a2a2a; }
          img { max-width: 100%; height: auto; border-radius: 4px; }
          a { color: #60a5fa; }
          hr { border: none; border-top: 1px solid #333; margin: 2em 0; }
          .task-list-item { list-style: none; }
          .task-list-item input { margin-right: 0.5em; }
        </style>
        ${html}
      `;
    } catch (e) {
      previewRef.current.innerHTML = `<div style="color: #ef4444; padding: 20px;">Render error: ${e.message}</div>`;
    }
  };

  const handleContentChange = (e) => {
    setContent(e.target.value);
    if (previewMode !== 'edit') renderPreview();
  };

  const saveAsHtml = () => {
    if (!window.md) { setStatus('Markdown parser not loaded'); return; }
    try {
      const html = window.md.render(content);
      const fullHtml = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${fileName.replace('.md', '')}</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 40px 20px; }
    h1, h2, h3, h4 { color: #111; }
    code { background: #f4f4f4; padding: 0.2em 0.4em; border-radius: 4px; }
    pre { background: #f8f8f8; padding: 1em; border-radius: 8px; overflow-x: auto; }
    blockquote { border-left: 3px solid #3b82f6; padding-left: 1em; color: #666; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #ddd; padding: 0.5em; }
    th { background: #f4f4f4; }
  </style>
</head>
<body>${html}</body></html>`;
      downloadFile(fullHtml, fileName.replace('.md', '.html'), 'text/html');
      setStatus('Saved as HTML');
    } catch (e) { setStatus('HTML export failed: ' + e.message); }
  };

  const saveAsPdf = () => {
    if (!previewRef.current) { setStatus('Nothing to export'); return; }
    try {
      const printWindow = window.open('', '_blank');
      printWindow.document.write(`
        <!DOCTYPE html>
        <html>
        <head>
          <title>${fileName.replace('.md', '')}</title>
          <style>
            @page { margin: 2cm; }
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; padding: 20px; }
            h1, h2, h3, h4 { color: #111; page-break-after: avoid; }
            code { background: #f4f4f4; padding: 0.2em 0.4em; border-radius: 4px; }
            pre { background: #f8f8f8; padding: 1em; border-radius: 8px; overflow-x: auto; page-break-inside: avoid; }
            blockquote { border-left: 3px solid #3b82f6; padding-left: 1em; color: #666; }
            table { border-collapse: collapse; width: 100%; page-break-inside: avoid; }
            th, td { border: 1px solid #ddd; padding: 0.5em; }
            th { background: #f4f4f4; }
            img { max-width: 100%; }
            @media print { body { padding: 0; } }
          </style>
        </head>
        <body>${previewRef.current.innerHTML}</body>
        </html>
      `);
      printWindow.document.close();
      printWindow.focus();
      setTimeout(() => { printWindow.print(); setStatus('Print dialog opened for PDF'); }, 500);
    } catch (e) { setStatus('PDF export failed: ' + e.message); }
  };

  const downloadFile = (content, filename, mimeType) => {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const loadFile = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (evt) => {
      setContent(evt.target.result);
      setFileName(file.name);
      setStatus(`Loaded: ${file.name}`);
      renderPreview();
    };
    reader.readAsText(file);
  };

  const newFile = () => {
    setContent('');
    setFileName('untitled.md');
    setStatus('New file created');
    renderPreview();
  };

  const layouts = {
    split: { editor: 'w-1/2', preview: 'w-1/2' },
    edit: { editor: 'w-full', preview: 'hidden' },
    preview: { editor: 'hidden', preview: 'w-full' },
  };

  const layout = layouts[previewMode];

  return (
    <div className="h-full flex flex-col bg-black/20 rounded-xl">
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/10 bg-black/30 rounded-t-xl">
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={fileName}
            onChange={(e) => setFileName(e.target.value)}
            className="bg-black/50 border border-white/10 rounded px-2 py-1 text-sm text-white w-48 font-mono"
          />
          <span className="text-xs text-gray-500">.md</span>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={previewMode}
            onChange={(e) => setPreviewMode(e.target.value)}
            className="bg-black/50 border border-white/10 rounded px-2 py-1 text-sm text-white"
          >
            <option value="split">Split</option>
            <option value="edit">Edit</option>
            <option value="preview">Preview</option>
          </select>
          <input type="file" accept=".md,.txt,.markdown" onChange={loadFile} className="hidden" id="file-input" />
          <button onClick={() => document.getElementById('file-input').click()} className="px-3 py-1 text-xs bg-blue-600 hover:bg-blue-500 rounded transition">Open</button>
          <button onClick={newFile} className="px-3 py-1 text-xs bg-gray-600 hover:bg-gray-500 rounded transition">New</button>
          <button onClick={saveAsHtml} className="px-3 py-1 text-xs bg-green-600 hover:bg-green-500 rounded transition">Save HTML</button>
          <button onClick={saveAsPdf} className="px-3 py-1 text-xs bg-purple-600 hover:bg-purple-500 rounded transition">Save PDF</button>
        </div>
      </div>
      <div className={`flex-1 flex overflow-hidden ${layout.editor === 'hidden' ? 'hidden' : ''} ${layout.preview === 'hidden' ? '' : ''}`}>
        <div className={`${layout.editor} flex flex-col min-w-0 border-r border-white/5`}>
          <textarea
            ref={editorRef}
            value={content}
            onChange={handleContentChange}
            placeholder="Start writing markdown..."
            className="flex-1 bg-black/30 border-none resize-none p-4 text-white font-mono text-sm focus:outline-none placeholder-gray-500"
            spellCheck={false}
          />
        </div>
        {layout.preview !== 'hidden' && (
          <div className={`${layout.preview} flex flex-col min-w-0 bg-black/20 overflow-auto`}>
            <div ref={previewRef} className="flex-1 p-4 prose prose-invert max-w-none" dangerouslySetInnerHTML={{ __html: '' }} />
          </div>
        )}
      </div>
      <div className="px-4 py-2 text-xs text-gray-500 border-t border-white/10 bg-black/30 rounded-b-xl">
        {status}
      </div>
    </div>
  );
}