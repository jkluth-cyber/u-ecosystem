const nav=["home","timeline","u brain","scenarios","journal","resources","reflections","goals & projects","life balance","u agent","legacy","settings"];
document.querySelector("#nav").innerHTML=nav.map((x,i)=>`<button class="${i===0?"active":""}">${x}</button>`).join("");
const form=document.querySelector("#decision-form"), result=document.querySelector("#result");
const esc=s=>String(s??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]));
form.addEventListener("submit",async e=>{
  e.preventDefault(); result.classList.remove("hidden"); result.innerHTML="<h2>U is thinking with you…</h2>";
  const payload={title:title.value,situation:situation.value,desired_outcome:outcome.value,
    pillars:[...document.querySelectorAll("[name=pillar]:checked")].map(x=>x.value),
    consent:{analyze:analyze.checked,memory:memory.checked,research:false,external_actions:false,sensitive_data:false}};
  try{
    const r=await fetch("/api/jarvis",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({...payload,command:"decide"})});
    const envelope=await r.json(); if(!r.ok) throw new Error(JSON.stringify(envelope));
    const d=envelope.decision;
    result.innerHTML=`<small>U DECISION SYNTHESIS • CONFIDENCE ${Math.round(d.confidence*100)}%</small>
      <h2>${esc(d.recommendation)}</h2>${d.safety_message?`<p>${esc(d.safety_message)}</p>`:""}
      <div class="options">${d.options.map(o=>`<div class="option"><h3>${esc(o.name)}</h3><p>${esc(o.summary)}</p><strong>Next:</strong> ${esc(o.next_step)}<p>Score: ${Math.round(o.score*100)}%</p></div>`).join("")}</div>
      <h3>U Brain intelligence</h3><div class="intelligence">
        <div class="intel-card"><small>TRAJECTORY</small><h3>${esc(d.trajectory.direction)}</h3><p>${Math.round(d.trajectory.confidence*100)}% confidence • review in ${d.trajectory.review_in_days} days</p></div>
        <div class="intel-card"><small>EQUILIBRIUM</small><h3>${Math.round(d.equilibrium.balance*100)}%</h3><p>Pressure pillar: ${esc(d.equilibrium.pressure_pillar)}</p></div>
        <div class="intel-card"><small>RIPPLE ORDER</small><h3>${d.ripple_map.map(x=>esc(x.pillar)).join(" → ")}</h3><p>Backend-computed; UI-rendered</p></div></div>
      <h3>Why</h3><ul>${d.rationale.map(x=>`<li>${esc(x)}</li>`).join("")}</ul>
      <details><summary>Engine trace (${d.engine_trace.length})</summary><div class="trace">${d.engine_trace.map(x=>`<p>${esc(x.engine)} — ${esc(x.result)} ${esc(x.detail)}</p>`).join("")}</div></details>
      <p><small>${esc(d.disclaimer)}</small></p>`;
    result.scrollIntoView({behavior:"smooth"});
  }catch(err){result.innerHTML=`<h2>U could not complete this analysis.</h2><p>${esc(err.message)}</p>`}
});
const emergencyPanel=document.querySelector("#emergency-panel");
document.querySelector("#emergency").onclick=()=>{emergencyPanel.classList.toggle("hidden");emergencyPanel.scrollIntoView({behavior:"smooth"})};
document.querySelector("#emergency-submit").onclick=async()=>{
  const message=document.querySelector("#emergency-message").value.trim();
  const target=document.querySelector("#emergency-result");
  if(message.length<2){target.innerHTML="<p>Please add a brief description.</p>";return}
  const r=await fetch("/api/emergency",{method:"POST",headers:{"content-type":"application/json"},
    body:JSON.stringify({message,immediate_danger:document.querySelector("#immediate-danger").checked,country_code:"US"})});
  const d=await r.json();
  target.innerHTML=`<h3>${esc(d.message)}</h3><ol>${d.steps.map(x=>`<li>${esc(x)}</li>`).join("")}</ol>`;
};
