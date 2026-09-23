"""Create a source-backed visual brief; no model execution or result re-fitting."""
import csv
import hashlib
import json
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, Color, white
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

BASE = Path(__file__).resolve().parent
RUN = BASE / 'evidence/decision'
if not RUN.exists():
    RUN = BASE / 'outputs/decision-backup-20260918/outputs/decision-refined-20260918T235147Z'
OUT = BASE / 'coauthor_explainer'
OUT.mkdir(exist_ok=True)
PDF = OUT / 'output/pdf/sae_preference_experiment_explained.pdf'
PDF.parent.mkdir(parents=True, exist_ok=True)
A = json.loads((RUN / 'decision_analysis.json').read_text())
PLAN = json.loads((RUN / 'plan.json').read_text())
STATUS = json.loads((RUN / 'run_status.json').read_text())
assert STATUS['status'] == 'completed' and len(STATUS['conditions']) == 28
assert A['verdict'] == 'INCONCLUSIVE_EVALUATION_OR_ANCHOR_TRANSFER'
assert A['methods']['dense']['passed_cells'] == A['methods']['sae10']['passed_cells'] == 0

FONTDIR = Path('/System/Library/Fonts/Supplemental')
pdfmetrics.registerFont(TTFont('Arial', str(FONTDIR / 'Arial.ttf')))
pdfmetrics.registerFont(TTFont('Arial-Bold', str(FONTDIR / 'Arial Bold.ttf')))
pdfmetrics.registerFont(TTFont('Arial-Italic', str(FONTDIR / 'Arial Italic.ttf')))
pdfmetrics.registerFontFamily('Arial', normal='Arial', bold='Arial-Bold', italic='Arial-Italic', boldItalic='Arial-Bold')
W,H = 960,680
INK='#182E3B'; MUTED='#516574'; TEAL='#087F8C'; BLUE='#2B65B3'; ORANGE='#B86B22'; PURPLE='#7350A2'; RED='#A7453A'
BG='#F7F9FA'; LINE='#D5DFE4'; PALE='#EAF4F5'
c = canvas.Canvas(str(PDF), pagesize=(W,H))
c.setTitle('SAE steering: what we tested, what bias-like means, and what remains open')
c.setAuthor('Prepared with Codex from the saved research artifacts')
bounds=[]

def rect(x,y,w,h,fill,stroke=None,r=10):
    c.setFillColor(HexColor(fill));c.setStrokeColor(HexColor(stroke or fill))
    c.roundRect(x,H-y-h,w,h,r,fill=1,stroke=int(stroke is not None))

def txt(s,x,y,size=13,color=INK,bold=False):
    c.setFont('Arial-Bold' if bold else 'Arial',size);c.setFillColor(HexColor(color))
    c.drawString(x,H-y-size,s)

def para(s,x,y,w,size=14,color=INK,leading=None,maxh=None,bold=False):
    st=ParagraphStyle('body',fontName='Arial-Bold' if bold else 'Arial',fontSize=size,
                      leading=leading or size*1.35,textColor=HexColor(color),spaceAfter=0)
    p=Paragraph(s,st);pw,ph=p.wrap(w,1000)
    if maxh is not None:assert ph<=maxh+0.5,(c.getPageNumber(),s[:70],ph,maxh)
    assert y+ph<640,(c.getPageNumber(),s[:70],y+ph)
    p.drawOn(c,x,H-y-ph);bounds.append([c.getPageNumber(),x,y,w,ph]);return y+ph

def line(x1,y1,x2,y2,color=LINE,width=1):
    c.setStrokeColor(HexColor(color));c.setLineWidth(width);c.line(x1,H-y1,x2,H-y2)

def arrow(x1,y,x2,color=TEAL):
    line(x1,y,x2,y,color,1.8);line(x2-7,y-4,x2,y,color,1.8);line(x2-7,y+4,x2,y,color,1.8)

def label(s,x,y,color=TEAL):txt(s.upper(),x,y,10,color,True)

def header(n,title,sub):
    c.setFillColor(HexColor(BG));c.rect(0,0,W,H,fill=1,stroke=0)
    label('Research explanation  /  19 September 2026',42,22)
    txt(title,42,49,29,INK,True)
    para(sub,42,92,870,13,MUTED,maxh=38)
    line(42,644,918,644)
    txt('Prepared with Codex | Saved results checked against analysis code | Provisional research interpretation',42,653,9,MUTED)
    txt(f'{n} / 6',879,652,10,MUTED,True)

def card(x,y,w,h,tag,title,body,color=TEAL):
    rect(x,y,w,h,'#FFFFFF',LINE)
    label(tag,x+16,y+15,color)
    txt(title,x+16,y+37,18,color,True)
    para(body,x+16,y+64,w-32,12,leading=15.5,maxh=h-74)

def metric(name,template,target='combined'):
    return A['conditions'][name]['templates'][template]['targets'][target]['teacher_rmse']

def methodrange(method,template,target='combined'):
    vals=[metric(n,template,target) for n in A['methods'][method]['conditions'] if n.startswith(target+'_')]
    precision=4 if max(vals)-min(vals)<.001 else 3
    return f'{min(vals):.{precision}f}-{max(vals):.{precision}f}'

# PAGE 1: Standalone visual summary; exported as a shareable PNG as well.
header(1,'Changing choices is not yet a validated preference change',
       'Question: can Sparse Autoencoder (SAE) steering produce a stable risk-choice policy across rewards, wording and answer labels?')
card(42,143,276,184,'Action anchor','Raw logit gradient',
     'A residual-space direction built from sensitivity of risky-versus-safe answer scores, averaged over discovery prompts. No SAE is used.<br/><br/><b>Observed:</b> passed the action-control check at tested valid doses.',BLUE)
card(342,143,276,184,'Intended preference anchor','Low-Rank Adaptation',
     'LoRA is a trained weight-space adapter. We reused one trained to imitate a known Cumulative Prospect Theory (CPT) policy.<br/><br/><b>Observed:</b> passed original-wording checks; failed rewording.',PURPLE)
card(642,143,276,184,'Methods evaluated','Dense and SAE steering',
     'A free residual direction versus a combination of ten SAE decoder features. Both aim at the same target policy, with matched edit size and positions.<br/><br/><b>Observed:</b> neither method passed.',ORANGE)
label('Held-out results for the combined CPT target',42,350)
txt('Error relative to the intended policy',42,374,19,INK,True)
txt('Original wording',430,378,12,MUTED,True);txt('New wording',628,378,12,MUTED,True)
rows=[('LoRA reference',f'{metric("lora","original"):.3f}',f'{metric("lora","transfer"):.3f}',PURPLE),
      ('Dense steering',methodrange('dense','original'),methodrange('dense','transfer'),BLUE),
      ('Ten-feature SAE steering',methodrange('sae10','original'),methodrange('sae10','transfer'),ORANGE)]
for i,(name,v1,v2,col) in enumerate(rows):
    y=408+i*34;line(42,y-5,918,y-5);txt(name,52,y,14,col,True);txt(v1,450,y,16,INK,True);txt(v2,652,y,16,INK,True)
para('Root Mean Squared Error (RMSE) of choice probabilities; lower is better. Declared accuracy limit: 0.060. Steering ranges show two training seeds, not confidence intervals.',42,516,873,12,MUTED,maxh=36)
rect(42,563,876,64,PALE)
para('<b>Decision: defer the full feature sweep.</b> The tested recipe failed. A robust positive anchor and a passing dense control are still missing, so this does not establish a general limitation of the SAE dictionary.',58,576,841,14,maxh=43)
c.showPage()

# PAGE 2: Plain-language theory and the model-specific operational definition.
header(2,'CPT gives us a known choice policy to aim for',
       'CPT = Cumulative Prospect Theory. Here it is a mathematical behavioral benchmark, not a claim that a language model has human feelings.')
rect(42,143,876,66,'#FFFFFF',LINE)
para('<b>Illustrative question:</b> choose a guaranteed gain of 40 tokens, or a 50% chance of gaining 100 tokens and a 50% chance of gaining nothing. One answer cannot identify a preference; we vary outcomes and probabilities to measure a pattern.',58,158,843,14,maxh=44)
card(42,230,276,163,'1  /  Curvature: alpha','Sensitivity to amounts',
     'How does subjective value change as gains or losses grow? Our combined target uses <b>alpha = 0.8</b>, giving diminishing sensitivity in magnitude. The same exponent is used for gains and losses.',BLUE)
card(342,230,276,163,'2  /  Weighting: gamma','Treatment of probabilities',
     'Outcome probabilities are converted into decision weights using cumulative probabilities. Our combined target uses <b>gamma = 0.72</b>; gamma = 1 would leave probabilities undistorted.',TEAL)
card(642,230,276,163,'3  /  Loss aversion: lambda','Relative weight of losses',
     'How strongly does a loss count relative to an equal-sized gain? Our combined target uses <b>lambda = 2</b>: the value magnitude of a loss is twice that of the corresponding gain.',PURPLE)
para('<b>Two additional fitted quantities:</b> choice sensitivity (inverse temperature, beta) controls how sharply value differences affect answer probabilities; an A-label bias captures a tendency to select the option displayed as A. Our CPT fit therefore has <b>five parameters</b>, not only three.',42,417,876,14,maxh=62)
rect(42,505,876,63,PALE)
para('<b>Two steering targets:</b> combined = (alpha 0.8, gamma 0.72, lambda 2); neutral = (1, 1, 1). Both use beta = 3 and zero A-label bias. The neutral target is linear and probability-unweighted, but choices remain probabilistic.',58,518,842,13,maxh=43)
para('Implementation: outcomes are changes from a zero reference, scaled by 100 tokens. Gain/loss curvature and probability weighting are shared in this restricted CPT family. It does not cover every preference model. The example above is illustrative, not a measured test row.',42,585,876,11,MUTED,maxh=35)
c.showPage()

# PAGE 3: Actual workflow, fair comparison and implementation definitions.
header(3,'Learn on development prompts; judge on untouched prompts',
       'LLM = Large Language Model. We used the same Llama-3.3-70B-Instruct checkpoint in bfloat16 (bf16), a 16-bit numerical format.')
card(42,144,259,107,'Discovery','216 prompts','Screen 37 candidate SAE features and train steering directions.',TEAL)
arrow(309,195,335)
card(343,144,259,107,'Selection','96 prompts','Choose checkpoints and one shared dose / token scope per target.',BLUE)
arrow(610,195,636)
card(644,144,274,107,'Frozen evaluation','432 prompts per condition','108 scenarios x 2 answer orders x 2 wordings. No tuning on these answers.',PURPLE)
label('What was matched between dense and SAE steering',42,274)
rect(42,296,876,159,'#FFFFFF',LINE)
txt('Base hidden state h',62,320,17,INK,True);arrow(263,334,310)
txt('Add a fixed vector v',330,320,17,TEAL,True);arrow(541,334,588)
txt('Read risky / safe answer probabilities',608,321,14,INK,True)
para('<b>Dense:</b> v is freely optimized in the residual space.<br/><b>SAE:</b> v is a weighted sum of ten decoder feature directions. SAE = Sparse Autoencoder: an existing learned feature dictionary for internal model activity.',62,363,815,13,maxh=59)
para('Both selected edits use block-output 50, all nonpadding prompt positions and residual norm 16 per position. Edits are additive; we do not replace the state with a full SAE reconstruction.',62,418,815,11,MUTED,maxh=32)
para('<b>What matching does and does not mean:</b> the two methods receive the same-sized residual displacement at the same locations. That does not guarantee equal behavioral strength or optimization difficulty. The weight-space LoRA cannot be norm-matched this way.',42,477,876,13,maxh=55)
para('<b>Other controls:</b> the unmodified model, reused LoRA, raw positive/negative readout gradients, sparse SAE readout approximation, random directions, and 48 elementary arithmetic/probability/dominance items. There were 28 final conditions in total.',42,543,876,13,maxh=54)
para('Seeds are independent optimization initializations, not independent base models. Feature screening ranked full-grid choice loss, not direct switching-point / curvature effects. No new SAE or LoRA was trained in this latest round.',42,606,876,10.5,MUTED,maxh=30)
c.showPage()

# PAGE 4: Two separate questions, with actual model-comparison plot.
header(4,'Why we used the phrase "bias-like"',
       'This is a held-out predictive comparison between two explanations of the observed SAE-steered choices. It is not a semantic label for an SAE feature.')
card(42,143,425,133,'Explanation A  /  5 fitted parameters','Restricted CPT model',
     'Predict choices from rewards and probabilities using curvature, weighting, loss aversion, choice sensitivity and A-label bias.',PURPLE)
card(491,143,427,133,'Explanation B  /  7 fitted parameters','Answer-bias / confidence model',
     'Transform the base model\'s risky/safe log-odds with a separate shift and positive scale for each of three frames, plus an A-label bias.',TEAL)
para('<b>Both explanations were fitted on selection responses and then frozen.</b> The chart compares their error when predicting the actual SAE-steered probabilities on unseen scenarios and wording.',42,290,876,13,maxh=38)
label('Held-out explanatory RMSE  /  Lower is better',42,340)
txt('Bias / confidence model',662,341,11,TEAL,True);txt('CPT model',814,341,11,PURPLE,True)
chart_x,chart_w=329,551; top=376; xmax=.18
for tick in [0,.05,.10,.15]:
    x=chart_x+chart_w*tick/xmax;line(x,370,x,555,'#E1E7EB');txt(f'{tick:.2f}',x-10,559,10,MUTED)
chartrows=[]
for target in ['combined','neutral']:
    for seed in [31,73]:
        name=f'{target}_sae10_all_seed{seed}_rho16'
        for template in ['original','transfer']:
            b=A['conditions'][name]['templates'][template]['comparison'];chartrows.append((target,seed,template,b))
for i,(target,seed,template,b) in enumerate(chartrows):
    y=top+i*23
    txt(f'{target.capitalize()} / seed {seed} / '+('original' if template=='original' else 'new wording'),48,y-4,11,INK)
    vals=[b['heldout_shortcut_rmse'],b['heldout_cpt_rmse']]
    xs=[chart_x+chart_w*v/xmax for v in vals];line(xs[0],y+3,xs[1],y+3,'#B7C7CE',2)
    for x,col in zip(xs,[TEAL,PURPLE]):c.setFillColor(HexColor(col));c.circle(x,H-y-3,4,fill=1,stroke=0)
    txt(f'{vals[0]:.3f}',xs[0]-14,y-12,8,TEAL);txt(f'{vals[1]:.3f}',xs[1]-14,y-12,8,PURPLE)
rect(42,593,876,42,'#FFF2E7')
para('<b>Interpret carefully:</b> the bias model has more parameters and access to base-model responses. Better held-out prediction supports this descriptive explanation; it does not prove an internal mechanism or exclude every preference model.',55,601,850,11,maxh=30)
c.showPage()

# PAGE 5: Verdict with definitions of outcomes and evidence limits.
header(5,'The current recipe failed; the general SAE question stays open',
       'Keep target recovery, behavioral model comparison, and feature meaning as three separate claims.')
label('Question 1  /  Did the interventions recover the planted policy?',42,142)
table_y=166; widths=[126,236,223,291]; xs=[42,168,404,627]
heads=['Target','Intervention','Original wording','New wording']
for x,w,s in zip(xs,widths,heads):rect(x,table_y,w-2,29,INK,r=0);txt(s,x+9,table_y+7,11,'#FFFFFF',True)
tab=[]
for target in ['combined','neutral']:
    if target=='combined':tab.append((target,'LoRA',f'{metric("lora","original"):.4f}',f'{metric("lora","transfer"):.4f}'))
    for method,name in [('dense','Dense vector'),('sae10','Ten SAE features')]:tab.append((target,name,methodrange(method,'original',target),methodrange(method,'transfer',target)))
for i,row in enumerate(tab):
    y=table_y+30+i*28
    for x,w,s in zip(xs,widths,row):rect(x,y,w-2,27,'#FFFFFF',r=0);txt(s,x+9,y+6,12,INK,i==0)
para('RMSE against the planted teacher; target <= 0.060. Ranges span two seeds, not uncertainty intervals. These are different errors from page 4, whose target was the actual steered behavior.',42,343,876,11,MUTED,maxh=34)
card(42,391,276,132,'Action reference','Raw gradient: pass',
     'The valid-dose raw gradient met the operational action-control criterion. That validates one useful negative control.',BLUE)
card(342,391,276,132,'Preference reference','LoRA: partial success',
     'Passed the latest provisional criteria in original wording. Rewording failed recovery, prediction and answer-order checks.',PURPLE)
card(642,391,276,132,'Steering outcome','Dense 0/8; SAE 0/8',
     'Eight combinations = 2 targets x 2 seeds x 2 wordings. None passed the complete rule; this is not eight separate tests.',ORANGE)
para('<b>Beyond exact target recovery:</b> a separate preference-like check removed the planted-parameter and teacher-accuracy requirements. Both methods still passed 0/8. Yet failure of a finite candidate set and optimizer budget is not evidence that every SAE intervention must fail.',42,543,876,13,maxh=54)
para('The earlier stricter repair rule used teacher RMSE <= 0.040; the reused LoRA misses it on this new grid in both wordings. "Pass" above refers only to the latest provisional rule. These thresholds do not replace the collaborator\'s full go/pivot protocol.',42,609,876,10.5,MUTED,maxh=29)
c.showPage()

# PAGE 6: Probe distinction, geometry, next test, and traceability.
header(6,'What to align with coauthors before another GPU run',
       'The freely trained dense vector is a new diagnostic control. The original probe is also a dense residual direction, learned in a different way.')
labels=['','Current dense control','Original Llama probe code']
tx=[42,231,575];tw=[185,340,343]
for x,w,s in zip(tx,tw,labels):rect(x,145,w,27,INK,r=0);txt(s,x+10,151,12,'#FFFFFF',True)
comp=[('How learned','Optimize CPT choice-probability loss','Train a linear classifier on activations'),
      ('Where applied','Block-output 50; selected all prompt tokens','Layer 48; final 20% with a position ramp'),
      ('Comparison status','Evaluated in this pilot','Not rerun under these matched conditions')]
for i,row in enumerate(comp):
    y=173+i*33
    for x,w,s in zip(tx,tw,row):rect(x,y,w,32,'#FFFFFF',r=0);para(s,x+10,y+8,w-20,11,maxh=26,bold=x==42)
para('We cannot infer how the original probe would perform from this dense control\'s failure. A fair head-to-head needs aligned prompts, layer, token scope, dose, training objective and held-out criteria.',42,280,876,12,MUTED,maxh=34)
card(42,332,425,123,'Interpretability status','Existing dictionary; our analyses',
     'We used Goodfire\'s released layer-50 SAE. Descriptions are cached Neuronpedia labels, not independently validated meanings. Activations and steering effects are our measurements.',TEAL)
card(491,332,427,123,'Sparse readout diagnostic','Large residual is scope-limited',
     'The ten-feature readout approximation left relative residual norm 0.961. This diagnoses that sparse fit; it does not show that the full dictionary cannot express the gradient.',ORANGE)
rect(42,474,876,64,PALE)
para('<b>Next gate:</b> validate a LoRA across new phrasings, label orders and reward grids. If it passes, repeat the small matched dense / SAE comparison. If dense succeeds and SAE fails, the sparse recipe is implicated more specifically. If both fail, change the intervention format before a full sweep.',57,487,846,12.5,maxh=46)
para('<b>Definitions and sources:</b> CPT: Tversky &amp; Kahneman (1992), <link href="https://doi.org/10.1007/BF00122574" color="#087F8C">doi:10.1007/BF00122574</link>. LoRA: Hu et al. (2021), <link href="https://arxiv.org/abs/2106.09685" color="#087F8C">arXiv:2106.09685</link>. SAE: <link href="https://huggingface.co/Goodfire/Llama-3.3-70B-Instruct-SAE-l50" color="#087F8C">Goodfire layer-50 model card</link>. Result source: decision-refined-20260918T235147Z, decision_analysis.json. Local source index, full methods and figure data accompany this brief.',42,559,876,10.5,MUTED,maxh=47)
para('Prepared with Codex using saved results checked against the analysis code. This brief adds no experimental data; its figures are drawn from the saved analysis. The previous GPU session was stopped and its artifacts verified.',42,611,876,10,MUTED,maxh=27)
c.showPage();c.save()

# Exact plotted values and a portable provenance manifest.
with (OUT/'figure_data.csv').open('w',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=['target','seed','wording','bias_model_rmse','cpt_model_rmse'])
    writer.writeheader()
    for target,seed,template,b in chartrows:
        writer.writerow(dict(target=target,seed=seed,wording=template,bias_model_rmse=b['heldout_shortcut_rmse'],cpt_model_rmse=b['heldout_cpt_rmse']))
manifest={'purpose':'Explain existing results to coauthors; no new inference or training.',
          'source_run':str(RUN),'source_sha256':{},'page_count':6,'outputs':[str(PDF)],
          'public_references':['https://doi.org/10.1007/BF00122574','https://arxiv.org/abs/2106.09685','https://huggingface.co/Goodfire/Llama-3.3-70B-Instruct-SAE-l50'],
          'limitations':['The full external go/pivot rule was not supplied.','Current tests use a restricted CPT family, one base model/SAE, one saved LoRA seed and a bounded 37-feature candidate screen.','Bias model has seven parameters and baseline predictions; CPT fit has five. Predictive advantage is not mechanism identification.']}
for p in [RUN/'decision_analysis.json',RUN/'plan.json',RUN/'selection_lock.json',BASE/'cpt.py',BASE/'decision_analysis.py',BASE/'decision_report.py',BASE/'DECISION_RESULTS.md',BASE.parent/'Probes/probes.py',BASE.parent/'Probes/models.py',BASE.parent/'Probes/config.py']:
    manifest['source_sha256'][str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
(OUT/'provenance.json').write_text(json.dumps(manifest,indent=2)+'\n')
(OUT/'text_bounds.json').write_text(json.dumps(bounds)+'\n')
print(PDF)
