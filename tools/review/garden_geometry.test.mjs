import test from 'node:test';
import assert from 'node:assert/strict';
import {
  circle, rectangle, arc, point, isClosed, fitStroke, sampleGeometry, validateGeometry,
  measureGeometry, outlineMeasurements, centerOf, handlesOf, moveHandle, transformGeometry,
} from '../../src/garden/geometry.mjs';

const TAU = 2 * Math.PI;
const close = (actual, expected, tolerance=1e-7) =>
  assert.ok(Math.abs(actual-expected)<=tolerance, `${actual} differs from ${expected} by more than ${tolerance}`);
const closePoint = (actual, expected, tolerance) => expected.forEach((v,i)=>close(actual[i],v,tolerance));
const roundStroke = (cx,cz,r,start,sweep,n,jitter=0) => Array.from({length:n+1},(_,i)=>{
  const t=start+sweep*i/n, rr=r+jitter*Math.sin(i*1.71);
  return [cx+rr*Math.cos(t),cz+rr*Math.sin(t)];
});
const corner = p => ({p,in:p,out:p,mode:'corner'});
const poly = points => ({type:'curve',closed:true,knots:points.map(corner)});

test('exact primitive dimensions and measurements survive resize, translation and rotation',()=>{
  const r=rectangle([2,1],4,3,Math.PI/3), metrics=measureGeometry(r);
  assert.deepEqual(metrics,{area:12,perimeter:14,width:4,depth:3});
  const changed=transformGeometry(r,{offset:[3,-2],angle:.4,scale:[2,.5]});
  assert.equal(changed.type,'rectangle');closePoint(changed.center,[5,-1]);
  close(changed.width,8);close(changed.depth,1.5);close(changed.yaw,Math.PI/3+.4);
  const c=transformGeometry(circle([1,0],2),{origin:[0,0],scale:[1.5,1],angle:Math.PI/2});
  closePoint(c.center,[0,1.5]);close(c.radius,3);close(measureGeometry(c).area,9*Math.PI);
  assert.throws(()=>transformGeometry(c,{scale:[2,.5]}),/same scale/);
  closePoint(centerOf(point([2,.7],.4)),[2,.7]);
  assert.equal(measureGeometry(point([0,0])).perimeter,0);
});

test('hand-drawn circle becomes an exact primitive and subtle wobble does not create redundant knots',()=>{
  const g=fitStroke(roundStroke(2,-1,3,0,TAU,90,.035),{closed:true});
  assert.equal(g.type,'circle');closePoint(g.center,[2,-1],.015);close(g.radius,3,.017);
  const line=fitStroke(Array.from({length:100},(_,i)=>[i*.035,.008*Math.sin(i)]));
  assert.equal(line.type,'curve');assert.equal(line.closed,false);assert.equal(line.knots.length,2);
  close(measureGeometry(line).perimeter,distEnds(line),1e-7);
});
function distEnds(g) {
  return Math.hypot(g.knots.at(-1).p[0]-g.knots[0].p[0],g.knots.at(-1).p[1]-g.knots[0].p[1]);
}

test('a drawn circular sweep is a genuine arc, with sign and exact three-point construction',()=>{
  const raw=roundStroke(1,4,2,.3,-Math.PI*.8,48,.012);
  const a=fitStroke(raw);
  assert.equal(a.type,'arc');assert.ok(a.sweepAngle<0);close(a.radius,2,.025);
  close(measureGeometry(a).perimeter,a.radius*-a.sweepAngle);
  const sparse=fitStroke(roundStroke(3,-4,2,.25,Math.PI/2,2),{mode:'arc'});
  closePoint(sparse.center,[3,-4]);close(sparse.radius,2);close(sparse.startAngle,.25);close(sparse.sweepAngle,Math.PI/2);
  assert.throws(()=>fitStroke([[0,0],[1,0],[2,0]],{mode:'arc'}),/curved sweep/);
});

test('rotated rectangle from four precise corners keeps measured size; resize anchors opposite corner',()=>{
  const source=rectangle([7,2],3,1.5,.22);
  const fit=fitStroke(sampleGeometry(source),{closed:true});
  assert.equal(fit.type,'rectangle');close(Math.min(fit.width,fit.depth),1.5,1e-6);close(Math.max(fit.width,fit.depth),3,1e-6);
  const oldHandles=handlesOf(source),fixed=oldHandles.find(h=>h.id==='corner:2');
  const desired=oldHandles.find(h=>h.id==='corner:0').point.map(v=>v-.4);
  const next=moveHandle(source,'corner:0',desired);
  closePoint(handlesOf(next).find(h=>h.id==='corner:2').point,fixed.point);
  closePoint(handlesOf(next).find(h=>h.id==='corner:0').point,desired);
  assert.throws(()=>moveHandle(source,'corner:0',fixed.point),/dimensions/);
});

test('sampling respects circle sagitta and keeps a single closing vertex',()=>{
  const c=circle([0,0],1.5),sample=sampleGeometry(c,.004);
  assert.notDeepEqual(sample[0],sample.at(-1));
  for(let i=0;i<sample.length;i++){
    const a=sample[i],b=sample[(i+1)%sample.length],mid=[(a[0]+b[0])/2,(a[1]+b[1])/2];
    assert.ok(c.radius-Math.hypot(...mid)<=.004+1e-8);
  }
  const quarter=arc([0,0],4,0,Math.PI/2),q=sampleGeometry(quarter);
  closePoint(q[0],[4,0]);closePoint(q.at(-1),[0,4]);
  close(measureGeometry(quarter).width,4);close(measureGeometry(quarter).depth,4);
  assert.ok(isClosed(c));assert.ok(!isClosed(quarter));
});

test('closing a Bezier path measures its analytic area including curvature',()=>{
  // Unit rectangle under y=1 plus an exact quadratic arch 4t(1−t) above it.
  const g={type:'curve',closed:true,knots:[
    corner([0,0]),corner([1,0]),{...corner([1,1]),out:[2/3,7/3]},
    {...corner([0,1]),in:[1/3,7/3]},
  ]};
  validateGeometry(g);
  const m=measureGeometry(g);
  close(m.area,1+2/3);close(m.depth,2);close(m.width,1);
  closePoint(centerOf(g),[.5,1]);
  close(m.perimeter,3+Math.sqrt(17)/2+Math.asinh(4)/8, .0001);
  close(measureGeometry(transformGeometry(g,{offset:[14,-3]})).area,m.area);
});

test('outline dimensions report intrinsic rectangle sides, the circle radius and signed arc midpoint',()=>{
  const r=outlineMeasurements(rectangle([1,3],4,2,Math.PI/2));
  close(r.width,4);close(r.depth,2);close(r.area,8);close(r.perimeter,12);
  assert.deepEqual(r.segments.map(s=>s.label),['Side 1','Side 2','Side 3','Side 4']);
  [4,2,4,2].forEach((n,i)=>close(r.segments[i].length,n));
  [[2,3],[1,5],[0,3],[1,1]].forEach((p,i)=>closePoint(r.segments[i].at,p));
  const c=outlineMeasurements(circle([2,3],2));
  close(c.radius,2);close(c.width,4);close(c.depth,4);close(c.area,Math.PI*4);
  assert.equal(c.segments.length,1);assert.equal(c.segments[0].label,'Circumference');
  close(c.segments[0].length,4*Math.PI);closePoint(c.segments[0].at,[2,1]);
  const a=outlineMeasurements(arc([4,1],2,Math.PI,-Math.PI/2));
  close(a.radius,2);close(a.segments[0].length,Math.PI);assert.equal(a.segments[0].label,'Arc');
  closePoint(a.segments[0].at,[4-Math.SQRT2,1+Math.SQRT2]);
});

test('concave and curved outline lengths follow the controlled path and label its measured halfway point',()=>{
  const concave=outlineMeasurements(poly([[0,0],[4,0],[4,1],[2,1],[2,3],[0,3]]));
  close(concave.area,8);close(concave.perimeter,14);close(concave.width,4);close(concave.depth,3);
  assert.deepEqual(concave.segments.map(s=>s.length),[4,1,2,2,2,3]);
  const arch={type:'curve',closed:true,knots:[
    corner([0,0]),corner([1,0]),{...corner([1,1]),out:[2/3,7/3]},
    {...corner([0,1]),in:[1/3,7/3]},
  ]};
  const m=outlineMeasurements(arch),s=m.segments[2];
  close(m.area,5/3);close(m.width,1);close(m.depth,2);
  close(m.perimeter,m.segments.reduce((v,e)=>v+e.length,0));
  assert.equal(s.label,'Curve 3');close(s.length,Math.sqrt(17)/2+Math.asinh(4)/8,.00002);
  closePoint(s.at,[.5,2],.000001);

  // Cubic x=t³,z=t has nonuniform speed. Use an independent fine polyline
  // to find the halfway station and distinguish it from the point at t=.5.
  const asymmetric={type:'curve',closed:false,knots:[
    {...corner([0,0]),out:[0,1/3]},{...corner([1,1]),in:[0,2/3]},
  ]};
  const measured=outlineMeasurements(asymmetric).segments[0];
  const cumulative=[0],steps=10000;
  for(let i=1;i<=steps;i++){
    const t=i/steps,last=(i-1)/steps;
    cumulative.push(cumulative[i-1]+Math.hypot(t**3-last**3,t-last));
  }
  const half=cumulative.at(-1)/2,k=cumulative.findIndex(s=>s>=half);
  const t=((k-1)+(half-cumulative[k-1])/(cumulative[k]-cumulative[k-1]))/steps;
  close(measured.length,cumulative.at(-1),.00002);closePoint(measured.at,[t**3,t],.000005);
});

test('knot movement translates both controls and dragging a smooth handle preserves its opposite tangent',()=>{
  const g={type:'curve',closed:false,knots:[
    corner([0,0]),{p:[2,1],in:[1,1],out:[3.5,1],mode:'smooth'},corner([5,0]),
  ]};
  const moved=moveHandle(g,'out:1',[2,3]),k=moved.knots[1];
  closePoint(k.in,[2,0]);closePoint(k.out,[2,3]);closePoint(g.knots[1].in,[1,1]);
  const translated=moveHandle(moved,'knot:1',[4,3]).knots[1];
  closePoint(translated.in,[4,2]);closePoint(translated.out,[4,5]);
  assert.ok(handlesOf(moved).some(h=>h.id==='in:1'));
});
test('curve fitting limits noisy contours to a few editable anchors',()=>{
  const raw=Array.from({length:201},(_,i)=>{
    const t=i/200;return [t*8,Math.sin(2*Math.PI*t)+.012*Math.sin(i*2.1)];
  });
  const g=fitStroke(raw,{mode:'curve'});
  assert.ok(g.knots.length>=4 && g.knots.length<=12);
  assert.ok(g.knots.slice(1,-1).every(k=>k.mode==='smooth'));
});

test('reject malformed geometry, zero dimensions, crossed contours and touching non-neighbouring edges',()=>{
  assert.throws(()=>circle([0,0],0));assert.throws(()=>rectangle([0,0],2,NaN));
  assert.throws(()=>arc([0,0],1,0,TAU));assert.throws(()=>point([0,Infinity]));
  assert.throws(()=>validateGeometry(poly([[0,0],[2,2],[0,2],[2,0]])),/crosses/);
  assert.throws(()=>validateGeometry(poly([[0,0],[3,0],[3,3],[1,0],[0,3]])),/crosses|doubles back/);
  assert.throws(()=>fitStroke([[0,0],[2,2],[0,2],[2,0]],{closed:true}),/crosses/);
  assert.throws(()=>moveHandle(poly([[0,0],[2,0],[2,2],[0,2]]),'knot:1',[1,3]),/crosses/);
});

test('arc handle edits keep the opposite endpoint, radius and sweep direction',()=>{
  const a=arc([0,0],2,Math.PI/4,-Math.PI/2);
  const b=moveHandle(a,'end',[0,-8]);
  close(b.startAngle,a.startAngle);close(b.radius,2);close(b.sweepAngle,-3*Math.PI/4);
  const c=moveHandle(a,'radius',[0,3]);
  close(c.radius,3);close(c.sweepAngle,a.sweepAngle);
});

test('open rough runs preserve a real corner and avoid accidental circle classification',()=>{
  const raw=[[0,0],[1,.01],[2,0],[3,0],[3,.8],[3,1.6],[3,2]];
  const g=fitStroke(raw,{mode:'straight'});
  assert.equal(g.knots.length,3);assert.equal(g.knots[1].mode,'corner');
  closePoint(g.knots[1].p,[3,0]);close(measureGeometry(g).perimeter,5);
});

test('stored geometry round-trips without replacement points or hidden runtime state',()=>{
  const shapes=[point([2,-3],.87),arc([1,.5],2,.3,-1),rectangle([0,1],2,3,.5),
    fitStroke([[0,0],[2,1],[3,0],[4,-1]],{mode:'curve'})];
  for(const g of shapes){
    const stored=JSON.parse(JSON.stringify(g));
    assert.deepEqual(validateGeometry(stored),g);
    assert.deepEqual(handlesOf(stored),handlesOf(g));
  }
});
