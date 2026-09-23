"""Read-only model access check; downloads tiny config, never prints tokens."""
import argparse
import json
import sys
from huggingface_hub import HfApi, get_hf_file_metadata, hf_hub_download, hf_hub_url
from .auth import resolve_token

MODEL = "meta-llama/Llama-3.3-70B-Instruct"
SAE = "Goodfire/Llama-3.3-70B-Instruct-SAE-l50"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hf-token-name", help="Saved local token name, never the token value")
    args = parser.parse_args()
    try:
        token = resolve_token(args.hf_token_name)
        api = HfApi(token=token)
        model_revision = api.model_info(MODEL).sha
        config = hf_hub_download(MODEL, "config.json", token=token, revision=model_revision)
        with open(config) as handle:
            model_config = json.load(handle)
        index = hf_hub_download(MODEL, "model.safetensors.index.json", token=token, revision=model_revision)
        with open(index) as handle:
            shard = next(iter(json.load(handle)["weight_map"].values()))
        get_hf_file_metadata(hf_hub_url(MODEL, shard, revision=model_revision), token=token)
        sae_info = api.model_info(SAE)
        files = [x.rfilename for x in sae_info.siblings]
        get_hf_file_metadata(hf_hub_url(SAE, "Llama-3.3-70B-Instruct-SAE-l50.pt", revision=sae_info.sha), token=token)
        print(json.dumps({"model_access": True, "weight_download_access": True,
                          "model_revision": model_revision,
                          "sae_revision": sae_info.sha, "sae_files": files,
                          "layers": model_config["num_hidden_layers"],
                          "hidden_size": model_config["hidden_size"]}, indent=2))
    except Exception as error:
        response = getattr(error, "response", None)
        print(json.dumps({"model_access": False, "error_type": type(error).__name__,
                          "http_status": getattr(response, "status_code", None),
                          "next_step": "Use an existing HF login approved for the model; do not paste tokens into chat."}))
        sys.exit(1)


if __name__ == "__main__":
    main()
