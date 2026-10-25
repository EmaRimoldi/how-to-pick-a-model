from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(frozen=True)
class HFGeneration:
    text: str
    tokens_generated: int
    wall_seconds: float


class TransformersGenerator:
    def __init__(self, model_id: str) -> None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        if not torch.cuda.is_available():
            raise RuntimeError("TransformersGenerator requires a CUDA GPU")
        self.torch = torch
        self.model_id = model_id
        self.tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id,
            dtype=torch.bfloat16,
            device_map="auto",
            low_cpu_mem_usage=True,
            trust_remote_code=True,
        )
        self.model.eval()
        warmup = self.tokenizer("def warmup():\n    return 1", return_tensors="pt").to(self.model.device)
        with torch.inference_mode():
            self.model.generate(
                **warmup,
                do_sample=False,
                max_new_tokens=1,
                pad_token_id=self.tokenizer.eos_token_id,
            )
        torch.cuda.synchronize()

    def generate(
        self,
        prompt: str,
        *,
        temperature: float,
        top_p: float,
        max_new_tokens: int,
        seed: int,
    ) -> HFGeneration:
        torch = self.torch
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        messages = [{"role": "user", "content": prompt}]
        rendered = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = self.tokenizer(rendered, return_tensors="pt").to(self.model.device)
        torch.cuda.synchronize()
        started = time.perf_counter()
        with torch.inference_mode():
            output = self.model.generate(
                **inputs,
                do_sample=temperature > 0,
                temperature=temperature,
                top_p=top_p,
                max_new_tokens=max_new_tokens,
                pad_token_id=self.tokenizer.eos_token_id,
            )
        torch.cuda.synchronize()
        elapsed = time.perf_counter() - started
        generated = output[0, inputs["input_ids"].shape[1] :]
        return HFGeneration(
            text=self.tokenizer.decode(generated, skip_special_tokens=True),
            tokens_generated=int(generated.numel()),
            wall_seconds=float(elapsed),
        )
