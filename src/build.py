from bs4 import BeautifulSoup
import re,os,base64,urllib.parse
SRC="/mnt/user-data/uploads/Desktop/MMM-proto"
uri={}
for f in os.listdir("assets"):
    uri[os.path.splitext(f)[0]]="data:image/webp;base64,"+base64.b64encode(open("assets/"+f,"rb").read()).decode()
def key(p): return re.sub(r"[^a-z0-9]","",os.path.splitext(os.path.basename(p))[0].lower())
def fix_urls(h):
    return re.sub(r"url\('([^']+)'\)",lambda m:"var(--im-"+key(m.group(1))+")",h)
fams=set()
def load(f):
    s=BeautifulSoup(open(os.path.join(SRC,f)).read(),"lxml")
    for l in s.find_all("link",href=re.compile("fonts.googleapis.com/css2")):
        q=urllib.parse.urlparse(l["href"]).query
        for v in urllib.parse.parse_qs(q)["family"]: fams.add(v)
    return s
screens=[]
for k in ["p01","p03","p05","p07","p08","p09","p10"]:
    s=load(k+".html"); root=s.body.find(attrs={"data-pencil-id":True},recursive=False)
    bg=re.search(r"background-color:\s*([^;]+)",s.body.get("style","")); 
    root["class"]="screen"; root["data-screen"]=k
    screens.append(str(root))
# supply lander: swap remote sky photos for local renders, wrap in a 1440 viewport
s=load("supply.html")
for sid in ["jhSCF","A1ZOqb"]:
    e=s.find(attrs={"data-pencil-id":sid}); e["style"]=re.sub(r"url\('[^']*'\)","url('sky/"+sid+".jpeg')",e["style"])
root=s.body.find(attrs={"data-pencil-id":True},recursive=False)
root["style"]=root["style"]+"; flex-shrink: 0"
screens.append('<div class="screen" data-screen="supply" style="width:1440px;overflow:hidden;position:relative;background:#2A8EEA">'+str(root)+'</div>')
modals=[]
for k,mid,scrim in [("m_load","hzvKj","#1A0806B3"),("m_receipt","dbufV","#1A0806B3"),("m_l2","X5sh41","#0D1F17CC"),("m_l3","ka3jm","#101713B8"),("m_l4","AEkhZ","#101713B8"),("m_l5","eSz6T","#0A1A29C7")]:
    s=load(k+".html"); el=s.find(attrs={"data-pencil-id":mid})
    st=el["style"]; st=re.sub(r"(^|;)\s*(left|top|position|z-index):[^;]*","",st)
    el["style"]=st.strip("; ")+"; position: relative"
    w=re.search(r"width:\s*(\d+)px",st).group(1)
    modals.append(f'<div class="modal" data-modal="{k}" data-scrim="{scrim}" style="width:{w}px">{el}</div>')
best={}
for f in fams:
    n=f.split(":")[0]
    if len(f)>len(best.get(n,"")): best[n]=f
fams=set(best.values())
fl="https://fonts.googleapis.com/css2?"+"&".join("family="+urllib.parse.quote(f,safe=":;@.,") for f in sorted(fams))+"&display=swap"
out=open("shell.html").read().replace("__FONTS__",f'<link rel="stylesheet" href="{fl}">').replace("__SCREENS__","\n".join(screens)).replace("__MODALS__","\n".join(modals))
out=fix_urls(out)
used=set(re.findall(r"var\(--im-([a-z0-9]+)\)",out))
css=":root{"+"".join(f"--im-{key(k)}:url('{v}');" for k,v in uri.items() if key(k) in used)+"}"
out=out.replace("</style>",css+"</style>",1)
open("mmm-fun-level-up.html","w").write(out)
print(len(out)//1024,"KB", sorted(fams))
print("unresolved urls:",[u for u in set(re.findall(r"var\(--im-([a-z0-9]+)\)",out)) if key(u) not in [key(k) for k in uri]])
