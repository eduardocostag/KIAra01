(()=>{
  if(matchMedia('(prefers-reduced-motion: reduce)').matches)return;
  const selectors=['.portrait img','.portrait video','.photo img','.photo video','.visual img','.visual video','.portrait-person'];
  const media=[...new Set(selectors.flatMap(selector=>[...document.querySelectorAll(selector)]))];
  media.forEach((element,index)=>{
    if(element.closest('[data-cinema-scene]'))return;
    const stage=element.parentElement;
    stage.classList.add('character-motion-stage');
    element.classList.add('character-motion-media');
    element.style.setProperty('--character-delay',`${index*-.7}s`);
    let frame=0,targetX=0,targetY=0,currentX=0,currentY=0,scrollLift=0;
    const render=()=>{
      currentX+=(targetX-currentX)*.08;
      currentY+=(targetY-currentY)*.08;
      element.style.setProperty('--character-x',`${currentX.toFixed(2)}px`);
      element.style.setProperty('--character-y',`${(currentY+scrollLift).toFixed(2)}px`);
      element.style.setProperty('--character-rx',`${(-currentY*.18).toFixed(2)}deg`);
      element.style.setProperty('--character-ry',`${(currentX*.18).toFixed(2)}deg`);
      frame=requestAnimationFrame(render);
    };
    stage.addEventListener('pointermove',event=>{
      const box=stage.getBoundingClientRect();
      targetX=((event.clientX-box.left)/box.width-.5)*13;
      targetY=((event.clientY-box.top)/box.height-.5)*10;
    });
    stage.addEventListener('pointerleave',()=>{targetX=0;targetY=0});
    const onScroll=()=>{
      const box=stage.getBoundingClientRect();
      const progress=Math.max(-1,Math.min(1,(innerHeight/2-(box.top+box.height/2))/innerHeight));
      scrollLift=progress*-12;
    };
    addEventListener('scroll',onScroll,{passive:true});
    new IntersectionObserver(entries=>{
      const visible=entries[0].isIntersecting;
      stage.classList.toggle('character-visible',visible);
      if(visible&&!frame){onScroll();render()}
      if(!visible&&frame){cancelAnimationFrame(frame);frame=0}
    },{rootMargin:'120px'}).observe(stage);
  });
  const style=document.createElement('style');
  style.textContent=`
    .character-motion-stage{perspective:1100px;transform-style:preserve-3d}
    .character-motion-media{--character-x:0px;--character-y:0px;--character-rx:0deg;--character-ry:0deg;transform-origin:50% 82%!important;transform:translate3d(var(--character-x),var(--character-y),18px) rotateX(var(--character-rx)) rotateY(var(--character-ry)) scale(1.045)!important;opacity:0;filter:brightness(.96);transition:opacity .85s cubic-bezier(.2,.8,.2,1),filter .5s;animation:character-breathe 5.8s var(--character-delay,0s) ease-in-out infinite alternate!important;will-change:transform}
    .character-visible .character-motion-media{opacity:1;filter:brightness(1)}
    @keyframes character-breathe{0%{scale:1}50%{scale:1.012}100%{scale:1.004}}
    @media(max-width:760px){.character-motion-media{transform:translate3d(calc(var(--character-x)*.45),calc(var(--character-y)*.45),8px) rotateY(calc(var(--character-ry)*.4)) scale(1.035)!important}}
  `;
  document.head.appendChild(style);
})();
