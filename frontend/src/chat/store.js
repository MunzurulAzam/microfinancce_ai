const DB_NAME = 'umoja-chat-workspace';
export const uid = () => crypto.randomUUID();
const request = req => new Promise((resolve, reject) => { req.onsuccess = () => resolve(req.result); req.onerror = () => reject(req.error); });

export function createStore(name = DB_NAME) {
    let connection;
    async function db() {
        if (!connection) connection = new Promise((resolve, reject) => {
            const req = indexedDB.open(name, 1);
            req.onupgradeneeded = () => {
                const database = req.result;
                database.createObjectStore('conversations', { keyPath: 'id' });
                database.createObjectStore('messages', { keyPath: 'id' }).createIndex('conversationId', 'conversationId');
                database.createObjectStore('settings');
            };
            req.onsuccess = () => { req.result.onversionchange = () => { req.result.close(); connection = null; }; resolve(req.result); };
            req.onerror = () => { connection = null; reject(req.error); };
            req.onblocked = () => { connection = null; reject(new Error('Close older app tabs to upgrade chat storage.')); };
        });
        return connection;
    }
    async function transaction(stores, mode, action) {
        const tx = (await db()).transaction(stores, mode);
        const done = new Promise((resolve, reject) => { tx.oncomplete = resolve; tx.onabort = () => reject(tx.error || new Error('History transaction failed')); tx.onerror = () => {}; });
        try { const result = await action(tx); await done; return result; }
        catch (error) { try { tx.abort(); } catch { /* already aborted */ } await done.catch(() => {}); throw error; }
    }
    const read = (store, key) => transaction([store], 'readonly', tx => request(tx.objectStore(store).get(key)));
    return {
        list: () => transaction(['conversations'], 'readonly', async tx => (await request(tx.objectStore('conversations').getAll())).filter(c => !c.deletedAt).sort((a,b) => b.updatedAt - a.updatedAt)),
        get: id => read('conversations', id),
        messages: id => transaction(['messages'], 'readonly', async tx => (await request(tx.objectStore('messages').index('conversationId').getAll(id))).sort((a,b) => a.sequence - b.sequence)),
        setting: key => read('settings', key),
        saveSetting: (key, value) => transaction(['settings'], 'readwrite', tx => request(tx.objectStore('settings').put(value, key))),
        patch: (id, patch) => transaction(['conversations'], 'readwrite', async tx => {
            const s = tx.objectStore('conversations'), c = await request(s.get(id));
            if (!c || c.deletedAt) return;
            // Never accept mode, pending or identifiers through UI metadata edits.
            for (const key of ['title', 'draft', 'country']) if (key in patch) c[key] = patch[key];
            s.put(c);
        }),
        remove: id => transaction(['conversations','messages'], 'readwrite', async tx => {
            const s = tx.objectStore('conversations'), c = await request(s.get(id));
            if (!c) return;
            s.put({ id, deletedAt: Date.now(), updatedAt: Date.now() });
            const messages = tx.objectStore('messages');
            for (const key of await request(messages.index('conversationId').getAllKeys(id))) messages.delete(key);
        }),
        begin: ({ id, mode, country, text, retryId, requestId = uid() }) => transaction(['conversations','messages','settings'], 'readwrite', async tx => {
            const cs = tx.objectStore('conversations'), ms = tx.objectStore('messages');
            let c = await request(cs.get(id));
            if (c?.deletedAt) throw new Error('This conversation was deleted. Start a new chat.');
            if (c?.pending) throw new Error('A response is already running in this conversation.');
            const now = Date.now();
            c ||= { id, mode, country, title: [...text.trim()].slice(0,60).join(''), createdAt: now, updatedAt: now, draft: '', sequence: 0 };
            let reply;
            if (retryId) {
                reply = await request(ms.get(retryId));
                if (!reply || reply.conversationId !== id || !['error','interrupted'].includes(reply.status)) throw new Error('This response cannot be retried.');
                text = reply.question;
            } else {
                ms.put({ id: uid(), conversationId: id, role: 'user', text, status: 'complete', requestId, sequence: ++c.sequence, createdAt: now });
                reply = { id: uid(), conversationId: id, role: 'assistant', question: text, sequence: ++c.sequence, createdAt: now };
            }
            Object.assign(reply, { status: 'pending', requestId, text: '', response: null, country: retryId ? reply.country : country });
            ms.put(reply);
            Object.assign(c, { pending: { requestId, messageId: reply.id, startedAt: now }, updatedAt: now, draft: '' });
            cs.put(c); tx.objectStore('settings').put(id, 'lastActive');
            if (!retryId) tx.objectStore('settings').put({ text: '', mode, country }, 'newDraft');
            return { conversation: c, reply, question: text, requestId };
        }),
        finish: (id, requestId, response, status = 'complete', error = '') => transaction(['conversations','messages'], 'readwrite', async tx => {
            const cs = tx.objectStore('conversations'), ms = tx.objectStore('messages'), c = await request(cs.get(id));
            if (!c || c.deletedAt || c.pending?.requestId !== requestId) return false;
            const m = await request(ms.get(c.pending.messageId));
            Object.assign(m, { status, response, text: error || response?.answer || '', completedAt: Date.now() });
            ms.put(m); c.pending = null; c.updatedAt = Date.now(); cs.put(c); return true;
        }),
    };
}
export const store = createStore();
