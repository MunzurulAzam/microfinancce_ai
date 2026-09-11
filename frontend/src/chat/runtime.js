import { contextFor } from './context';
import { store } from './store';
import { askQuestion, askWarehouse } from '../services/api';

const channel = typeof BroadcastChannel !== 'undefined' ? new BroadcastChannel('umoja-chat') : null;
const listeners = new Set();
export function subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); }
function notify(id) { for (const fn of listeners) fn(id); }
channel?.addEventListener('message', e => notify(e.data));
export function changed(id) { notify(id); channel?.postMessage(id); }
async function locked(id, fn) {
    if (navigator.locks) return navigator.locks.request(`umoja-chat:${id}`, { ifAvailable: true }, lock => {
        if (!lock) throw new Error('A response is already running in another tab.');
        return fn();
    });
    return fn(); // IndexedDB still atomically enforces one pending request.
}
export async function send(options, onStarted) {
    return locked(options.id, async () => {
        const started = await store.begin(options);
        changed(options.id); onStarted?.(options.id);
        let response, error;
        try {
            const messages = await store.messages(options.id);
            const context = contextFor(messages, started.reply.sequence - 1);
            const call = started.conversation.mode === 'warehouse' ? askWarehouse : askQuestion;
            response = await call(started.question, { country: started.reply.country, context });
            if (response.success === false) throw response;
        } catch (e) { if (e && typeof e === 'object' && typeof e.success === 'boolean') response = e; error = e.error || e.answer || e.message || String(e) || 'Request failed. Please retry.'; }
        // Keep pending on a failed storage write, so reload offers an explicit retry.
        await store.finish(options.id, started.requestId, response || null, error ? 'error' : 'complete', error);
        changed(options.id);
    });
}
export async function recover() {
    for (const c of await store.list()) {
        if (!c.pending) continue;
        const interrupt = async () => {
            await store.finish(c.id, c.pending.requestId, null, 'interrupted', 'Interrupted — the request did not finish. Retry when ready.');
            changed(c.id);
        };
        if (navigator.locks) await navigator.locks.request(`umoja-chat:${c.id}`, { ifAvailable: true }, lock => lock ? interrupt() : undefined);
        // Without Web Locks, wait beyond the HTTP timeout before reclaiming a pending request.
        else if (Date.now() - c.pending.startedAt > 240000) await interrupt();
    }
}
