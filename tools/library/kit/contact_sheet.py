"""Generate the full catalogue contact sheet or a compact six-family guide plate."""
import argparse,json,math
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
HERE=Path(__file__).resolve().parent

def draw(out,small=False):
    items=json.loads((HERE/'catalogue.json').read_text())['items']
    styles=['modern','contemporary','scandinavian','country','industrial','traditional','shared']
    kinds=['sofa','dining_chair','dining_table','bed','kitchen_base','table_lamp','plant']
    columns=7 if small else 10
    width=146 if small else 142
    rows=[(style,[i for i in items if i['style']==style and (not small or i['kind'] in kinds)]) for style in styles]
    height=sum(44+math.ceil(len(group)/columns)*(width+27) for _,group in rows if group)
    sheet=Image.new('RGB',(width*columns,height),'#eeeae3');d=ImageDraw.Draw(sheet)
    title=ImageFont.load_default(21);caption=ImageFont.load_default(13)
    y=0
    for style,group in rows:
        if not group:continue
        d.rectangle((0,y,sheet.width,y+40),fill='#35483f')
        d.text((12,y+7),('Country / farmhouse' if style=='country' else style.title())+'  ·  '+str(len(group)),font=title,fill='white')
        y+=44
        for n,entry in enumerate(group):
            x=(n%columns)*width; top=y+(n//columns)*(width+27)
            with Image.open(HERE/entry['thumbnail']) as im:
                sheet.paste(im.convert('RGB').resize((width,width),Image.Resampling.LANCZOS),(x,top))
            d.text((x+5,top+width+4),entry['kind'].replace('_',' '),font=caption,fill='#242b28')
        y+=math.ceil(len(group)/columns)*(width+27)
    out.parent.mkdir(exist_ok=True,parents=True);sheet.save(out,quality=88)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('out',type=Path);p.add_argument('--small',action='store_true');a=p.parse_args();draw(a.out,a.small)
