const state = { dataset: document.getElementById('dataset-select').value, sections: [], applicants: [] };

// Toggle menu buttons
function $(id) { return document.getElementById(id); }
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
        btn.classList.add('active')
        $('view-' + btn.dataset.view).classList.add('active')
    })
})

// Update on dropdown change
document.getElementById('dataset-select').addEventListener('change', e => {
    state.dataset = e.target.value
    loadDataset();
});

async function loadDataset() {
    const res = await fetch(`/api/dataset?dataset=${state.dataset}`);
    const data = await res.json();
    state.sections = data.sections;
    state.applicants = data.applicants;
    renderSections();
    renderApplicants();
    renderSectionPicker();
    loadEligibility();
}

function renderSections() {
  const el = $('sections-list');
  if (!state.sections.length) { el.innerHTML = '<div class="empty">No sections in this dataset.</div>'; return; }
  el.innerHTML = state.sections.map(s => `
    <div class="card">
      <div class="card-head">
        <h3>${s.title}</h3>
        <span class="cid">${s.section_id}</span>
      </div>
      <div class="meta-row">
        <span><b>Term:</b> ${s.term} ${s.year}</span>
        <span><b>Instructor:</b> ${s.instructor || '—'}</span>
        <span><b>Lecture:</b> ${s.lecture_meetings.join(', ') || '—'}</span>
      </div>
      <div class="meta-row" style="margin-top:6px;">
        <span class="pill">${s.la_count} LA</span>
        <span class="pill">${s.uta_count} UTA</span>
        ${s.uta_must_attend_lecture ? '<span class="pill" style="background:var(--brick-soft);color:var(--brick);">UTA must attend lecture</span>' : ''}
        ${s.labs.length === 0 ? '<span class="pill" style="background:var(--brick-soft);color:var(--brick);">No labs defined</span>' : ''}
      </div>
      <div class="meta-row" style="margin-top:6px;">
        <b>Labs:</b>&nbsp;${s.labs.map(l => `${l.lab_id} (${l.meetings.join(', ')})`).join(' · ') || 'none'}
      </div>
    </div>
  `).join('');
}

function renderApplicants() {
  const body = $('applicants-body');
  if (!state.applicants.length) { body.innerHTML = '<tr><td colspan="6" class="empty">No applicants in this dataset.</td></tr>'; return; }
  body.innerHTML = state.applicants.map(a => `
    <tr>
      <td><span class="cid" style="font-size:11px;">${a.applicant_id}</span></td>
      <td><b>${a.name}</b><br><span style="color:var(--ink-soft); font-size:11.5px;">${a.email}</span></td>
      <td>${a.gpa !== null ? a.gpa.toFixed(2) : '—'}</td>
      <td>${a.position_types.join(' / ') || '—'}</td>
      <td>${a.ranked_preferences.map(p => `#${p.rank} ${p.course_id}`).join(', ') || '<i>unranked</i>'}</td>
      <td>${a.skills.map(sk => `<span class="pill">${sk}</span>`).join('') || '—'}</td>
    </tr>
  `).join('');
}

function renderSectionPicker() {
  const sel = $('section-select');
  sel.innerHTML = state.sections.map(s => `<option value="${s.section_id}">${s.section_id}</option>`).join('');
  sel.onchange = loadEligibility;
}

$('elig-min-gpa').addEventListener('change', loadEligibility);
$('elig-min-gpa-uta').addEventListener('change', loadEligibility);

async function loadEligibility() {
  const minGpa = $('elig-min-gpa').value;
  const minGpaUta = $('elig-min-gpa-uta').value;
  const params = new URLSearchParams({ dataset: state.dataset });
  if (minGpa) params.set('min_gpa', minGpa);
  if (minGpaUta) params.set('min_gpa_uta', minGpaUta);

  const res = await fetch(`/api/eligibility?${params.toString()}`);
  const data = await res.json();
  const sectionId = $('section-select').value;
  const row = data.rows.find(r => r.section_id === sectionId) || data.rows[0];
  const body = $('eligibility-body');
  if (!row) { body.innerHTML = '<tr><td colspan="4" class="empty">No sections available.</td></tr>'; return; }

  body.innerHTML = row.cells.map(c => `
    <tr>
      <td>${c.applicant_name} <span style="color:var(--ink-soft); font-size:11px;">(${c.applicant_id})</span></td>
      <td>${c.position}</td>
      <td>
        ${c.eligible ? '<span class="stamp ok">ELIGIBLE</span>' : '<span class="stamp no">INELIGIBLE</span>'}
        ${!c.eligible ? `<div class="reasons">${c.reasons.join(' · ')}</div>` : ''}
      </td>
      <td>${c.eligible ? c.score.toFixed(2) : '—'}</td>
    </tr>
  `).join('');
}

$('solve-btn').addEventListener('click', async () => {
  const body = {
    dataset: state.dataset,
    min_gpa: $('solve-min-gpa').value || null,
    min_gpa_uta: $('solve-min-gpa-uta').value || null,
    weights: {
      grade_weight: $('w-grade').value,
      experience_weight: $('w-exp').value,
      recommendation_weight: $('w-rec').value,
      preference_weight: $('w-pref').value,
      skill_match_weight: $('w-skill').value,
      uta_readiness_bonus: $('w-uta').value,
    },
  };
  const res = await fetch('/api/solve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  renderSolveResults(data);
});

function renderSolveResults(data) {
  const el = $('solve-results');
  const rows = data.assignments.map(a => `
    <tr>
      <td>${a.applicant_name} (${a.applicant_id})</td>
      <td>${a.section_id}</td>
      <td>${a.position}</td>
      <td>${a.score.toFixed(2)}</td>
    </tr>
  `).join('') || '<tr><td colspan="4" class="empty">No assignments made.</td></tr>';

  el.innerHTML = `
    <div class="result-summary">
      <div><b>Total score</b> ${data.total_score}</div>
      <div><b>Nodes explored</b> ${data.nodes_explored}</div>
      <div><b>${data.optimal ? 'Optimal ✓' : 'Node limit hit — best found'}</b></div>
    </div>
    <table>
      <thead><tr><th>Applicant</th><th>Section</th><th>Position</th><th>Score</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    ${data.unfilled_slots.length ? `
      <div style="margin-top:16px;">
        <div style="font-size:11px; text-transform:uppercase; letter-spacing:.03em; color:var(--ink-soft); margin-bottom:6px;">Unfilled slots (${data.unfilled_slots.length})</div>
        <ul class="unfilled-list">${data.unfilled_slots.map(s => `<li>${s}</li>`).join('')}</ul>
      </div>` : ''}
  `;
}

loadDataset();