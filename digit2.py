from PIL import Image; import numpy as np, pandas as pd
U='/root/.claude/uploads/404971f2-04c6-5c7b-999b-994434938137/'
RUNS={  # file, frame L,R,T,B, ymin,ymax, supply
 '2A':('bec991b7',(164,2124,110,982),21.25,28.75,21.0),
 '2B':('9d515e56',(122,2118,108,980),21.0,28.0,21.0),
 'T3':('e4b6ed0c',(124,2120,110,982),24.0,31.0,24.0),
 'T3fine':('0eb8542d',(146,2120,108,980),24.0,25.6,24.0)}
grid=np.round(np.arange(0,5.4001,0.01),3); out=[]
for k,(f,(L,R,T,B),lo,hi,sup) in RUNS.items():
    a=np.array(Image.open(U+f+'-image.png').convert('RGB')).astype(int)
    g=(a[:,:,1]>70)&(a[:,:,1]-a[:,:,0]>35)&(a[:,:,1]-a[:,:,2]>35)
    g[:T+75, R-260:]=False          # legend
    xs=[];ys=[]
    for c in range(L+1,R):
        r=np.nonzero(g[T:B+1,c])[0]
        if len(r):
            # steep segments: take column mean is ok; take median
            xs.append((c-L)/(R-L)*6); ys.append(hi-np.median(r)/(B-T)*(hi-lo))
    xs=np.array(xs); ys=np.array(ys)
    Tg=np.interp(grid,xs,ys,left=np.nan,right=np.nan)
    # gaps where the curve lies on the bottom axis -> supply value
    present=np.zeros_like(grid,bool)
    for x in xs: present[min(int(round(x/0.01)),len(grid)-1)]=True
    Tg=np.where(np.isnan(Tg),np.nan,Tg)
    d=pd.DataFrame({'x':grid,'T':Tg,'run':k,'supply':sup})
    print(k,len(xs),'xrange',xs.min().round(3),xs.max().round(3),'T',np.nanmin(Tg).round(2),np.nanmax(Tg).round(2))
    out.append(d)
D=pd.concat(out); D['rise']=D['T']-D['supply']; D.to_csv('lineA_digitised.csv',index=False)
for k,g in D.groupby('run'):
    print(k,[ (x, round(float(g.loc[g.x==x,'T'].iloc[0]),2)) for x in (0.0,0.05,0.1,0.15,0.3,1.0,2.7,4.4,5.0,5.3,5.4)])
