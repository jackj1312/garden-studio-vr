from pathlib import Path
import json
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor,white,black
from reportlab.lib.pagesizes import A3,landscape
root=Path(__file__).resolve().parents[2];out=root/'renders/garden-tool/studio-concept';out.mkdir(parents=True,exist_ok=True)
f=json.loads((root/'assets/sites/house-wip/layout/approved_2b.json').read_text())['garden']['objects'][0];w=f['geometry']['width'];d=f['geometry']['depth'];s=40*mm;x0=55*mm;y0=23*mm
c=canvas.Canvas(str(out/'tattoo-studio-floor-plan-P01.pdf'),pagesize=landscape(A3));c.setTitle('Tattoo studio - proposed ground floor - first iteration P01')
def pt(x,z):return x0+(x+w/2)*s,y0+(d/2-z)*s
def rect(x,z,a,b,fill='#eeeeea',stroke='#333333'):
 X,Y=pt(x-a/2,z+b/2);c.setFillColor(HexColor(fill));c.setStrokeColor(HexColor(stroke));c.setLineWidth(.55);c.rect(X,Y,a*s,b*s,fill=1)
def label(x,z,text,size=8):
 X,Y=pt(x,z);c.setFillColor(black);c.setFont('Helvetica',size);c.drawCentredString(X,Y,text)
def line(x1,z1,x2,z2):
 c.setStrokeColor(black);c.setLineWidth(.6);c.line(*pt(x1,z1),*pt(x2,z2))
def dim(x1,z1,x2,z2,text):
 a,b=pt(x1,z1);q,r=pt(x2,z2);c.setStrokeColor(HexColor('#666666'));c.setLineWidth(.4);c.line(a,b,q,r)
 for X,Y in [(a,b),(q,r)]:c.line(X-2,Y-2,X+2,Y+2)
 c.setFillColor(black);c.setFont('Helvetica',8)
 if abs(a-q)<1:c.saveState();c.translate(a-4,(b+r)/2);c.rotate(90);c.drawCentredString(0,0,text);c.restoreState()
 else:c.drawCentredString((a+q)/2,b+4,text)
rect(0,0,w,d,'#fafaf7');t=.12
for args in [(-w/2+t/2,0,t,d),(0,-d/2+t/2,w,t),(0,d/2-t/2,w,t)]:rect(*args,fill='#555555')
h=2.4;doorZ=-d*.25;doorW=1;winZ=d*.20;winW=min(2.2,d*.36)
start=-d/2
for lo,hi in [(doorZ-.5,doorZ+.5),(winZ-winW/2,winZ+winW/2)]:
 rect(w/2-t/2,(start+lo)/2,t,lo-start,'#555555');start=hi
rect(w/2-t/2,(start+d/2)/2,t,d/2-start,'#555555')
line(w/2-.07,winZ-winW/2,w/2-.07,winZ+winW/2);line(w/2-.03,winZ-winW/2,w/2-.03,winZ+winW/2)
# Door swing diagram; provisional inward opening.
hx,hz=w/2-.12,doorZ+.5
line(hx,hz,hx-1,hz);X,Y=pt(hx,hz);c.arc(X-s,Y-s,X+s,Y+s,90,90)
wcW=1.35;wcD=1.65;wcX=-w/2+wcW;wcZ=-d/2+wcD
rect(wcX,-d/2+wcD/2,.1,wcD,'#555555');rect(-w/2+(wcW-.8)/2,wcZ,wcW-.8,.1,'#555555')
# WC door swings into WC.
line(wcX-.05,wcZ,wcX-.05,wcZ-.75);X,Y=pt(wcX-.05,wcZ);c.arc(X-.75*s,Y-.75*s,X+.75*s,Y+.75*s,90,90)
rect(-w/2+wcW/2,-d/2+.52,.38,.62);rect(-w/2+wcW/2,-d/2+.24,.40,.18)
rect(-w/2+.34,-d/2+1.25,.38,.32);label(-w/2+.78,-d/2+1.20,'WC',10)
rect(.75,-d/2+.4,1.9,.55);rect(.25,-d/2+.4,.50,.38,'#cad9df');label(.75,-d/2+.91,'CLEANING / SINK',8)
for i,z in [(1,-.28),(2,1.86)]:
 rect(-.45,z,.78,1.9,'#d2dfe1');rect(-.45,z-.68,.60,.40,'#bacdd1');label(-.45,z,'BED '+str(i),9);label(-.45,z+.28,'780 x 1900',7)
 rect(.30,z-.2,.38,.55,'#d9d4c5');label(.30,z-.2,'T'+str(i),7)
rect(-w/2+.37,.15,.5,1.1);label(-w/2+.37,.15,'DRAW',7);rect(-w/2+.90,.15,.45,.45,'#d9d4c5')
rect(w/2-.42,2.25,.55,1.15);c.saveState();X,Y=pt(w/2-.42,2.25);c.translate(X,Y);c.rotate(90);c.setFillColor(black);c.setFont('Helvetica',7);c.drawCentredString(0,0,'WELCOME');c.restoreState()
label(1.05,.25,'STUDIO',10);label(1.05,.55,'circulation',8)
for z in [-d/2,d/2]:line(-w/2-.08,z,-w/2-.65,z)
dim(-w/2-.5,-d/2,-w/2-.5,d/2,f'{d*1000:.0f} overall')
for x in [-w/2,w/2]:line(x,-d/2-.08,x,-d/2-.43)
dim(-w/2,-d/2-.32,w/2,-d/2-.32,f'{w*1000:.0f} overall')
label(w/2+.48,0,'DRIVE',9)
# Right-side drawing information.
L=260*mm;R=405*mm;c.setFillColor(black);c.setFont('Helvetica-Bold',18);c.drawString(L,274*mm,'TATTOO STUDIO')
c.setFont('Helvetica',12);c.drawString(L,265*mm,'Proposed ground floor plan')
c.setFont('Helvetica-Bold',10);c.drawString(L,254*mm,'FIRST ITERATION - NOT FOR SUBMISSION')
notes=[('DRAWING','GS-TS-001 / P01'),('DATE','06 November 2026'),('SCALE','1:25 at A3 - print at 100%'),('FOOTPRINT',f'{w:.3f} x {d:.3f} m / {w*d:.2f} m2 external'),('SOURCE','Saved garden base; no footprint changes'),('ORIENTATION','North is +X (right), from project frame'),('ROOF','Hipped; 2.4 m eaves + 0.8 m rise assumed'),('WALLS','120 mm outer / 100 mm partition assumed')]
y=241*mm
for k,v in notes:
 c.setFont('Helvetica-Bold',8);c.drawString(L,y,k);c.setFont('Helvetica',9);c.drawString(L,y-12,v);y-=25
c.setFont('Helvetica-Bold',10);c.drawString(L,y-5,'DESIGN NOTES');y-=24
texts=['Two beds with separate setup trolleys (T1 / T2).','Cleaning counter with indicative sink; drawing desk','and welcome desk. Equipment is schematic.','WC enclosure nominal 1350 x 1650 mm overall.','Door widths shown: entry 1000 / WC 750 mm.','Door swings, access, drainage, ventilation and','hygiene zoning need review before design freeze.','No accessible WC or turning circle demonstrated.','Boundary offsets and existing site survey are not','part of this drawing. All dimensions in millimetres','unless stated. Do not scale for construction.']
c.setFont('Helvetica',9)
for text in texts:c.drawString(L,y,text);y-=13
c.setFont('Helvetica-Bold',9);c.drawString(L,61*mm,'N');c.line(L,57*mm,L+30*mm,57*mm);c.line(L+30*mm,57*mm,L+26*mm,59*mm);c.line(L+30*mm,57*mm,L+26*mm,55*mm)
c.setFont('Helvetica',8);c.drawString(L,47*mm,'Scale bar (metres)')
for i in range(4):
 c.setFillColor(black if i%2==0 else white);c.rect(L+i*20*mm,37*mm,20*mm,3*mm,fill=1);c.setFillColor(black);c.drawString(L+i*20*mm,33*mm,str(i*.5))
c.drawString(L+80*mm,33*mm,'2.0')
c.setStrokeColor(HexColor('#999999'));c.line(L,23*mm,R,23*mm);c.setFont('Helvetica',8);c.drawString(L,18*mm,'Garden Studio | Concept layout | Sheet 1 of 1')
c.save();print(out/'tattoo-studio-floor-plan-P01.pdf')
