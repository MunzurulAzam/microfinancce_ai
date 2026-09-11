import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { Menu, Plus, Search, Pencil, Trash2, Send, X, Sparkles, ArrowDown } from 'lucide-react';
import { store, uid } from './store';
import { changed, subscribe, send, recover } from './runtime';
import Message from './Message';
import ReportPeriods from './ReportPeriods';
import './Workspace.css';

const blank = { text: '', mode: 'ask', country: 'ALL' };
const countries = [['ALL','All countries'],['UG','Uganda'],['KY','Kenya'],['TZ','Tanzania'],['ZM','Zambia']];
export default function Workspace() {
    const { id } = useParams(), location = useLocation(), navigate = useNavigate();
    const [list,setList] = useState([]), [conversation,setConversation] = useState(null), [messages,setMessages] = useState([]);
    const [draft,setDraft] = useState(blank), [ready,setReady] = useState(false), [error,setError] = useState('');
    const [search,setSearch] = useState(''), [sidebar,setSidebar] = useState(false), [collapsed,setCollapsed] = useState(false);
    const [edit,setEdit] = useState(null), [title,setTitle] = useState(''), [deleting,setDeleting] = useState(null), [newResponse,setNewResponse] = useState(false);
    const viewport = useRef(null), nearBottom = useRef(true), lastView = useRef(''), dirty = useRef(false), active = useRef(id);
    const writeQueue = useRef(Promise.resolve()), alive = useRef(false), lastResponse = useRef(''), draftRevision = useRef(0);
    const reportError = e => setError(`History could not be saved or loaded. ${e?.message || 'Check browser storage permissions and available space.'}`);
    const queueWrite = fn => { writeQueue.current = writeQueue.current.catch(() => {}).then(fn); writeQueue.current.catch(reportError); return writeQueue.current; };
    useEffect(() => {
        let mounted = true, revision = 0;
        alive.current = true;
        active.current = id; dirty.current = false;
        async function refresh(initial = false) {
            const version = ++revision;
            try {
                const entries = await store.list();
                if (!mounted || version !== revision) return;
                setList(entries);
                if (id) {
                    const c = await store.get(id), ms = c && !c.deletedAt ? await store.messages(id) : [];
                    if (!mounted || version !== revision) return;
                    setConversation(c?.deletedAt ? null : c || null); setMessages(ms);
                    if (!dirty.current) setDraft(c && !c.deletedAt ? { text: c.draft || '', mode: c.mode, country: c.country } : blank);
                    if (!c || c.deletedAt) setError('This conversation is no longer available. Start a new chat.');
                    else if (initial) await store.saveSetting('lastActive', id);
                } else if (initial || !dirty.current) {
                    if (initial && location.pathname !== '/ask-ai' && !location.search.includes('new=1')) {
                        const previous = await store.setting('lastActive');
                        if (mounted && entries.some(c => c.id === previous)) { navigate(`/chat/${previous}`, { replace: true }); return; }
                    }
                    const saved = await store.setting('newDraft');
                    if (!mounted || version !== revision) return;
                    setMessages([]); setConversation(null);
                    setDraft({ ...blank, ...saved, ...(location.pathname === '/ask-ai' ? { mode: 'warehouse' } : {}) });
                }
                if (mounted) setReady(true);
            } catch (e) { if (mounted) { reportError(e); setReady(true); } }
        }
        void refresh(true);
        const unsubscribe = subscribe(() => { void refresh(); });
        const focus = () => { void recover().then(() => refresh()).catch(reportError); };
        window.addEventListener('focus',focus);
        void recover().catch(reportError);
        const timer = setInterval(focus, 30000);
        return () => { mounted = false; alive.current = false; unsubscribe(); window.removeEventListener('focus',focus); clearInterval(timer); };
    }, [id,location.pathname,location.search,navigate]);
    useLayoutEffect(() => {
        const el = viewport.current;
        if (!el || !ready) return;
        if (lastView.current !== (id || 'new') || nearBottom.current) {
            el.scrollTop = el.scrollHeight; lastView.current = id || 'new';
        } else if (messages.at(-1)?.status === 'complete' && lastResponse.current !== `${messages.at(-1)?.id}:${messages.at(-1)?.status}`) {
            // Schedule the indicator outside this effect's render cycle.
            lastResponse.current = `${messages.at(-1)?.id}:${messages.at(-1)?.status}`;
            const frame = requestAnimationFrame(() => setNewResponse(true));
            return () => cancelAnimationFrame(frame);
        }
        lastResponse.current = `${messages.at(-1)?.id}:${messages.at(-1)?.status}`;
    }, [messages,id,ready]);
    const updateDraft = patch => {
        const next = { ...draft, ...patch }; dirty.current = true; setDraft(next);
        const target = id, version = ++draftRevision.current;
        queueWrite(async () => {
            if (target) await store.patch(target, { draft: next.text, country: next.country });
            else await store.saveSetting('newDraft', next);
            if (version === draftRevision.current && active.current === target) dirty.current = false;
            changed(target);
        });
    };
    const submit = async (event, retry) => {
        event?.preventDefault();
        if ((!draft.text.trim() && !retry) || conversation?.pending || !ready) return;
        const target = id || uid();
        setError(''); nearBottom.current = true; setNewResponse(false);
        try {
            await writeQueue.current;
            await send({ id: target, mode: draft.mode, country: draft.country, text: draft.text.trim(), retryId: retry?.id }, savedId => {
                dirty.current = false;
                if (alive.current && active.current === id) {
                    setDraft(d => ({ ...d, text: '' }));
                    if (!id) navigate(`/chat/${savedId}`);
                }
            });
        } catch (e) { reportError(e); }
    };
    const newChat = () => { setError(''); setSidebar(false); setReady(false); dirty.current = false; navigate('/?new=1'); if (!id && location.search === '?new=1') setReady(true); };
    const rename = async e => { e.preventDefault(); if (!title.trim()) return; try { await store.patch(edit,{ title: [...title.trim()].slice(0,60).join('') }); changed(edit); setEdit(null); } catch (err) { reportError(err); } };
    const remove = async () => { try { await store.remove(deleting); changed(deleting); if (id === deleting) newChat(); setDeleting(null); } catch (err) { reportError(err); } };
    const busy = Boolean(conversation?.pending);
    return <div className={`cw ${collapsed ? 'cw-collapsed' : ''}`}>
        {sidebar && <button className="cw-backdrop" aria-label="Close history" onClick={() => setSidebar(false)} />}
        <aside className={`cw-sidebar ${sidebar ? 'cw-open' : ''}`} aria-label="Chat history">
            <div className="cw-sidebar-head"><strong>Your workspace</strong><button className="cw-mobile-close" aria-label="Close history" onClick={() => setSidebar(false)}><X size={18}/></button></div>
            <button className="cw-new" onClick={newChat}><Plus size={18}/>New Chat</button>
            <label className="cw-search"><Search size={16}/><input aria-label="Search chats" placeholder="Search chats" value={search} onChange={e => setSearch(e.target.value)}/></label>
            <div className="cw-history">{list.filter(c => c.title.toLowerCase().includes(search.toLowerCase())).map(c => <div key={c.id} className={`cw-history-item ${c.id === id ? 'selected' : ''}`}>
                <button className="cw-chat-link" onClick={() => { if (id !== c.id) setReady(false); setError(''); setSidebar(false); navigate(`/chat/${c.id}`); }}><span>{c.title}</span><small>{c.mode === 'warehouse' ? 'Data Q&A' : 'Ask AI'}{c.pending ? ' · Responding…' : ''}</small></button>
                <button aria-label={`Rename ${c.title}`} onClick={() => { setEdit(c.id); setTitle(c.title); }}><Pencil size={14}/></button>
                <button aria-label={`Delete ${c.title}`} onClick={() => setDeleting(c.id)}><Trash2 size={14}/></button>
            </div>)}{!list.length && <p className="cw-muted">Your conversations will appear here.</p>}</div>
            <p className="cw-storage-note">Saved in this browser only. Anyone using this browser profile can view these chats. Clearing browser data removes history.</p>
        </aside>
        <section className="cw-main" aria-label="Chat workspace">
            <header className="cw-top"><button aria-label="Toggle history" onClick={() => { setSidebar(s => !s); setCollapsed(s => !s); }}><Menu size={20}/></button><div><strong>{conversation?.title || 'Start a conversation'}</strong><small>UMOJA International · AI workspace</small></div><button onClick={newChat} title="New Chat" aria-label="New Chat"><Plus size={20}/></button></header>
            {error && <div className="cw-error" role="alert">{error}<button aria-label="Dismiss error" onClick={() => setError('')}><X size={16}/></button></div>}
            <div ref={viewport} className="cw-messages" onScroll={() => { const el = viewport.current; nearBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 100; if (nearBottom.current) setNewResponse(false); }}>
                {!ready ? <p role="status">Restoring your workspace…</p> : !messages.length ? <div className="cw-welcome"><span className="cw-mark"><Sparkles size={30}/></span><h1>What would you like to explore?</h1><p>Ask about your portfolio, analyse a member, or prepare a monthly report.</p><div className="cw-examples">{['Group Performance Report August 2026', 'Show me statistics', 'Credit score for '].map(q => <button key={q} onClick={() => updateDraft({ text: q })}>{q}</button>)}</div></div> : messages.map(m => <Message key={m.id} message={m} busy={busy} onRetry={m => submit(null,m)} onRegenerate={(text,country) => updateDraft({ text, country: country || 'ALL' })}/>)}
            </div>
            {newResponse && <button className="cw-new-response" onClick={() => { viewport.current.scrollTop = viewport.current.scrollHeight; nearBottom.current = true; setNewResponse(false); }}><ArrowDown size={16}/>New response</button>}
            <form className="cw-composer" onSubmit={submit}>
                <div className="cw-options"><label>Mode <select aria-label="Chat mode" value={draft.mode} disabled={Boolean(id)} onChange={e => updateDraft({ mode: e.target.value })}><option value="ask">Ask AI</option><option value="warehouse">Data Q&amp;A</option></select></label><label>Country <select aria-label="Country filter" value={draft.country} disabled={busy} onChange={e => updateDraft({ country: e.target.value })}>{countries.map(([code,name]) => <option value={code} key={code}>{name}</option>)}</select></label>{id && <small>New Chat to change mode</small>}</div>
                <ReportPeriods key={draft.country} country={draft.country} busy={busy} onSelect={text => updateDraft({ text })}/>
                <div className="cw-input"><textarea aria-label="Message" rows={2} maxLength={2000} placeholder="Ask a question or continue this conversation…" value={draft.text} disabled={!ready || Boolean(id && !conversation)} onChange={e => updateDraft({ text: e.target.value })} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void submit(e); } }}/><button aria-label="Send message" type="submit" disabled={!ready || busy || !draft.text.trim() || Boolean(id && !conversation)}><Send size={20}/></button></div>
                <p className="cw-caption">{busy ? 'You can browse other chats while this response is prepared.' : 'Enter to send · Shift + Enter for a new line · Verify financial decisions against source data.'}</p>
            </form>
        </section>
        {edit && <div className="cw-modal-backdrop"><form className="cw-modal" role="dialog" aria-modal="true" aria-label="Rename conversation" onSubmit={rename}><h2>Rename conversation</h2><input aria-label="Conversation title" autoFocus maxLength={60} value={title} onChange={e => setTitle(e.target.value)}/><div><button type="button" onClick={() => setEdit(null)}>Cancel</button><button type="submit">Save</button></div></form></div>}
        {deleting && <div className="cw-modal-backdrop"><div className="cw-modal" role="dialog" aria-modal="true" aria-label="Delete conversation"><h2>Delete conversation?</h2><p>This removes its messages from this browser. It cannot be undone.</p><div><button onClick={() => setDeleting(null)}>Cancel</button><button onClick={remove}>Delete</button></div></div></div>}
    </div>;
}
