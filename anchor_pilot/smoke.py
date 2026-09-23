"""Bounded bf16 70B engineering smoke, with a download-free CPU fixture mode.

This does not train a LoRA, fit CPT, select confirmatory features, or implement
the scientific go/pivot rule. All prompts and results are development-only.
"""
import argparse
import hashlib
import importlib.metadata
import json
import platform
import time
from pathlib import Path

import torch
from huggingface_hub import HfApi, hf_hub_download
from transformers import AutoModelForCausalLM, AutoTokenizer, LlamaConfig, LlamaForCausalLM

from .core import readout, readout_gradient, residual_patch, sparse_match, unit
from .auth import resolve_token
from .preflight import MODEL, SAE
from .prompts import smoke_prompts

SAE_REVISION = "128ee921ecd1b8b3a87d776cbcc357c0855da134"
FEATURES = [184, 4237, 31935, 13142, 20117, 4992]


def save_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def load_stack(fixture, token_name=None):
    if fixture:
        config = LlamaConfig(vocab_size=32, hidden_size=24, intermediate_size=48,
                             num_hidden_layers=3, num_attention_heads=4, num_key_value_heads=2)
        model = LlamaForCausalLM(config).eval().requires_grad_(False)
        dictionary = torch.randn(24, 48)
        return model, None, dictionary, [0, 1], [1, 3, 5, 7, 9, 11], {
            "mode": "CPU_random_fixture", "model": "random_tiny_llama",
            "scientific_evidence": False,
        }
    if not torch.cuda.is_available():
        raise RuntimeError("Real-model mode needs CUDA. Use --fixture only for local software checks.")
    if not torch.cuda.is_bf16_supported():
        raise RuntimeError("This GPU stack does not support bf16")
    # Check access before downloading model weights. Pin the resolved revision.
    token = resolve_token(token_name)
    api = HfApi(token=token)
    revision = api.model_info(MODEL).sha
    hf_hub_download(MODEL, "config.json", revision=revision, token=token)
    tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=revision, token=token)
    memory_limits = {
        i: f"{int(torch.cuda.get_device_properties(i).total_memory / 2**30) - 12}GiB"
        for i in range(torch.cuda.device_count())
    }
    model = AutoModelForCausalLM.from_pretrained(
        MODEL, revision=revision, token=token, torch_dtype=torch.bfloat16,
        device_map="balanced", max_memory=memory_limits, attn_implementation="sdpa",
        trust_remote_code=False,
    ).eval().requires_grad_(False)
    if any(str(device) in {"cpu", "disk"} for device in model.hf_device_map.values()):
        raise RuntimeError("Model offloaded to CPU/disk; this is not the requested all-GPU bf16 smoke")
    if {parameter.dtype for parameter in model.parameters()} != {torch.bfloat16}:
        raise RuntimeError("Base model parameters are not uniformly bf16")
    checkpoint = hf_hub_download(SAE, "Llama-3.3-70B-Instruct-SAE-l50.pt", revision=SAE_REVISION, token=token)
    state = torch.load(checkpoint, map_location="cpu", weights_only=True)
    dictionary = state["decoder_linear.weight"].detach().float().contiguous()
    if dictionary.shape[0] != model.config.hidden_size or dictionary.shape[1] <= max(FEATURES):
        raise RuntimeError("Unexpected decoder dimensions or missing requested feature indices")
    return model, tokenizer, dictionary, [48, 50], FEATURES, {
        "mode": "bf16_real_model", "model": MODEL, "model_revision": revision,
        "sae": SAE, "sae_revision": SAE_REVISION, "decoder_shape": list(dictionary.shape),
        "device_map": {name: str(device) for name, device in model.hf_device_map.items()},
        "scientific_evidence": False,
    }


def prepare_inputs(model, tokenizer, rows):
    prepared = []
    for index, row in enumerate(rows):
        if tokenizer is None:
            inputs = {"input_ids": torch.tensor([[1, 5 + index, 7, 3]])}
            ids = {"A": 4, "B": 8}
        else:
            messages = [{"role": "user", "content": row["text"]}]
            rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = tokenizer(rendered, return_tensors="pt", add_special_tokens=False)
            inputs = {key: value.to(model.get_input_embeddings().weight.device) for key, value in inputs.items()}
            ids = {}
            for label in ("A", "B"):
                encoded = tokenizer.encode(label, add_special_tokens=False)
                full = tokenizer.encode(rendered + label, add_special_tokens=False)
                prefix = inputs["input_ids"][0].tolist()
                if len(encoded) != 1 or full != prefix + encoded:
                    raise RuntimeError(f"Label {label} is not a single continuation token; revise readout")
                ids[label] = encoded[0]
        prepared.append((inputs, ids[row["risky_label"]], ids[row["safe_label"]]))
    return prepared


def gpu_memory():
    return [{"device": i, "name": torch.cuda.get_device_name(i),
             "peak_allocated_gib": torch.cuda.max_memory_allocated(i) / 2**30,
             "peak_reserved_gib": torch.cuda.max_memory_reserved(i) / 2**30}
            for i in range(torch.cuda.device_count())]


def run(args):
    torch.manual_seed(17)
    torch.set_num_threads(min(8, torch.get_num_threads()))
    if args.rho <= 0:
        raise ValueError("rho must be positive")
    args.output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    report = {"status": "started", "scope": "provisional_engineering_smoke",
              "go_pivot_thresholds": None, "scientific_pass": None,
              "rho": args.rho, "seed": 17, "token_scope": "last_prompt_token",
              "layer_indexing": "zero_based_block_output", "python": platform.python_version(),
              "versions": {name: importlib.metadata.version(name)
                           for name in ("torch", "transformers", "accelerate", "huggingface-hub")}}
    save_json(args.output / "report.json", report)
    try:
        print("Loading model and decoder", flush=True)
        model, tokenizer, decoder, layers, features, metadata = load_stack(args.fixture, args.hf_token_name)
        report.update(metadata)
        rows = smoke_prompts()
        prepared = prepare_inputs(model, tokenizer, rows)
        save_json(args.output / "prompts.json", rows)
        report["prompt_sha256"] = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
        report["answer_token_ids"] = [
            {"prompt_id": row["id"], "risky": risky, "safe": safe}
            for row, (_, risky, safe) in zip(rows, prepared)
        ]
        baselines = [readout(model, inputs, risky, safe) for inputs, risky, safe in prepared]
        report["baselines"] = baselines
        report["layers"] = {}
        directions = {}
        for layer in layers:
            print(f"Computing gradients at layer {layer}", flush=True)
            samples = [readout_gradient(model, inputs, layer, risky, safe) for inputs, risky, safe in prepared]
            gradients = torch.stack([sample[0] for sample in samples])
            mean_gradient = gradients.mean(0)
            direction = unit(mean_gradient)
            directions[str(layer)] = direction
            stats = {"per_prompt_gradient_norms": gradients.norm(dim=-1).tolist(),
                     "mean_gradient_norm": float(mean_gradient.norm()),
                     "mean_alignment_per_prompt": [float(unit(g) @ direction) for g in gradients],
                     "baseline_residual_norms": [sample[2] for sample in samples]}
            inputs, risky, safe = prepared[0]
            with residual_patch(model, layer, torch.zeros_like(direction)):
                zero_readout = readout(model, inputs, risky, safe)
            stats["zero_dose_exact_identity"] = zero_readout == baselines[0]
            if not stats["zero_dose_exact_identity"]:
                raise RuntimeError("Zero-dose readout changed")
            # Validate the per-prompt gradient, not the averaged direction.
            local_direction = unit(gradients[0])
            expected = float(gradients[0] @ local_direction)
            stats["finite_difference"] = []
            epsilon_grid = args.fd_eps or ([0.0001, 0.0003] if args.fixture else [0.025, 0.05, 0.1, 0.25, 0.5, 1.0])
            if any(epsilon <= 0 for epsilon in epsilon_grid):
                raise ValueError("Finite-difference steps must be positive")
            for epsilon in epsilon_grid:
                margins = []
                for sign in (-1, 1):
                    with residual_patch(model, layer, sign * epsilon * local_direction):
                        margins.append(readout(model, inputs, risky, safe)["margin"])
                observed = (margins[1] - margins[0]) / (2 * epsilon)
                stats["finite_difference"].append({"epsilon": epsilon, "autograd": expected,
                                                   "numerical": observed,
                                                   "relative_error": abs(observed - expected) / max(abs(expected), 1e-12)})
            report["layers"][str(layer)] = stats
            save_json(args.output / "report.json", report)
        sae_layer = layers[-1]
        direction = directions[str(sae_layer)]
        cosines = (decoder.T @ direction) / decoder.norm(dim=0).clamp_min(1e-12)
        best_index = int(cosines.argmax())
        reconstructed, indices, coefficients, error = sparse_match(decoder, direction, args.sparse_k)
        report["sae_readout_reconstruction"] = {
            "k": args.sparse_k, "feature_indices": indices, "coefficients": coefficients.tolist(),
            "relative_error_before_renormalization": error,
            "decoded_norm_before_renormalization": float(reconstructed.norm()),
            "signed_coefficients_allowed": True, "highest_positive_cosine_feature": best_index,
            "highest_positive_cosine": float(cosines[best_index]),
        }
        report["feature_alignment"] = [{"feature": feature, "cosine": float(cosines[feature]),
                                        "decoder_norm": float(decoder[:, feature].norm()),
                                        "alpha_for_positive_rho": args.rho / float(decoder[:, feature].norm())}
                                       for feature in features]
        interventions = []
        for layer in layers:
            interventions.extend([(layer, "readout_gradient", directions[str(layer)]),
                                  (layer, "random_seed17", unit(torch.randn_like(direction)))])
        interventions.extend((sae_layer, f"feature_{feature}", unit(decoder[:, feature])) for feature in features)
        interventions.extend([
            (sae_layer, "creativity_triple_equal_latent_weights", unit(decoder[:, features[-3:]].sum(1))),
            (sae_layer, "sae_native_readout_signed_omp", unit(reconstructed)),
        ])
        records = []
        for layer, name, vector in interventions:
            print(f"Checking {name} at layer {layer}", flush=True)
            for index, (row, (inputs, risky, safe)) in enumerate(zip(rows, prepared)):
                trace = []
                with residual_patch(model, layer, args.rho * vector, trace):
                    result = readout(model, inputs, risky, safe)
                records.append({"prompt_id": row["id"], "frame": row["frame"], "layer": layer,
                                "intervention": name, **result, **trace[0],
                                "margin_change": result["margin"] - baselines[index]["margin"]})
            save_json(args.output / "interventions.json", records)
        torch.save({"unit_gradients": directions, "omp_indices": indices,
                    "omp_coefficients": coefficients}, args.output / "directions.pt")
        report["status"] = "completed_requires_diagnostic_review"
        report["engineering_execution_completed"] = True
        report["intervention_rows"] = len(records)
    except Exception as error:
        report["status"] = "failed"
        report["error_type"] = type(error).__name__
        # No raw exception text: HTTP errors can contain credential-bearing URLs.
        raise
    finally:
        report["elapsed_seconds"] = time.monotonic() - started
        report["gpu_memory"] = gpu_memory()
        save_json(args.output / "report.json", report)
    print(json.dumps({"status": report["status"], "output": str(args.output),
                      "elapsed_seconds": report["elapsed_seconds"]}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", action="store_true", help="Random tiny CPU model; no scientific evidence")
    parser.add_argument("--hf-token-name", help="Saved local token name, never the token value")
    parser.add_argument("--output", type=Path, required=True, help="New output directory; refuses to overwrite")
    parser.add_argument("--rho", type=float, default=1.0, help="Provisional per-position residual norm")
    parser.add_argument("--sparse-k", type=int, default=3)
    parser.add_argument("--fd-eps", type=float, nargs="+", help="Optional positive finite-difference step sizes")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
