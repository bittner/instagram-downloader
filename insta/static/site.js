// SPDX-FileCopyrightText: 2026 Peter Bittner <django@bittner.it>
// SPDX-License-Identifier: GPL-3.0-or-later
// Sticky header: slides away when scrolling down, back on the first scroll up.
const hdr=document.querySelector('header');let lastY=window.scrollY;
addEventListener('scroll',()=>{const y=window.scrollY;
 hdr.classList.toggle('away',y>lastY&&y>hdr.offsetHeight);lastY=y;},{passive:true});

// Topic and content-type filters, and the carousel sliders (account pages only).
const chips=document.querySelectorAll('.chips button'),cards=document.querySelectorAll('.card');
document.querySelectorAll('.slides').forEach(s=>{
 const track=s.querySelector('.track'),v=track.querySelectorAll('video,img');let i=0,x0=null,dx=0;
 const place=(px=0)=>track.style.transform=`translateX(calc(${-i*100}% + ${px}px))`;
 const go=n=>{v[i].pause?.();i=(n+v.length)%v.length;place();
  s.querySelector('.count').textContent=`${i+1} / ${v.length}`;};
 s.querySelector('.prev').onclick=()=>go(i-1);s.querySelector('.next').onclick=()=>go(i+1);
 track.addEventListener('pointerdown',e=>{if(e.button)return;x0=e.clientX;dx=0;
  track.classList.add('dragging');track.setPointerCapture(e.pointerId);});
 track.addEventListener('pointermove',e=>{if(x0===null)return;dx=e.clientX-x0;place(dx);});
 const end=()=>{if(x0===null)return;x0=null;track.classList.remove('dragging');
  Math.abs(dx)>s.clientWidth/6?go(i-Math.sign(dx)):place();};
 track.addEventListener('pointerup',end);track.addEventListener('pointercancel',end);
 track.addEventListener('dragstart',e=>e.preventDefault());});
const typeBtns=document.querySelectorAll('.types button');let state={topic:'all',type:'all'};
function apply(){chips.forEach(b=>b.classList.toggle('active',b.dataset.topic===state.topic));
 typeBtns.forEach(b=>b.classList.toggle('active',b.dataset.type===state.type));
 cards.forEach(c=>c.hidden=(state.topic!=='all'&&!(' '+c.dataset.topics+' ').includes(' '+state.topic+' '))
  ||(state.type!=='all'&&c.dataset.type!==state.type));
 const q=new URLSearchParams();if(state.topic!=='all')q.set('topic',state.topic);
 if(state.type!=='all')q.set('type',state.type);
 history.replaceState(null,'',q.size?'#'+q:location.pathname);}
chips.forEach(b=>b.onclick=()=>{state.topic=b.dataset.topic;apply();});
typeBtns.forEach(b=>b.onclick=()=>{state.type=b.dataset.type;apply();});
const h=location.hash.slice(1);
if(h.includes('=')){const q=new URLSearchParams(h);state.topic=q.get('topic')||'all';
 state.type=q.get('type')||'all';}
else if(h){state.topic=h;}
apply();
