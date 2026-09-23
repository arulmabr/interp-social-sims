"""Post hoc discovery-only sparse geometry; no behavioral test or reselection."""
import argparse
import hashlib
from pathlib import Path

import torch
from huggingface_hub import hf_hub_download

from .core import sparse_match
from .preflight import SAE
from .smoke import SAE_REVISION, save_json


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True)
    args=p.parse_args();torch.set_num_threads(4)
    path=hf_hub_download(SAE,'Llama-3.3-70B-Instruct-SAE-l50.pt',revision=SAE_REVISION,local_files_only=True)
    state=torch.load(path,map_location='cpu',weights_only=True,mmap=True)
    decoder=state['decoder_linear.weight'].float()
    data=torch.load(args.run/'footprint.pt',map_location='cpu',weights_only=True)
    target=data['delta_h'].mean(0);result={}
    for k in (1,3,10,30):
        decoded,indices,coefficients,error=sparse_match(decoder,target,k)
        result[str(k)]={'indices':indices,'coefficients':coefficients.tolist(),'relative_error':error,
                        'decoded_norm':float(decoded.norm()),'decoded_cosine_with_target':float(decoded@target/(decoded.norm()*target.norm()))}
        print(f'Post hoc discovery OMP k={k}: relative error={error:.5f}',flush=True)
    save_json(args.run/'sparse_geometry_diagnostic.json',{
        'scope':'Post hoc geometric comparison using saved discovery residuals only. These vectors were not steered, did not enter checkpoint selection, and have no behavioral pass/fail result.',
        'methods':result,'sae_revision':SAE_REVISION,
        'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})


if __name__=='__main__':main()
