"""figures/B3_contrasts_plain.{png,pdf} - the B3.2 anchor contrasts, plain table.

The same content as `make_B3_contrasts.py` with the interval printed as text
instead of drawn. Use this one where a figure would be out of place (a slide of
prose, an email body) and the drawn version where the reader should *see* that
one interval crosses zero and the other does not.

Every value is read from the run's own gate output; nothing is typed in here.

    python figures/make_B3_contrasts_plain.py
"""
import json, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
S,INK,INK2,MUT,HAIR,AX = "#fcfcfb","#0b0b0b","#52514e","#898781","#e1e0d9","#c3c2b7"
CRIT,SER = "#d03b3b","#ec835a"
g=json.load(open("/orcd/data/gabrieli/001/guna23/iclr_risk_2027/trackB/b3_lora_70b/gate_b3.json"))
C=g["contrasts"]
ROWS=[("preference","preference − reference"),("bias","bias − reference")]
COLS=[(0.020,"CONTRAST","left"),(0.300,"PLANTED","right"),(0.415,"MEASURED","right"),
      (0.632,"95% INTERVAL","right"),(0.690,"VERDICT","left")]
fig=plt.figure(figsize=(12.2,2.45),dpi=200); fig.patch.set_facecolor(S)
ax=fig.add_axes([0,0,1,1]); ax.set_xlim(0,1); ax.set_ylim(0,1); ax.axis("off")
T=dict(transform=ax.transAxes)
ax.text(0.020,0.885,"The anchor is the contrast, and only one of them resolves",
        fontsize=14,color=INK,va="bottom",**T)
for x,lab,ha in COLS:
    ax.text(x,0.700,lab,fontsize=8.5,color=MUT,va="bottom",ha=ha,**T)
ax.plot([0.020,0.980],[0.645,0.645],color=AX,lw=1.0,**T)
for i,(k,label) in enumerate(ROWS):
    c=C[k]; y=0.430-i*0.290
    if i: ax.plot([0.020,0.980],[y+0.150,y+0.150],color=HAIR,lw=1.0,**T)
    st = CRIT if c["ci_contains_zero"] else SER
    ax.text(0.020,y,label,fontsize=11.5,color=INK,va="center",**T)
    ax.text(0.300,y,f"{c['truth']:.4f}",fontsize=11,color=INK2,va="center",ha="right",
            family="monospace",**T)
    ax.text(0.415,y,f"{c['estimate']:.4f}",fontsize=11,color=INK,va="center",ha="right",
            family="monospace",**T)
    ax.text(0.632,y,f"[{c['ci_lo']:+.4f}, {c['ci_hi']:+.4f}]",fontsize=11,color=INK,
            va="center",ha="right",family="monospace",**T)
    ax.plot([0.666],[y],"o",ms=7,color=st,markeredgecolor=S,markeredgewidth=1.4,**T)
    v=("interval includes zero" if c["ci_contains_zero"] else "resolved, but under-recovers")
    d=(f"planted signal sits {c['buried_x']:.0f}× under the adapters' own noise"
       if c["ci_contains_zero"] else
       f"interval excludes the planted value, {c['abs_err_in_mdc']:.1f} MDC low")
    ax.text(0.690,y+0.040,v,fontsize=10.5,color=INK,va="center",**T)
    ax.text(0.690,y-0.045,d,fontsize=8.3,color=MUT,va="center",**T)
fig.savefig("figures/B3_contrasts_plain.png",facecolor=S)
fig.savefig("figures/B3_contrasts_plain.pdf",facecolor=S)
print("wrote figures/B3_contrasts_plain.{png,pdf}")
