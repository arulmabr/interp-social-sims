"""CPU-only nominated-feature footprints from saved discovery residuals.

Uses the pinned SAE already cached on the pod. No model queries, intervention
selection, training, or frozen responses are involved.
"""
import argparse
import hashlib
from pathlib import Path

import torch
from huggingface_hub import hf_hub_download

from .preflight import SAE
from .smoke import SAE_REVISION, save_json
from .targeted_footprints import TARGETS


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True)
    args=p.parse_args();torch.set_num_threads(2)
    filename=hf_hub_download(SAE,'Llama-3.3-70B-Instruct-SAE-l50.pt',revision=SAE_REVISION,local_files_only=True)
    state=torch.load(filename,map_location='cpu',weights_only=True,mmap=True)
    atoms=state['decoder_linear.weight'][:,TARGETS].float()
    weights=state['encoder_linear.weight'][TARGETS].float();bias=state['encoder_linear.bias'][TARGETS].float()
    data=torch.load(args.run/'footprint.pt',map_location='cpu',weights_only=True)
    directions=torch.load(args.run/'directions.pt',map_location='cpu',weights_only=True)
    base,delta=data['base'],data['delta_h'];norms=atoms.norm(dim=0)
    projection=delta@atoms/norms
    before=torch.relu(base@weights.T+bias);after=torch.relu((base+delta)@weights.T+bias);change=after-before
    gradient=directions['gradient_l50_sign+1']['vector']
    cosine=gradient@atoms/norms
    entries=[{'feature':index,'cosine_readout':float(cosine[j]),
              'mean_unit_decoder_projection':float(projection[:,j].mean()),
              'mean_absolute_unit_decoder_projection':float(projection[:,j].abs().mean()),
              'single_column_coefficient_for_mean_delta':float(projection[:,j].mean()/norms[j]),
              'mean_encoder_before':float(before[:,j].mean()),'mean_encoder_after':float(after[:,j].mean()),
              'mean_encoder_change':float(change[:,j].mean()),
              'mean_absolute_encoder_change':float(change[:,j].abs().mean())}
             for j,index in enumerate(TARGETS)]
    save_json(args.run/'targeted_footprints.json',{
        'scope':'Descriptive fixed-feature analysis of discovery prompts; not intervention selection.',
        'historical_identity_caveat':'Feature 47380 matches the locally cached option-selection label; identity with the historical paper figure is not independently established.',
        'sae_revision':SAE_REVISION,'prompt_ids':data['prompt_ids'],'features':entries,
        'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'input_footprint_sha256':hashlib.sha256((args.run/'footprint.pt').read_bytes()).hexdigest()})
    print('Saved seven nominated discovery-feature footprints; no model responses queried.')


if __name__=='__main__':main()
