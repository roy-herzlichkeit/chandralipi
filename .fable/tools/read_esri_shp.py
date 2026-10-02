"""ESRI shapefile (polygon) + dBASE III reader per the published ESRI Shapefile Technical Description (1998)."""
import struct, numpy as np
def read_dbf(p):
    b=open(p,'rb').read(); n,hl,rl=struct.unpack('<IHH',b[4:12]); f=[];o=32
    while b[o]!=0x0D:
        f.append((b[o:o+11].split(b'\0')[0].decode(), b[o+16])); o+=32
    rows=[]
    for r in range(n):
        rec=b[hl+r*rl: hl+(r+1)*rl]; pos=1; v={}
        for name,ln in f: v[name]=rec[pos:pos+ln].decode('latin1').strip(); pos+=ln
        rows.append(v)
    return rows
def read_shp(p):
    b=open(p,'rb').read(); o=100; polys=[]
    while o < len(b):
        num,clen=struct.unpack('>ii',b[o:o+8]); c=b[o+8:o+8+2*clen]; o+=8+2*clen
        st=struct.unpack('<i',c[:4])[0]
        if st==0: polys.append(None); continue
        assert st in (5,15,25), st
        npart,npt=struct.unpack('<ii',c[36:44]); parts=struct.unpack(f'<{npart}i',c[44:44+4*npart])
        pts=np.frombuffer(c[44+4*npart:44+4*npart+16*npt],dtype='<f8').reshape(npt,2)
        polys.append(pts[parts[0]:(parts[1] if npart>1 else npt)])
    return polys
