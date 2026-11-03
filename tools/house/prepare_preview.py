"""Build an immutable, private read-only snapshot of the actual studio walkthrough.

    python3 tools/house/prepare_preview.py --candidate assets/sites/house \
      --destination '/…/Garden Studio VR/assets/previews' --owner '/…/assets/sites/house-wip'

The server exposes only files.json entries beneath /preview/<key>/. Source data,
client history and the editable site are never published into this snapshot.
"""
import argparse
import contextlib
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import struct
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from layout_store import effective_furnish, initial, stored

FRONTEND=Path(__file__).resolve().parents[2]
SITE="assets/sites/house-preview"
KIT="tools/library/kit"
VERSIONS=("existing_2022","as_built_now","approved_2b","single_storey_option")
SKIES=("kloofendal_43d_clear_puresky_2k.exr","sky_midday_2k.jpg","sky_midday_4k.jpg")
NORMALS=("red_brick","weathered_plank_siding","wood_floor_deck","grass_ground","brushed_concrete")
NAME=re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\Z")
PRODUCT=re.compile(r"[a-z0-9_]+\.[a-z0-9_]+\Z")
DIGEST=re.compile(r"[a-f0-9]{64}\Z")


def relative(name):
    if not isinstance(name,str) or not name or not all(NAME.fullmatch(x) for x in name.split("/")):
        raise ValueError("Unapproved relative package path: "+repr(name))
    return name


@contextlib.contextmanager
def regular(path):
    """Open every path component without following a symlink, including symlinked parents."""
    path=Path(path).absolute()
    with contextlib.ExitStack() as stack:
        fd=os.open(path.anchor,os.O_RDONLY|os.O_DIRECTORY)
        stack.callback(os.close,fd)
        for part in path.parts[1:-1]:
            if part in (".",".."):raise ValueError("Unresolved source path: "+str(path))
            fd=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
            stack.callback(os.close,fd)
        leaf=os.open(path.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
        stream=stack.enter_context(os.fdopen(leaf,"rb"))
        if not stat.S_ISREG(os.fstat(leaf).st_mode):raise ValueError("Not a regular source file: "+str(path))
        yield stream


def read_json(path):
    with regular(path) as source:return json.load(source)


def encode(obj):
    return (json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode()


def file_hash(stream):
    h=hashlib.sha256()
    for block in iter(lambda:stream.read(1<<20),b""):h.update(block)
    return h.hexdigest()


def require_glb(path, compressed=False):
    with regular(path) as f:
        head=f.read(20)
        if len(head)!=20:raise ValueError("Incomplete GLB: "+str(path))
        tag,schema,size,chunk,kind=struct.unpack("<4sIIII",head)
        if tag!=b"glTF" or schema!=2 or size!=os.fstat(f.fileno()).st_size or kind!=0x4e4f534a or chunk>size-20:
            raise ValueError("Malformed generated model: "+str(path))
        doc=json.loads(f.read(chunk))
    if any("uri" in r for key in ("images","buffers") for r in doc.get(key,[])):
        raise ValueError("Generated GLB has an unexpected external URI: "+str(path))
    if compressed and "EXT_meshopt_compression" not in doc.get("extensionsUsed",[]):
        raise ValueError("Missing Meshopt extension in "+str(path))


def read_layout(owner,version,seed):
    # The live directory lock is shared with publication and other layout operations.
    # Read its committed canonical state only. Never recover or initialise owner data.
    parent=None
    with contextlib.ExitStack() as stack:
        for component in Path(owner).absolute().parts:
            if component in (".",".."):raise ValueError("Unresolved owner directory")
            parent=os.open(component,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent)
            stack.callback(os.close,parent)
        fcntl.flock(parent,fcntl.LOCK_SH)
        try:
            with regular(owner/"layout"/(version+".json")) as f:
                actual=stored(f.read(),owner.name,version)
        except FileNotFoundError:actual=initial(owner.name,version)
    visible=effective_furnish(actual,seed)
    return {**{k:visible[k] for k in ("schema","version","revision","items","wallColours","roomFloors","garden")},
            "site":"house-preview","furnishSeeded":True}


class Package:
    def __init__(self):
        self.files={}
        self.expected={}
        self.model_pairs=[]
        self.models=set()

    def add(self,key,source,digest=None):
        key=relative(key)
        if key in self.files and self.files[key]!=source:raise ValueError("Conflicting preview input: "+key)
        self.files[key]=source
        if digest is not None:
            if not DIGEST.fullmatch(digest):raise ValueError("Invalid recorded SHA for "+key)
            self.expected[key]=digest

    def tree(self,project,folder,eligible):
        base=project/folder
        for directory,subdirs,files in os.walk(base,followlinks=False):
            subdirs[:]=[d for d in subdirs if not d.startswith(".") and not (Path(directory)/d).is_symlink()]
            for f in files:
                path=Path(directory)/f
                if eligible(path):self.add(path.relative_to(project).as_posix(),path)

    def catalogue(self,project):
        base=project/KIT
        cat=read_json(base/"catalogue.json")
        self.add(KIT+"/catalogue.json",encode(cat))
        materials=read_json(base/"materials.json")
        rooms=read_json(base/"room-materials.json")
        self.add(KIT+"/materials.json",encode(materials))
        self.add(KIT+"/room-materials.json",encode(rooms))
        maps={}
        for mat in materials["materials"].values():
            for channel,name in mat.get("maps",{}).items():maps[name]=mat.get("map_sha256",{}).get(channel)
        for r in rooms["files"]:
            maps[r["path"]]=r["sha256"]
        allowed_images=set()
        for name,sha in maps.items():
            if not re.fullmatch(r"maps/[A-Za-z0-9_-]+\.(?:jpg|png)",name):raise ValueError("Invalid reviewed kit map "+name)
            self.add(KIT+"/"+name,base/name,sha)
            allowed_images.add(Path(name).stem)
        for item in cat["items"]:
            key=item["id"]
            if not PRODUCT.fullmatch(key) or item["model"]!="models/"+key+".gltf" or item["thumbnail"]!="thumbs/"+key+".png":
                raise ValueError("Invalid reviewed catalogue entry")
            model=item["model"]
            self.add(KIT+"/"+item["thumbnail"],base/item["thumbnail"])
            doc=read_json(base/model)
            self.add(KIT+"/"+model,encode(doc))
            for r in doc.get("buffers",[]):
                if r.get("uri")!=key+".bin":raise ValueError("Unexpected catalogue buffer")
                name="models/"+r["uri"];self.add(KIT+"/"+name,base/name)
            for r in doc.get("images",[]):
                u=r.get("uri","")
                if not re.fullmatch(r"\.\./textures/[A-Za-z0-9_-]+\.(?:png|jpg)",u) or PurePosixPath(u).stem not in allowed_images:
                    raise ValueError("Unreviewed catalogue image: "+u)
                self.add(KIT+"/"+u[3:],base/u[3:])
        return {i["id"] for i in cat["items"]}

    def site_models(self,site,manifest,owner,known_stock):
        for row in manifest["versions"]:
            v=row["id"];runtime=row.get("furnish_runtime")
            if v not in VERSIONS:raise ValueError("Unreviewed house version "+v)
            fixed=bool(runtime)
            prefix=f"furnish/{v}/fixed" if fixed else v
            files={"glb":prefix+".glb","glb_quest":prefix+"_quest.glb",
                   "glb_quest_meshopt":prefix+"_quest_mo.glb","elements":v+"_elements.json","stages":v+".json"}
            for key,file in files.items():
                if row.get(key,file)!=file:raise ValueError("Unexpected "+key+" for "+v)
                row[key]=file
                if file.endswith(".glb"):self.models.add((site/file,key=="glb_quest_meshopt"))
                self.add(SITE+"/"+file,site/file)
            self.model_pairs.append((site/files["glb_quest"],site/files["glb_quest_meshopt"]))
            seed=None
            variants={}
            if fixed:
                for field in ("seed","variants"):
                    if runtime.get(field)!=f"furnish/{v}/{field}.json":raise ValueError("Invalid furnishing sidecar: "+v)
                raw=read_json(site/runtime["seed"])
                seed={k:raw[k] for k in ("schema","items","wallColours","roomFloors") if k in raw}
                self.add(SITE+"/"+runtime["seed"],encode(seed))
                regj=read_json(site/runtime["variants"]); variants=regj["variants"]
                self.add(SITE+"/"+runtime["variants"],encode({k:regj[k] for k in ("schema","variants","hosts","sourceIds") if k in regj}))
                for key,entry in variants.items():
                    if not re.fullmatch(r"site-[a-f0-9]{64}",key):raise ValueError("Invalid measured model key")
                    for field in ("url","questUrl"):
                        model=entry[field]
                        if not re.fullmatch(r"furnish/models/[a-f0-9]{64}\.gltf",model):raise ValueError("Unexpected measured model "+model)
                        dest=SITE+"/"+model
                        if dest in self.files:continue
                        doc=read_json(site/model)
                        # Keep the immutable recorded model bytes. Its path hash is the
                        # product identity; buffer/image stems are SHA of those actual bytes.
                        self.add(dest,site/model)
                        for group,folder,ext in (("buffers","buffers","bin"),("images","textures","webp")):
                            for r in doc.get(group,[]):
                                uri=r.get("uri","")
                                match=re.fullmatch(r"\.\./"+folder+r"/([a-f0-9]{64})\."+ext,uri)
                                if not match:raise ValueError("Unapproved measured model dependency: "+uri)
                                name="furnish/"+uri[3:]
                                self.add(SITE+"/"+name,site/name,match.group(1))
            view=read_layout(owner,v,seed)
            for item in view["items"]:
                variant=item["variant"]
                if variant not in variants and variant not in known_stock and not (variant=="standard" and item.get("catalogueId") in known_stock):
                    raise ValueError("Saved item variant is unavailable in preview: "+item["id"])
            self.add(SITE+"/layout/"+v+".json",encode(view))


def collect(candidate,owner,project=FRONTEND):
    site=candidate.absolute();owner=owner.absolute();project=project.absolute();out=Package()
    out.add("house.html",project/"house.html")
    out.tree(project,"src",lambda p:p.suffix in (".js",".mjs",".css"))
    out.tree(project,"assets/vendor/three",lambda p:p.suffix in (".js",".mjs",".wasm") or p.name in ("LICENSE","LICENSE.txt","COPYING"))
    for sky in SKIES:out.add("assets/hdri/"+sky,project/"assets/hdri"/sky)
    for source in NORMALS:
        name="assets/textures/"+source+"/normal.jpg";out.add(name,project/name)
    stock=out.catalogue(project)
    manifest=read_json(site/"versions.json")
    manifest={k:manifest[k] for k in ("contract","name","as_built_now","default","versions")}
    if tuple(row["id"] for row in manifest["versions"])!=VERSIONS:raise ValueError("Incomplete house version manifest")
    for row in manifest["versions"]:row["spec_site"]="house-preview"
    out.site_models(site,manifest,owner,stock)
    out.add(SITE+"/versions.json",encode(manifest))
    for name in ("materials.json","regs_map.json","regs.json","spec/catalogue_v1.json","spec/finish_interfaces.json"):
        out.add(SITE+"/"+name,site/name)
    spec=read_json(site/"spec/spec_v1.json")
    spec.get("sources",{}).pop("photos",None)
    out.add(SITE+"/spec/spec_v1.json",encode(spec))
    out.add("assets/planner/house-preview/doors.json",project/"assets/planner/house/doors.json")
    return out


def write_snapshot(package,destination):
    for path,compressed in sorted(package.models):require_glb(path,compressed)
    for original,twin in package.model_pairs:
        if twin.stat().st_mtime_ns<original.stat().st_mtime_ns:
            raise ValueError("Meshopt twin is older than its fixed Quest model: "+str(twin))
    if destination.name!="previews" or destination.parent.name!="assets":raise ValueError("Expected an assets/previews destination")
    destination.mkdir(mode=0o700,parents=True,exist_ok=True)
    if destination.resolve()!=destination.absolute():raise ValueError("Preview destination must not be a symlink")
    with (destination/".prepare.lock").open("a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        current=destination/"current.json"
        reusable={}
        if current.exists():
            previous=read_json(current)["key"]
            if not re.fullmatch(r"[a-f0-9]{20}",previous):raise ValueError("Invalid existing snapshot key")
            for name,sha in read_json(destination/previous/"files.json")["files"].items():
                if DIGEST.fullmatch(sha):reusable[sha]=destination/previous/relative(name)
        with tempfile.TemporaryDirectory(prefix=".incoming-",dir=destination) as temp:
            stage=Path(temp)/"snapshot";stage.mkdir()
            hashes={}
            verified={}
            for name,source in sorted(package.files.items()):
                target=stage/name;target.parent.mkdir(parents=True,exist_ok=True)
                ctx=io.BytesIO(source) if isinstance(source,bytes) else regular(source)
                with ctx as stream:
                    sha=file_hash(stream)
                    if name in package.expected and sha!=package.expected[name]:raise ValueError("Resource digest mismatch: "+name)
                    old=verified.get(sha)
                    if old is None and sha in reusable:
                        possible=reusable[sha]
                        with regular(possible) as f:
                            if file_hash(f)!=sha:raise ValueError("Previous snapshot changed: "+name)
                        old=possible
                    if old is not None:
                        os.link(old,target)
                    else:
                        stream.seek(0)
                        with target.open("xb") as t:shutil.copyfileobj(stream,t,1<<20)
                        with regular(target) as f:
                            if file_hash(f)!=sha:raise ValueError("Source changed during snapshot: "+name)
                        target.chmod(0o444)
                    hashes[name]=sha;verified[sha]=target
            index=encode({"schema":1,"files":hashes})
            key=hashlib.sha256(index).hexdigest()[:20]
            target=destination/key
            if target.exists():
                with regular(target/"files.json") as f:
                    if f.read()!=index:raise ValueError("Snapshot key collision")
                for name,sha in hashes.items():
                    with regular(target/name) as f:
                        if file_hash(f)!=sha:raise ValueError("Immutable snapshot changed: "+name)
            else:
                (stage/"files.json").write_bytes(index)
                (stage/"files.json").chmod(0o444)
                os.replace(stage,target)
            marker=Path(temp)/"current.json"
            marker.write_bytes(encode({"schema":1,"key":key,"site":"house-preview","versions":list(VERSIONS)}))
            with marker.open("rb") as f:os.fsync(f.fileno())
            os.replace(marker,current)
            directory=os.open(destination,os.O_RDONLY|os.O_DIRECTORY)
            try:os.fsync(directory)
            finally:os.close(directory)
    return key,len(hashes)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    for option in ("candidate","destination","owner"):parser.add_argument("--"+option,required=True,type=Path)
    args=parser.parse_args()
    key,n=write_snapshot(collect(args.candidate,args.owner),args.destination)
    print(json.dumps({"key":key,"files":n,"viewer":"/preview/"+key+"/house.html?site=house-preview&version=approved_2b"}))
