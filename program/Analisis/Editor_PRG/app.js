'use strict';
const $ = id => document.getElementById(id), D = EDITOR_DATA, E = PRG;
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const number = n => Number.isFinite(n) ? String(Number(n.toPrecision(8))) : '';
const from64 = s => Uint8Array.from(atob(s), c => c.charCodeAt(0));
const filename = () => `M_${String(model.programId || 0).padStart(4, '0')}.PRG`;
let currentKey = 'M_0182.PRG', model = E.parse(from64(D.templates.find(t => t.filename === currentKey).base64), currentKey), selected = 0;
let history = [], stash = {}, custom = [], timer, savedDraft = null;
const STORAGE = 'setex-prg-studio-v1';
try { savedDraft = localStorage.getItem(STORAGE); if (savedDraft) $('draftbar').hidden = false; } catch { }
function toast(message) { $('toast').textContent = message; $('toast').hidden = false; clearTimeout(timer); timer = setTimeout(() => $('toast').hidden = true, 6500); }
function checkpoint() { history.push({ model: E.clone(model), selected }); if (history.length > 30) history.shift(); }
function draftObject() { return { format: 'SETEX-PRG-STUDIO', version: 1, cnfSha256: D.cnf_sha256, model, selected }; }
function autosave() { try { localStorage.setItem(STORAGE, JSON.stringify(draftObject())); } catch { } }
function mutate(action, full = true) { try { checkpoint(); action(); stash[currentKey] = E.clone(model); autosave(); if (full) render(); else { renderSteps(); renderValidation(); $('undo-btn').disabled = !history.length; } } catch (e) { const prev = history.pop(); if (prev) { model = prev.model; selected = prev.selected; } toast(e.message); render(); } }
function functionOptions(line, current) {
    const options = Object.values(D.functions).filter(f => f.lines.includes(Number(line))).sort((a, b) => a.name.localeCompare(b.name));
    let s = ''; if (current && !options.some(f => f.id === current)) s += `<option value="${current}">${esc(D.functions[current]?.name || 'Fungsi tidak dikenal')} · ID ${current} (template)</option>`;
    for (const f of options) s += `<option value="${f.id}" ${f.id === current ? 'selected' : ''}>${esc(f.name)} · ID ${f.id}</option>`;
    return s;
}
function renderLibrary() {
    const q = $('program-search').value.trim().toLowerCase(); const entries = [...D.templates.map(t => ({ key: t.filename, id: t.id, title: t.title, steps: t.steps })), ...custom];
    $('library-count').textContent = entries.length + ' program';
    $('program-list').innerHTML = entries.filter(t => { const m = stash[t.key] || (t.key === currentKey ? model : null); return [m?.title || t.title, m?.programId || t.id, t.key].join(' ').toLowerCase().includes(q); }).map(t => {
        const m = t.key === currentKey ? model : stash[t.key], id = m?.programId || t.id, title = m?.title || t.title, count = m?.steps.length || t.steps;
        return `<button class="program ${t.key === currentKey ? 'active' : ''}" data-program="${esc(t.key)}"><span class="programid">${String(id).padStart(4, '0')}</span><strong>${esc(title)}</strong><small>${count} langkah${stash[t.key] ? ' · draf' : ''}</small></button>`;
    }).join('');
    $('program-list').querySelectorAll('[data-program]').forEach(b => b.onclick = () => {
        stash[currentKey] = E.clone(model); currentKey = b.dataset.program;
        model = stash[currentKey] ? E.clone(stash[currentKey]) : E.parse(from64(D.templates.find(t => t.filename === currentKey).base64), currentKey);
        selected = 0; history = []; render();
    });
}
function summary(step) {
    const r = step.records.find(r => r.line === 1), f = D.functions[r?.functionId]; const c = E.comments(step); if (c) return c;
    if (f?.id === 141) return `${number(r.values[0])} °C · ${number(r.values[2])} min`;
    if (f?.id === 144) return `${number(r.values[0])} min`;
    if (f?.id === 713) return `${number(r.values[1])} L`;
    return step.records.filter(r => r.line).length + ' fungsi';
}
function renderSteps() {
    $('step-count').textContent = model.steps.length; $('record-count').textContent = model.steps.reduce((n, s) => n + s.records.filter(r => r.line).length, 0);
    $('step-list').innerHTML = model.steps.map((s, i) => { const r = s.records.find(r => r.line === 1); return `<button class="stepitem ${selected === i ? 'active' : ''}" data-step="${i}"><span class="stepnum">${String(i + 1).padStart(2, '0')}</span><span class="steptext"><strong>${esc(D.functions[r?.functionId]?.name || 'Fungsi ' + r?.functionId)}</strong><small>${esc(summary(s))}</small></span></button>`; }).join('');
    $('step-list').querySelectorAll('[data-step]').forEach(b => b.onclick = () => { selected = Number(b.dataset.step); renderSteps(); renderDetails(); });
}
function parameterField(r, recordIndex, p, i) {
    const pd = D.parameters[p.definition_id], value = r.values[i], choices = E.choicesFor(D, pd), raw = E.view(E.bytes(r.raw)), meta = raw.getUint16(7 + i * 6, true), fixed = meta !== 0;
    let control;
    if (choices.length) { const sorted = [...choices].sort((a, b) => a.value - b.value); control = `<select data-param="${recordIndex},${i}" ${fixed ? 'disabled' : ''} aria-label="${esc(pd.name)}">${!sorted.some(c => c.value === value) ? `<option value="${value}">${number(value)} · nilai asli</option>` : ''}${sorted.map(c => `<option value="${c.value}" ${c.value === value ? 'selected' : ''}>${esc(c.text)} (${c.value})</option>`).join('')}</select>`; }
    else control = `<div class="control"><input type="number" step="any" data-param="${recordIndex},${i}" value="${number(value)}" ${fixed ? 'disabled' : ''} aria-label="${esc(pd.name)}"><span class="unit">${esc(pd.unit || 'nilai')}</span></div>`;
    const bounds = []; if (!p.index_min) bounds.push('min ' + number(p.minimum)); if (!p.index_max) bounds.push('maks ' + number(p.maximum));
    const hint = fixed ? 'Nilai referensi/formula dipertahankan' : (p.index_min || p.index_max ? 'Batas dinamis dari konfigurasi' : bounds.join(' · '));
    return `<div class="field"><label>${esc(pd.name)}</label>${control}<div class="hint">P${i + 1} · definisi ${pd.id}${hint ? ' · ' + esc(hint) : ''}</div></div>`;
}
function renderDetails() {
    selected = Math.min(Math.max(0, selected), model.steps.length - 1); const step = model.steps[selected], boundary = selected === 0 || selected === model.steps.length - 1;
    const commentRecords = step.records.filter(r => !r.line), manyComments = commentRecords.length > 1;
    let body = `<div class="stepbar"><div><div class="eyebrow">LANGKAH ${String(selected + 1).padStart(2, '0')}</div><h3>${esc(D.functions[step.records.find(r => r.line === 1)?.functionId]?.name || 'Detail langkah')}</h3></div><div class="smallactions"><button id="move-up" ${selected <= 1 || boundary ? 'disabled' : ''}>↑ Naik</button><button id="move-down" ${selected >= model.steps.length - 2 || boundary ? 'disabled' : ''}>↓ Turun</button><button id="duplicate-step" ${boundary ? 'disabled' : ''}>Duplikasi</button><button id="delete-step" class="danger" ${boundary ? 'disabled' : ''}>Hapus</button></div></div><div class="comment"><label for="step-comment">Komentar langkah</label><input id="step-comment" maxlength="61" value="${esc(E.comments(step))}" ${manyComments ? 'disabled' : ''} placeholder="Contoh: MASUK SABUN"><div class="hint">Tampil saat langkah aktif · maksimal 61 karakter ASCII</div></div>`;
    step.records.forEach((r, ri) => {
        if (!r.line) return; const f = D.functions[r.functionId], resource = D.resources[r.line];
        const parameters = f?.parameters || []; const unexplained = r.values.map((value, i) => ({ value, i })).filter(p => p.i >= parameters.length && p.value !== 0);
        body += `<article class="resource"><div class="resourcehead"><div class="resourcetitle"><strong>${r.line === 1 ? 'Fungsi utama' : esc(resource?.name || 'Resource ' + r.line)}</strong><small>Slot ${r.line} · ${r.line === 1 ? 'alur proses utama' : 'fungsi tambahan dalam langkah yang sama'}</small></div>${r.line !== 1 ? `<button class="quiet" data-remove="${ri}" aria-label="Hapus resource ${r.line}">Hapus</button>` : ''}</div><div class="functionbody"><div class="functionselect"><label>Fungsi</label><select data-function="${ri}" ${boundary && r.line === 1 ? 'disabled' : ''} aria-label="Fungsi slot ${r.line}">${functionOptions(r.line, r.functionId)}</select></div><div class="fields">${parameters.map((p, i) => parameterField(r, ri, p, i)).join('')}</div>${!parameters.length ? '<div class="emptyparams">Fungsi ini tidak memiliki parameter yang didefinisikan CNF.</div>' : ''}${unexplained.length ? `<div class="preserved">Nilai tambahan asli dipertahankan: ${unexplained.map(p => 'P' + (p.i + 1) + ' = ' + number(p.value)).join(', ')}. Tidak ada definisinya pada CNF lokal.${r.functionId === 718 ? ' Pada backup grup 002, P6 bernama Mixer Type AT2.' : ''}</div>` : ''}</div></article>`;
    });
    const used = new Set(step.records.map(r => r.line)), lines = Object.values(D.resources).filter(r => r.id !== 1 && !r.disabled && !used.has(r.id) && Object.values(D.functions).some(f => f.lines.includes(r.id)));
    body += `<div class="addresource"><select id="new-resource" aria-label="Resource tambahan" ${!lines.length ? 'disabled' : ''}>${lines.map(r => `<option value="${r.id}">${esc(r.name)} · slot ${r.id}</option>`).join('')}</select><button id="add-resource" ${!lines.length ? 'disabled' : ''}>＋ Tambah fungsi</button></div>`;
    $('step-details').innerHTML = body;
    $('step-comment').onchange = e => mutate(() => E.setComment(step, e.target.value));
    $('move-up').onclick = () => mutate(() => { [model.steps[selected - 1], model.steps[selected]] = [model.steps[selected], model.steps[selected - 1]]; selected--; });
    $('move-down').onclick = () => mutate(() => { [model.steps[selected + 1], model.steps[selected]] = [model.steps[selected], model.steps[selected + 1]]; selected++; });
    $('duplicate-step').onclick = () => mutate(() => { model.steps.splice(selected + 1, 0, E.clone(step)); selected++; });
    $('delete-step').onclick = () => mutate(() => { model.steps.splice(selected, 1); selected = Math.min(selected, model.steps.length - 1); });
    $('step-details').querySelectorAll('[data-function]').forEach(el => el.onchange = () => mutate(() => { const i = Number(el.dataset.function), r = step.records[i]; step.records[i] = E.defaults(D, Number(el.value), r.line); }));
    $('step-details').querySelectorAll('[data-param]').forEach(el => el.onchange = () => { const [ri, i] = el.dataset.param.split(',').map(Number); mutate(() => { step.records[ri].values[i] = el.value === '' ? NaN : Number(el.value); }, false); });
    $('step-details').querySelectorAll('[data-remove]').forEach(el => el.onclick = () => mutate(() => step.records.splice(Number(el.dataset.remove), 1)));
    $('add-resource').onclick = () => mutate(() => { const line = Number($('new-resource').value), f = Object.values(D.functions).filter(f => f.lines.includes(line)).sort((a, b) => a.name.localeCompare(b.name))[0]; step.records.push(E.defaults(D, f.id, line)); step.records.sort((a, b) => a.line - b.line); });
}
function renderValidation() {
    const check = E.validate(model, D), box = $('validation'); box.className = 'validation ' + (check.errors.length ? 'bad' : 'good');
    const undefinedCount = model.steps.reduce((n, s) => n + s.records.filter(r => r.line && D.functions[r.functionId] && r.values.some((v, i) => i >= D.functions[r.functionId].parameter_count && v !== 0)).length, 0);
    box.innerHTML = `<strong>${check.errors.length ? 'Periksa ' + check.errors.length + ' hal sebelum ekspor' : '✓ Struktur program siap diekspor'}</strong>${check.errors.length ? '<ul>' + check.errors.slice(0, 8).map(x => '<li>' + esc(x) + '</li>').join('') + '</ul>' : `<span>${model.steps.length} langkah · Program Start dan Program End tersedia · ${filename()}</span>`}${undefinedCount ? `<div>${undefinedCount} record menyimpan nilai tambahan tanpa definisi CNF; nilai asli tetap disertakan.</div>` : ''}${check.notes.length ? `<details><summary>${check.notes.length} catatan konfigurasi / template</summary><ul>${check.notes.map(x => '<li>' + esc(x) + '</li>').join('')}</ul></details>` : ''}`;
    $('export-prg').disabled = !!check.errors.length;
}
function render() {
    $('workspace-title').textContent = model.title || 'Program tanpa nama'; $('workspace-subtitle').textContent = `Template ${model.filename} · CNF lokal sc777ce`;
    $('program-id').value = model.programId; $('program-title').value = model.title; $('filename').textContent = filename();
    $('undo-btn').disabled = !history.length; renderLibrary(); renderSteps(); renderDetails(); renderValidation();
}
function download(name, data, type) { const blob = new Blob([data], { type }), url = URL.createObjectURL(blob), a = document.createElement('a'); a.href = url; a.download = name; document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 10000); }
function newModel(m, key) { stash[currentKey] = E.clone(model); currentKey = key; model = m; selected = 0; history = []; custom.push({ key, id: m.programId, title: m.title, steps: m.steps.length }); stash[key] = E.clone(model); autosave(); render(); }
$('program-search').oninput = renderLibrary;
$('program-id').onchange = e => mutate(() => model.programId = Number(e.target.value));
$('program-title').onchange = e => mutate(() => model.title = e.target.value);
$('add-step').onclick = () => mutate(() => { const at = Math.min(Math.max(1, selected + 1), model.steps.length - 1); model.steps.splice(at, 0, E.newStep(D)); selected = at; });
$('new-program').onclick = () => { const used = new Set([...D.templates.map(t => t.id), ...custom.map(t => t.id), ...Object.values(stash).map(m => m.programId), model.programId]); let next = Math.max(...used) + 1; if (next > 9999) next = Array.from({ length: 9999 }, (_, i) => i + 1).find(i => !used.has(i)); if (!next) { toast('Seluruh ID program 1–9999 sudah digunakan.'); return; } const header = model.header, m = E.clone(model); m.header = header; m.title = 'PROGRAM BARU'; m.programId = next; m.steps = [E.newStep(D, 1), E.newStep(D, 2)]; m.filename = model.filename; newModel(m, 'baru-' + Date.now()); toast('Program baru memakai header template ' + m.filename + '. Tambahkan langkah di antara Start dan End.'); };
$('undo-btn').onclick = () => { const previous = history.pop(); if (!previous) return; model = previous.model; selected = previous.selected; stash[currentKey] = E.clone(model); autosave(); render(); };
$('save-draft').onclick = () => { autosave(); download(filename().replace('.PRG', '.draft.json'), JSON.stringify(draftObject(), null, 2), 'application/json'); toast('Draf JSON disimpan. Gunakan Ekspor PRG untuk membuat file mesin.'); };
$('export-prg').onclick = () => { try { const b = E.serialize(model, D), check = E.parse(b, filename()); if (check.steps.length !== model.steps.length) throw Error('Verifikasi jumlah langkah gagal.'); download(filename(), b, 'application/octet-stream'); toast(filename() + ' diekspor · ' + b.length.toLocaleString('id-ID') + ' byte · ' + model.steps.length + ' langkah.'); } catch (e) { toast(e.message); renderValidation(); } };
$('import-prg').onclick = () => $('file-prg').click();
$('file-prg').onchange = async e => { const f = e.target.files[0]; if (!f) return; try { const m = E.parse(await f.arrayBuffer(), f.name); newModel(m, 'impor-' + Date.now()); toast('PRG dimuat: ' + f.name); } catch (error) { toast(error.message); } finally { e.target.value = ''; } };
function restoreDraft(s) {
    const d = typeof s === 'string' ? JSON.parse(s) : s; if (d.format !== 'SETEX-PRG-STUDIO' || d.version !== 1 || d.cnfSha256 !== D.cnf_sha256) throw Error('Draf tidak sesuai format atau konfigurasi CNF editor ini.'); const m = d.model;
    if (!m || !Array.isArray(m.steps) || m.steps.length < 2 || m.steps.length > 65535 || !Array.isArray(m.steps[0].records) || typeof m.header !== 'string' || m.header.length !== 768) throw Error('Struktur draf tidak valid.');
    // Serialize/reparse valid drafts as a structural guard; invalid drafts stay editable with validation messages.
    for (const step of m.steps) { if (!Array.isArray(step.records) || !step.records.length) throw Error('Record draf tidak valid.'); for (const r of step.records) if (typeof r.raw !== 'string' || !/^[0-9a-f]{130}$/i.test(r.raw)) throw Error('Byte record draf tidak valid.'); }
    newModel(m, 'draf-' + Date.now()); selected = Math.min(d.selected || 0, m.steps.length - 1); $('draftbar').hidden = true; render(); toast('Draf dipulihkan.');
}
$('restore-draft').onclick = () => { try { restoreDraft(savedDraft); } catch (e) { toast(e.message); } };
$('discard-draft').onclick = () => { $('draftbar').hidden = true; savedDraft = null; try { localStorage.removeItem(STORAGE); } catch { } };
$('load-draft-btn').onclick = () => $('file-draft').click();
$('file-draft').onchange = async e => { const f = e.target.files[0]; if (!f) return; try { restoreDraft(await f.text()); } catch (error) { toast(error.message); } finally { e.target.value = ''; } };
function renderCatalog() { const q = $('catalog-search').value.toLowerCase(); $('catalog-body').innerHTML = Object.values(D.functions).filter(f => [f.id, f.name, ...f.parameters.map(p => D.parameters[p.definition_id].name)].join(' ').toLowerCase().includes(q)).sort((a, b) => a.id - b.id).map(f => `<tr><td>${f.id}</td><td>${esc(f.name)}</td><td>${esc(f.lines.map(l => D.resources[l]?.name || l).join(', ') || 'Belum ditempatkan')}</td><td>${f.parameters.map((p, i) => 'P' + (i + 1) + ' ' + esc(D.parameters[p.definition_id].name)).join('<br>') || '—'}</td></tr>`).join(''); }
$('catalog-btn').onclick = () => { renderCatalog(); $('catalog').showModal(); }; $('close-catalog').onclick = () => $('catalog').close(); $('catalog-search').oninput = renderCatalog;
document.addEventListener('keydown', e => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') { e.preventDefault(); $('save-draft').click(); } });
render();
