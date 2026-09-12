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
 const go=n=>{v[i].pause?.();i=(n+v.length)%v.length;place();s.dataset.index=i;
  s.querySelector('.count').textContent=`${i+1} / ${v.length}`;};
 s.querySelector('.prev').onclick=()=>go(i-1);s.querySelector('.next').onclick=()=>go(i+1);
 track.addEventListener('pointerdown',e=>{if(e.button)return;x0=e.clientX;dx=0;
  track.classList.add('dragging');track.setPointerCapture(e.pointerId);});
 track.addEventListener('pointermove',e=>{if(x0===null)return;dx=e.clientX-x0;place(dx);});
 const end=()=>{if(x0===null)return;x0=null;track.classList.remove('dragging');track.dataset.dragged=Math.abs(dx)>5?'1':'';
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

// Lightbox: a near-full-screen view of a post's photos and videos, on a slide track like the cards.
const box=document.querySelector('.lightbox');
if(box){const stage=box.querySelector('.stage'),count=box.querySelector('.count');
 const track=document.createElement('div');track.className='track';stage.append(track);let n=0,i=0,x0=null,dx=0;
 const place=(px=0)=>track.style.transform=`translateX(calc(${-i*100}% + ${px}px))`;
 const show=()=>{place();count.textContent=n>1?`${i+1} / ${n}`:'';
  [...track.children].forEach((el,k)=>{el.classList.toggle('shown',k===i);if(el.tagName==='VIDEO'){k===i?el.play():el.pause();}});};
 const open=(card,start)=>{const files=[...card.querySelectorAll('.media video,.media img')].map(e=>e.getAttribute('src'));
  track.replaceChildren(...files.map(f=>f.endsWith('.mp4')?Object.assign(document.createElement('video'),{src:f,controls:true,preload:'metadata'})
   :Object.assign(document.createElement('img'),{src:f,alt:'',draggable:false})));
  n=files.length;i=start;card.querySelectorAll('video').forEach(v=>v.pause());
  box.querySelectorAll('.prev,.next').forEach(b=>b.hidden=n<2);track.classList.add('dragging');box.hidden=false;show();
  requestAnimationFrame(()=>track.classList.remove('dragging'));};
 const close=()=>{box.hidden=true;track.replaceChildren();};
 const step=d=>{i=(i+d+n)%n;show();};
 cards.forEach(c=>{const current=()=>+(c.querySelector('.slides')?.dataset.index||0);
  const shown=()=>c.querySelector('.track')?c.querySelectorAll('.track > *')[current()]:c.querySelector('.media > img,.media > video');
  c.querySelector('.expand').onclick=()=>open(c,current());
  // A click on a photo opens it; the slider's pointer capture retargets clicks to the track, so look at the shown slide.
  c.querySelector('.media').addEventListener('click',e=>{if(e.target.closest('button'))return;
   if(c.querySelector('.track')?.dataset.dragged)return;
   if(shown()?.tagName==='IMG'&&(e.target.tagName==='IMG'||e.target.classList.contains('track')))open(c,current());});});
 box.querySelector('.close').onclick=close;box.onclick=e=>{if(e.target===box)close();};
 box.querySelector('.prev').onclick=()=>step(-1);box.querySelector('.next').onclick=()=>step(1);
 addEventListener('keydown',e=>{if(box.hidden)return;
  if(e.key==='Escape')close();else if(e.key==='ArrowLeft'&&n>1)step(-1);else if(e.key==='ArrowRight'&&n>1)step(1);});
 // Swipe (touch or mouse): the track follows the pointer and snaps to the next slide past a threshold.
 track.addEventListener('pointerdown',e=>{if(e.button||n<2)return;x0=e.clientX;dx=0;
  track.classList.add('dragging');track.setPointerCapture(e.pointerId);});
 track.addEventListener('pointermove',e=>{if(x0===null)return;dx=e.clientX-x0;place(dx);});
 const end=()=>{if(x0===null)return;x0=null;track.classList.remove('dragging');
  Math.abs(dx)>60?step(dx<0?1:-1):place();};
 track.addEventListener('pointerup',end);track.addEventListener('pointercancel',end);
 track.addEventListener('dragstart',e=>e.preventDefault());}
