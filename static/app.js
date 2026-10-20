'use strict';
const $ = id => document.getElementById(id);
const icon = name => `<svg aria-hidden="true"><use href="#i-${name}"></use></svg>`;
const esc = v => String(v ?? '').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const exampleResume = `JANE DOE
Data Analytics Student

EDUCATION
B.S. in Statistics and Data Science

EXPERIENCE
• Analyzed retail sales data using Python and SQL to identify purchasing patterns.
• Created Tableau dashboards to communicate weekly business metrics to a team of analysts.
• Built machine learning classification models for a university project.
• Collaborated with three classmates to present findings to a course instructor.
• Used Excel to clean and summarize marketing campaign data.`;
const exampleJob = `Junior Data Analyst — Growth Team

We are looking for a data analyst to support product and marketing teams.
Requirements:
• Experience with Python and SQL for data analysis.
• Build clear dashboards and reports using Tableau or similar tools.
• Familiarity with machine learning fundamentals.
• Communicate insights to non-technical audiences.
• Experience with cloud platforms such as AWS or GCP.
• Collaborate across teams to support business decisions.`;
const preview = {
 mode:'example',
 requirements:[
  {text:'Python and SQL for data analysis',status:'matched',evidence:'Analyzed retail sales data using Python and SQL'},
  {text:'Tableau dashboards',status:'matched',evidence:'Created Tableau dashboards'},
  {text:'Machine learning fundamentals',status:'matched',evidence:'Built machine learning classification models'},
  {text:'Communicate insights',status:'partial',evidence:'present findings to a course instructor'},
  {text:'AWS or GCP cloud platforms',status:'not_evidenced',evidence:''},
 ],
 suggestions:[
  {before:'Analyzed retail sales data using Python and SQL to identify purchasing patterns.',after:'Analyzed retail sales data using Python and SQL to identify purchasing patterns.',why:'This already shows relevant Python, SQL, and analysis experience. Keep this evidence-backed statement.',evidence:'Analyzed retail sales data using Python and SQL to identify purchasing patterns.'},
  {before:'Created Tableau dashboards to communicate weekly business metrics to a team of analysts.',after:'Created Tableau dashboards to communicate weekly business metrics to a team of analysts.',why:'Direct evidence of reporting and communicating metrics. No additional claims necessary.',evidence:'Created Tableau dashboards to communicate weekly business metrics to a team of analysts.'},
  {before:'Built machine learning classification models for a university project.',after:'Developed machine learning classification models for a university project.',why:'Makes the action verb more direct without changing the experience.',evidence:'Built machine learning classification models for a university project.'}
 ],
 missing:['Experience with AWS or GCP is not shown in this resume.'],
 summary:'Sample preview. Try an interactive run to view the complete evidence-backed workflow. Never add skills or metrics that are not supported by your resume.'
};
let state = {user:null,status:null,result:preview,lastResume:'',lastJD:'',generatedResume:'',reviews:[],authMode:'register',tab:'home',toastTimer:null};
async function api(path, opts={}) {
  const init = {credentials:'same-origin',...opts};
  if (opts.body && typeof opts.body!=='string') {init.headers = {...(init.headers||{}),'Content-Type':'application/json'};init.body=JSON.stringify(opts.body);}
  let r;
  try {r=await fetch(path,init);} catch {throw Error('Cannot connect to the ResumeFit server. Check that it is running.');}
  let data;
  try {data=await r.json();} catch {throw Error('Unexpected server response.');}
  if(!r.ok) throw Error(typeof data.detail==='string'?data.detail:'Request failed. Please try again.');
  return data;
}
function toast(message){const e=$('toast');e.textContent=message;e.classList.add('show');clearTimeout(state.toastTimer);state.toastTimer=setTimeout(()=>e.classList.remove('show'),4800);}
function updateAccount() {
  const u=state.user;
  $('profileName').textContent=u?u.email.split('@')[0]:'Sign in';
  $('avatar').textContent=u?u.email[0].toUpperCase():'G';
  $('creditCount').textContent=u?`${u.credits} credits`:(state.status?.ai_configured?'3 free credits':'Demo mode');
}
function setTab(tab){
  state.tab=tab;
  for(const v of ['home','facts','history','pricing']){
    $('main'+v[0].toUpperCase()+v.slice(1)).hidden=tab!==v;
    document.querySelector(`[data-nav="${v}"]`).classList.toggle('active',tab===v);
  }
  if(tab==='history') loadHistory();
  if(tab==='facts') loadFacts();
  window.scrollTo({top:0,behavior:'smooth'});
}
function counter(textareaId,countId){const t=$(textareaId);const update=()=>{$(countId).textContent=`${t.value.length.toLocaleString()} / 20,000 characters`;};t.addEventListener('input',update);update();}
function setInputs(resume,jd){$('resumeText').value=resume;$('jobText').value=jd;$('resumeText').dispatchEvent(new Event('input'));$('jobText').dispatchEvent(new Event('input'));}
function statusName(status) {return status==='matched'?'Matched':status==='partial'?'Partial':'Not evidenced';}
function renderResults(result, example=false) {
  state.result=result;
  state.generatedResume='';
  const mode=example?'Sample Preview':result.mode==='ai'?'Real AI · Live analysis':'Rule-based · Interactive demo';
  $('modeBadge').textContent=mode;
  $('modeBadge').classList.toggle('ai',result.mode==='ai');
  $('resultStatusLine').textContent=result.mode==='ai'?'Real AI result · Every factual claim needs your review':example?'Explore the example, then try the interactive demo':'Transparent rule-based demo · OpenAI API key required for context-aware rewriting';
  const reqs=Array.isArray(result.requirements)?result.requirements:[];
  const suggs=Array.isArray(result.suggestions)?result.suggestions:[];
  const gaps=Array.isArray(result.missing)?result.missing:[];
  const matched=reqs.filter(r=>r.status==='matched').length;
  const partial=reqs.filter(r=>r.status==='partial').length;
  state.reviews=suggs.map(r=>({accepted:false,edited:r.after||'',original:r.before||'',evidence:r.evidence||r.before||''}));
  $('resultsContent').innerHTML=`
    <div class="insightStrip" aria-label="Analysis overview">
      <div class="insight"><span class="insightIcon blue">${icon('target')}</span><div><strong>${reqs.length}</strong><small>JD requirements</small></div></div>
      <div class="insight"><span class="insightIcon green">${icon('check')}</span><div><strong>${matched} matched</strong><small>${partial} partially evidenced</small></div></div>
      <div class="insight"><span class="insightIcon amber">${icon('alert')}</span><div><strong>${gaps.length} gaps</strong><small>Not shown in resume</small></div></div>
    </div>
    <article class="resultCard requirementsCard">
      <div class="cardTitle"><span class="bubble">${icon('target')}</span><div><h2>JD Key Requirements</h2><p>Check which requirements your resume actually supports</p></div><span class="tagCount">${reqs.length} requirements</span></div>
      <div class="requirementList">${reqs.map((r,i)=>`<button class="requirementChip ${r.status==='matched'?'match':r.status==='partial'?'partial':'missing'}" data-req="${i}" title="View source evidence"><span class="chipDot"></span>${esc(r.text)}${r.priority==='nice'?' <em class="prio">nice-to-have</em>':''}${r.source==='bank'?' <em class="prio">fact bank</em>':''} <span class="chipArrow">↗</span></button>`).join('')||'<p>No job requirements extracted.</p>'}</div>
      <div class="evidenceInline" id="requirementEvidence" hidden></div>
      <div class="cardFootnote">${icon('shield')} A match means resume evidence was found — not an ATS pass-rate or hiring prediction.</div>
    </article>
    <article class="resultCard bulletsCard">
      <div class="cardTitle"><span class="bubble">${icon('file')}</span><div><h2>Tailored Bullet Points</h2><p>${suggs.some(s=>s.verified)?'Each rewrite passed an automated claim-by-claim check against its source bullet. ':''}Review every rewrite. Accept, edit or leave it unchanged.</p></div><span class="tagCount">${suggs.length} suggestions</span></div>
      <div class="bulletHead"><span></span><span>Before · Original</span><span>After · Proposed</span><span>Why it changed</span></div>
      ${suggs.map((r,i)=>`<div class="bulletRow" data-review-row="${i}"><span class="bulletNumber">${i+1}</span><div class="before">${esc(r.before)}</div><div class="after"><span class="afterText" id="afterText${i}">${esc(r.after)}</span><textarea class="reviewEdit" id="reviewEdit${i}" maxlength="650" aria-label="Edit suggested bullet ${i+1}" hidden>${esc(r.after)}</textarea><div class="reviewActions"><button class="reviewBtn accept" data-accept="${i}" aria-pressed="false">${icon('check')} <span>Accept</span></button><button class="reviewBtn" data-edit="${i}">${icon('edit')} Edit</button><button class="reviewBtn" data-copy="${i}">${icon('copy')} Copy</button></div></div><div class="reason"><strong>Why this changed</strong><p>${esc(r.why||'Rephrased to emphasize relevant, evidenced experience.')}</p><button class="evidenceBtn" data-evidence="${i}">${icon('shield')} Show source proof</button><div class="proofText" id="proof${i}" hidden>“${esc(r.evidence||r.before)}”${Array.isArray(r.claims)&&r.claims.length?`<ul class="claimList">${r.claims.map(c=>`<li class="${c.supported?'ok':'bad'}">${c.supported?'✓':'✗'} ${esc(c.claim)}${c.quote?` <small>— “${esc(c.quote)}”</small>`:''}</li>`).join('')}</ul>`:''}<button class="evidenceBtn" data-savefact="${i}">${icon('shield')} Save to Fact Bank</button></div></div></div>`).join('')||'<p class="notice">No evidence-grounded bullet suggestions could be generated. Add more detailed experience bullets and retry.</p>'}
    </article>
    <div class="bottomResults">
      <article class="resultCard"><div class="cardTitle"><span class="bubble">${icon('alert')}</span><div><h2>Missing Qualifications</h2><p>Not demonstrated in the uploaded resume</p></div><span class="tagCount">${gaps.length} items</span></div><ul class="missingList">${gaps.length?gaps.map(m=>`<li>${esc(m)}</li>`).join(''):'<li>No clear gaps identified.</li>'}</ul>${(result.gap_actions||[]).length?`<h3 class="subhead">Suggested next steps</h3><ul class="missingList actions">${result.gap_actions.map(a=>`<li><strong>${esc(a.requirement)}</strong> — ${esc(a.action)}</li>`).join('')}</ul>`:''}</article>
      <article class="resultCard summary"><div class="cardTitle"><span class="bubble">${icon('light')}</span><div><h2>Summary &amp; Next Steps</h2><p>What to focus on next</p></div></div><p class="summaryText">${esc(result.summary||'Review each suggestion against your original resume before applying.')}</p>${result.mode==='demo'?'<p class="notice">Demo analysis uses conservative text rules, not a language model. Add a server-side OpenAI key for real AI.</p>':''}</article>
    </div>
    ${result.agent?renderTrace(result.agent):''}
    <section class="reviewStudio" id="reviewStudio">
      <div class="studioIntro"><span class="studioIcon">${icon('check')}</span><div><h2>Your review studio</h2><p>Choose exactly which edits to apply to your resume. Original statements are preserved until you accept them.</p></div><span class="studioCount" id="acceptedCount">0 accepted</span></div>
      <div class="studioActions"><button class="reviewPrimary" id="applyChanges">${icon('check')} Apply accepted edits</button><button class="outlineButton" id="exportDocx">${icon('download')} Export Word .docx</button><button class="outlineButton" id="copyResume">${icon('copy')} Copy tailored resume</button></div>
      <div class="studioNotice" id="studioNotice">Export uses your original resume until you apply accepted edits. Word export is a clean single-column layout; original PDF styling is not preserved.</div>
    </section>`;
  document.querySelectorAll('[data-copy]').forEach(b=>b.addEventListener('click',()=>copyText(state.reviews[Number(b.dataset.copy)]?.edited||'')));
  document.querySelectorAll('[data-accept]').forEach(b=>b.addEventListener('click',()=>{
    const idx=Number(b.dataset.accept);state.reviews[idx].accepted=!state.reviews[idx].accepted;
    b.classList.toggle('isAccepted',state.reviews[idx].accepted);
    b.setAttribute('aria-pressed',String(state.reviews[idx].accepted));
    b.querySelector('span').textContent=state.reviews[idx].accepted?'Accepted':'Accept';
    $('acceptedCount').textContent=`${state.reviews.filter(r=>r.accepted).length} accepted`;
  }));
  document.querySelectorAll('[data-edit]').forEach(b=>b.addEventListener('click',()=>{
    const idx=Number(b.dataset.edit),area=$('reviewEdit'+idx),label=$('afterText'+idx);
    if(area.hidden){area.hidden=false;label.hidden=true;area.focus();b.textContent='Save edit';}
    else {const value=area.value.trim();if(value.length<12){toast('Please write a complete bullet.');return;}
      state.reviews[idx].edited=value;label.textContent=value;area.hidden=true;label.hidden=false;b.innerHTML=`${icon('edit')} Edit`;
      $('studioNotice').textContent='Manual edits are your responsibility. Check every metric, qualification and tool before exporting.';
    }
  }));
  document.querySelectorAll('[data-savefact]').forEach(b=>b.addEventListener('click',()=>saveFact(suggs[Number(b.dataset.savefact)].before)));
  document.querySelectorAll('[data-evidence]').forEach(b=>b.addEventListener('click',()=>{
    const pane=$('proof'+b.dataset.evidence);pane.hidden=!pane.hidden;
  }));
  document.querySelectorAll('[data-req]').forEach(b=>b.addEventListener('click',()=>{
    const r=reqs[Number(b.dataset.req)];const pane=$('requirementEvidence');
    pane.hidden=false;pane.textContent=(r.evidence?'Source evidence: “'+r.evidence+'”':'No supporting resume statement found for this requirement.')+' · '+statusName(r.status);
  }));
  $('applyChanges').onclick=applyChanges;
  $('exportDocx').onclick=downloadDocx;
  $('copyResume').onclick=()=>copyText(state.generatedResume||state.lastResume||$('resumeText').value);
  $('originalPre').textContent=example?exampleResume:state.lastResume||'No original resume available.';
  showResultTab('results');
}
function renderTrace(a){
  const t=a.tokens&&(a.tokens.in||a.tokens.out)?` · ${(a.tokens.in||0)+(a.tokens.out||0)} tokens`:'';
  return `<article class="resultCard traceCard"><details><summary><span class="bubble">${icon('shield')}</span><div><h2>How the agent worked</h2><p>${a.llm_calls} model calls · ${a.repair_rounds} repair round(s) · ${(a.dropped||[]).length} rewrite(s) rejected · ${a.seconds}s${t}</p></div></summary><ol class="traceList">${a.steps.map(s=>`<li><strong>${esc(s.step)}</strong> <span>${esc(s.detail)}</span></li>`).join('')}</ol>${(a.dropped||[]).length?`<h3 class="subhead">Rejected rewrites (could not be verified)</h3><ul class="missingList">${a.dropped.map(d=>`<li>${esc(d.fact)} <small>— ${esc(d.reason)}</small></li>`).join('')}</ul>`:''}</details></article>`;
}
async function saveFact(text){
  if(!state.user){showAuth('register');toast('Sign in to use your Fact Bank.');return;}
  try{await api('/api/facts',{method:'POST',body:{text}});toast('Saved to your Fact Bank.');}catch(e){toast(e.message);}
}
async function loadFacts(){
  const box=$('factList');
  if(!state.user){box.innerHTML='<p class="notice">Sign in to build your Fact Bank.</p>';return;}
  try{const d=await api('/api/facts');
    box.innerHTML=d.items.map(f=>`<div class="historyCard"><p>${esc(f.text)}</p><button class="historyDelete" data-delfact="${f.id}">${icon('trash')} Delete</button></div>`).join('')||'<p class="notice">No saved facts yet. Add true statements above, or save them from the results.</p>';
    box.querySelectorAll('[data-delfact]').forEach(b=>b.onclick=async()=>{try{await api('/api/facts/'+b.dataset.delfact,{method:'DELETE'});loadFacts();}catch(e){toast(e.message);}});
  }catch(e){toast(e.message);}
}
async function addFact(){
  const t=$('factText').value.trim();
  if(t.length<14){toast('Write a complete statement (at least 14 characters).');return;}
  if(!state.user){showAuth('register');return;}
  try{await api('/api/facts',{method:'POST',body:{text:t}});$('factText').value='';loadFacts();toast('Fact saved.');}catch(e){toast(e.message);}
}
function applyChanges(){
  let text=state.lastResume||$('resumeText').value;
  if(!text){toast('Run an analysis first.');return;}
  let applied=0;
  for(const r of state.reviews){if(!r.accepted)continue;
    if(text.includes(r.original)){text=text.replace(r.original,r.edited);applied++;}
    else {const lines=text.split('\n');const i=lines.findIndex(l=>l.trim().replace(/^[•*\-]\s*/, '')===r.original.trim());if(i>=0){lines[i]=lines[i].replace(r.original,r.edited);text=lines.join('\n');applied++;}}
  }
  state.generatedResume=text;$('resumeText').value=text;$('resumeText').dispatchEvent(new Event('input'));
  $('studioNotice').textContent=`${applied} accepted edit(s) applied. Review the updated resume in the left input or download it as Word. Your source remains in the Original Resume tab.`;
  toast(`${applied} edit(s) applied to your working resume.`);
}
async function downloadDocx(){
  const resume=state.generatedResume||state.lastResume||$('resumeText').value;
  if(resume.trim().length<25){toast('Provide your resume first.');return;}
  const btn=$('exportDocx');btn.disabled=true;
  try{const res=await fetch('/api/export/docx',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:JSON.stringify({resume})});
    if(!res.ok){let d=await res.json();throw Error(d.detail||'Could not export document.');}
    const blob=await res.blob();const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='ResumeFit_Tailored_Resume.docx';a.click();setTimeout(()=>URL.revokeObjectURL(url),5000);toast('Word resume exported.');
  }catch(e){toast(e.message);}finally{btn.disabled=false;}
}

function showResultTab(name) {
  const res=name==='results';
  $('resultsContent').hidden=!res;
  $('originalContent').hidden=res;
  $('resultsTab').classList.toggle('selected',res);
  $('originalTab').classList.toggle('selected',!res);
}
async function copyText(text){try {await navigator.clipboard.writeText(text);toast('Tailored bullet copied.');}catch{toast('Could not copy. Try selecting the text manually.');}}
async function tailor(){
  const resume=$('resumeText').value.trim(),jd=$('jobText').value.trim();
  if(resume.length<25||jd.length<25){toast('Please enter at least 25 characters in both resume and job description.');return;}
  if(state.status?.ai_configured&&!state.user){showAuth('register');toast('Create a free account to use real AI tailoring.');return;}
  const btn=$('tailorBtn');btn.disabled=true;$('tailorBtnText').textContent=state.status?.ai_configured?'Agent working (planning, retrieving, verifying)… up to a minute':'Analyzing your experience...';
  try {
    const result=await api('/api/tailor',{method:'POST',body:{resume,job_description:jd}});
    state.lastResume=resume;state.lastJD=jd;
    renderResults(result);
    if(state.user&&Number.isInteger(result.credits_remaining)){state.user.credits=result.credits_remaining;updateAccount();}
    toast(result.mode==='ai'?(result.charged===false?'Nothing verifiable to rewrite — no credit was used.':'AI analysis complete. Review all suggestions for accuracy.'):'Demo analysis complete. Configure your AI key to enable real rewriting.');
    if(window.innerWidth<850)$('resultsContent').scrollIntoView({behavior:'smooth',block:'start'});
  }catch(e){toast(e.message);}finally{btn.disabled=false;$('tailorBtnText').textContent='Tailor Resume';}
}
function downloadResult(){
  const r=state.result;if(!r||r.mode==='example'){toast('Run Tailor Resume first to save your own result.');return;}
  const lines=['ResumeFit Analysis',`Mode: ${r.mode==='ai'?'Real AI':'Rule-based demo'}`,'','JD REQUIREMENTS',...(r.requirements||[]).map(x=>`• ${x.text} [${statusName(x.status)}]`),'','TAILORED BULLETS',...(r.suggestions||[]).flatMap((x,i)=>[`${i+1}. BEFORE: ${x.before}`,`   AFTER: ${x.after}`,`   WHY: ${x.why}`,'']),'MISSING QUALIFICATIONS',...(r.missing||[]).map(x=>'• '+x),'','SUMMARY',r.summary||'','', 'Always verify your resume statements.'];
  const blob=new Blob([lines.join('\n')],{type:'text/plain;charset=utf-8'});
  const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='ResumeFit_Analysis.txt';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);toast('Analysis downloaded.');
}
async function loadHistory(){
  const list=$('historyList');
  if(!state.user){list.innerHTML='<div class="emptyState"><h2>Sign in to see your history</h2><p>Your analyses will be saved to your account after each run.</p><button id="historySignIn" class="outlineButton">Create an account / Sign in</button></div>';$('historySignIn').onclick=()=>showAuth('register');return;}
  list.innerHTML='<div class="emptyState">Loading your history...</div>';
  try {
    const data=await api('/api/history');
    if(!data.items.length){list.innerHTML='<div class="emptyState"><h2>No saved analyses yet</h2><p>Try tailoring your first job application.</p></div>';return;}
    list.innerHTML=data.items.map(x=>`<article class="historyCard"><button class="historyOpen" data-run="${x.id}"><span class="bubble">${icon('file')}</span><div class="historyCardTitle">${esc(x.title)}</div><small>${esc(new Date(x.created_at).toLocaleString())} · ${x.mode==='ai'?'AI Analysis':'Demo'}</small></button><button class="historyDelete" data-delete-run="${x.id}" aria-label="Delete analysis">${icon('trash')} Delete</button></article>`).join('');
    list.querySelectorAll('[data-delete-run]').forEach(b=>b.onclick=async()=>{if(!confirm('Delete this analysis permanently?'))return;try{await api('/api/history/'+b.dataset.deleteRun,{method:'DELETE'});loadHistory();toast('Analysis deleted.');}catch(e){toast(e.message);}});
    list.querySelectorAll('[data-run]').forEach(b=>b.onclick=()=>openHistory(Number(b.dataset.run)));
  }catch(e){list.innerHTML=`<div class="emptyState">${esc(e.message)}</div>`;}
}
async function openHistory(id){
  try {const run=await api('/api/history/'+id);state.lastResume=run.resume;state.lastJD=run.job_description;setInputs(run.resume,run.job_description);renderResults(run.result);setTab('home');toast('Your saved analysis has been loaded.');}
  catch(e){toast(e.message);}
}
function showAuth(mode='register'){
  state.authMode=mode;
  $('modalBackdrop').hidden=false;
  $('modalTitle').textContent=mode==='login'?'Welcome back':'Create your free account';
  $('modalSubtitle').textContent=mode==='login'?'Sign in to resume tailoring and view your past analyses.':'Save your history and get 3 free AI credits.';
  $('authSubmit').textContent=mode==='login'?'Sign in':'Create free account';
  $('authToggleText').firstChild.textContent=mode==='login'?"Don't have an account? ":'Already have an account? ';
  $('authToggle').textContent=mode==='login'?'Create one':'Sign in';
  $('password').setAttribute('autocomplete',mode==='login'?'current-password':'new-password');
  $('email').focus();
}
function hideAuth(){$('modalBackdrop').hidden=true;}
async function submitAuth(e){
  e.preventDefault();const btn=$('authSubmit');btn.disabled=true;
  try{
    const endpoint=state.authMode==='login'?'login':'register';
    const data=await api('/api/auth/'+endpoint,{method:'POST',body:{email:$('email').value,password:$('password').value}});
    state.user=data.user;updateAccount();hideAuth();$('password').value='';toast('Signed in successfully!');if(state.tab==='history')loadHistory();
  }catch(err){toast(err.message);}finally{btn.disabled=false;}
}
async function purchase(){
  if(!state.user){showAuth('register');toast('Sign in to purchase credits.');return;}
  try{const data=await api('/api/billing/checkout',{method:'POST'});if(data.url)window.location.assign(data.url);}
  catch(e){toast(e.message);}
}
async function profileClick(){
  if(!state.user){showAuth('login');return;}
  if(confirm(`Signed in as ${state.user.email}\nCredits: ${state.user.credits}\n\nSign out?`)){
    await api('/api/auth/logout',{method:'POST'});state.user=null;updateAccount();toast('Signed out.');if(state.tab==='history')loadHistory();
  }
}
async function uploadFile(file, target){
  if(!file)return;
  if(file.size>5*1024*1024){toast('Maximum file size is 5 MB.');return;}
  if(!/\.(pdf|docx|txt)$/i.test(file.name)){toast('Please upload a PDF, DOCX or TXT file.');return;}
  const label=$(target==='resume'?'resumeFileLabel':'jobFileLabel');
  label.textContent='Reading file...';
  const data=new FormData();data.append('file',file);
  try{const res=await fetch('/api/upload',{method:'POST',credentials:'same-origin',body:data});
    const obj=await res.json();if(!res.ok)throw Error(obj.detail||'File upload failed.');
    const id=target==='resume'?'resumeText':'jobText';$(id).value=obj.text;$(id).dispatchEvent(new Event('input'));
    label.textContent=file.name.length>23?file.name.slice(0,20)+'…':file.name;
    toast(`${file.name} imported. Review the extracted text before tailoring.`);
  }catch(err){label.textContent='Upload';toast(err.message);}
}
function setupUploads(){
  const drop=$('resumeDrop');const picker=$('resumeFile');
  drop.onclick=()=>picker.click();
  drop.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();picker.click();}};
  picker.onchange=()=>{uploadFile(picker.files[0],'resume');picker.value='';};
  for(const type of ['dragenter','dragover'])drop.addEventListener(type,e=>{e.preventDefault();drop.classList.add('dragOver');});
  for(const type of ['dragleave','drop'])drop.addEventListener(type,e=>{e.preventDefault();drop.classList.remove('dragOver');});
  drop.addEventListener('drop',e=>uploadFile(e.dataTransfer.files[0],'resume'));
  $('uploadJobBtn').onclick=()=>$('jobFile').click();
  $('jobFile').onchange=e=>{uploadFile(e.target.files[0],'job');e.target.value='';};
}
async function interactiveDemo(){
  const btn=$('interactiveDemo');btn.disabled=true;
  try{const d=await api('/api/showcase');setInputs(d.resume,d.job_description);
    state.lastResume=d.resume;state.lastJD=d.job_description;renderResults(d.result);
    $('resultsContent').scrollIntoView({behavior:'smooth',block:'start'});
    toast('Interactive sample loaded — explore matches, source evidence and accept/edit controls.');
  }catch(err){toast(err.message);}finally{btn.disabled=false;}
}

function setup(){
  document.querySelectorAll('[data-nav]').forEach(b=>b.onclick=()=>setTab(b.dataset.nav));
  $('brand').onclick=e=>{e.preventDefault();setTab('home');};
  $('sampleResume').onclick=()=>{setInputs(exampleResume,$('jobText').value);toast('Example resume inserted.');};
  $('sampleJob').onclick=()=>{setInputs($('resumeText').value,exampleJob);toast('Example job description inserted.');};
  $('tailorBtn').onclick=tailor;
  $('addFact').onclick=addFact;
  $('interactiveDemo').onclick=interactiveDemo;
  setupUploads();
  $('saveBtn').onclick=downloadResult;
  $('resultsTab').onclick=()=>showResultTab('results');
  $('originalTab').onclick=()=>showResultTab('original');
  $('backResults').onclick=()=>showResultTab('results');
  $('newTailor').onclick=()=>{setInputs('','');state.lastResume='';state.lastJD='';renderResults(preview,true);setTab('home');};
  $('creditsButton').onclick=()=>setTab('pricing');
  $('profileBtn').onclick=profileClick;
  $('freePlanBtn').onclick=()=>{if(!state.user)showAuth('register');else setTab('home');};
  $('purchaseBtn').onclick=purchase;
  $('authForm').onsubmit=submitAuth;
  $('authToggle').onclick=()=>showAuth(state.authMode==='login'?'register':'login');
  $('modalClose').onclick=hideAuth;
  $('modalBackdrop').onclick=e=>{if(e.target===$('modalBackdrop'))hideAuth();};
  document.addEventListener('keydown',e=>{if(e.key==='Escape')hideAuth();});
  counter('resumeText','resumeCount');counter('jobText','jobCount');
  renderResults(preview,true);
  Promise.allSettled([api('/api/status'),api('/api/me')]).then(([a,b])=>{
    if(a.status==='fulfilled')state.status=a.value;
    if(b.status==='fulfilled')state.user=b.value.user;
    updateAccount();
    const qs=new URLSearchParams(location.search);
    if(qs.get('payment')==='success')toast('Payment returned successfully. Credits appear after Stripe webhook verification.');
    if(qs.get('payment')==='cancel')toast('Checkout canceled. No credits were purchased.');
  });
}
window.addEventListener('DOMContentLoaded',setup);
