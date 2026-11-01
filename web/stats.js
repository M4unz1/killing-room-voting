'use strict';
function node(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;}
async function refreshStats(){
 try{
  const response=await fetch('/api/stats',{cache:'no-store'});const data=await response.json();
  if(!response.ok)throw new Error(data.error||'Statistik nicht verfügbar.');
  document.getElementById('scope').textContent=data.scope;
  const metrics=document.getElementById('metrics');metrics.replaceChildren();
  for(const [label,value] of [['Spielrunden',data.runs],['Stimmen',data.votes],['Boss-Siege',data.boss_wins],['Niederlagen',data.boss_deaths]]){
   const box=node('div','metric');box.append(node('strong','',value.toLocaleString('de-DE')),node('span','',label));metrics.append(box);
  }
  const bosses=document.getElementById('bosses');bosses.replaceChildren();
  if(!data.bosses.length)bosses.append(node('p','hint','Noch keine Boss-Ausgänge erfasst.'));
  for(const boss of data.bosses){
   const box=node('article','boss-row');const heading=node('div','result');
   heading.append(node('strong','',`Boss / Level ${boss.boss}`),node('strong','',boss.win_percentage===null?'–':`${boss.win_percentage.toLocaleString('de-DE')} % Siege`));
   const meter=node('progress','');meter.max=100;meter.value=boss.win_percentage||0;meter.setAttribute('aria-label',`Siegrate für Boss ${boss.boss}`);
   box.append(heading,meter,node('p','hint',`${boss.wins} Siege · ${boss.deaths} Niederlagen · ${boss.outcomes} erfasste Ausgänge`));bosses.append(box);
  }
  const popular=document.getElementById('popular');popular.replaceChildren();
  for(const item of data.popular_items){const row=node('div','popular-row');row.append(node('span','',item.id),node('b','',`${item.votes} Stimmen`));popular.append(row);}
  if(!data.popular_items.length)popular.append(node('p','hint','Noch keine Stimmen gespeichert.'));
  document.getElementById('stats-status').textContent='Aktualisiert: '+new Date().toLocaleTimeString('de-DE');
 }catch(error){document.getElementById('stats-status').textContent=error.message;}
}
refreshStats();setInterval(()=>{if(!document.hidden)refreshStats();},15000);
