#!/usr/bin/env python
"""Minimal OpenAI-compatible Qwen server for smoke tests.

This is intentionally small: it implements only the endpoints needed by the
VAO OpenAI-compatible adapter (`/v1/models` and `/v1/chat/completions`) using
`transformers` generation. It is not intended to replace vLLM/SGLang for
production throughput.
"""

from __future__ import annotations

import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


MODEL: Any = None
TOKENIZER: Any = None
MODEL_ID = ""
if torch.cuda.is_available():
    DEVICE = "cuda"
elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
    DEVICE = "mps"
else:
    DEVICE = "cpu"


class QwenOpenAIHandler(BaseHTTPRequestHandler):
    server_version = "vao-qwen-openai-compat/0.1"

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        if self.path.rstrip("/") == "/v1/models":
            self._write_json(
                {
                    "object": "list",
                    "data": [
                        {
                            "id": MODEL_ID,
                            "object": "model",
                            "created": 0,
                            "owned_by": "local",
                        }
                    ],
                }
            )
            return
        self.send_error(404, "not found")

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        if self.path.rstrip("/") != "/v1/chat/completions":
            self.send_error(404, "not found")
            return
        try:
            request = self._read_json()
            response = complete_chat(request)
        except Exception as exc:  # noqa: BLE001 - return debuggable server error.
            self._write_json({"error": {"message": f"{type(exc).__name__}: {exc}"}}, status=500)
            return
        self._write_json(response)

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[{self.log_date_time_string()}] {self.address_string()} {fmt % args}", flush=True)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("content-length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        return payload

    def _write_json(self, payload: dict[str, Any], *, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def complete_chat(request: dict[str, Any]) -> dict[str, Any]:
    messages = request.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ValueError("messages must be a non-empty list")
    max_new_tokens = int(request.get("max_tokens") or 2048)
    temperature = float(request.get("temperature") or 0.0)
    prompt = TOKENIZER.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    encoded = TOKENIZER(prompt, return_tensors="pt")
    encoded = {key: value.to(MODEL.device) for key, value in encoded.items()}
    input_tokens = int(encoded["input_ids"].shape[-1])
    with torch.inference_mode():
        output_ids = MODEL.generate(
            **encoded,
            max_new_tokens=max_new_tokens,
            do_sample=temperature > 0,
            temperature=max(temperature, 1e-5),
            top_p=0.95,
            pad_token_id=TOKENIZER.eos_token_id,
        )
    generated = output_ids[0, input_tokens:]
    text = TOKENIZER.decode(generated, skip_special_tokens=True).strip()
    output_tokens = int(generated.shape[-1])
    return {
        "id": f"chatcmpl-local-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": MODEL_ID,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": input_tokens,
            "completion_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="Qwen/Qwen2.5-Coder-1.5B-Instruct")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--dtype", default="bfloat16", choices=["auto", "float16", "bfloat16", "float32"])
    args = parser.parse_args()

    global MODEL, TOKENIZER, MODEL_ID
    MODEL_ID = args.model
    dtype = {
        "auto": "auto",
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
        "float32": torch.float32,
    }[args.dtype]
    print(f"Loading {MODEL_ID} on {DEVICE} with dtype={args.dtype}", flush=True)
    TOKENIZER = AutoTokenizer.from_pretrained(MODEL_ID)
    MODEL = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        torch_dtype=dtype,
        device_map="auto" if DEVICE == "cuda" else None,
    )
    if DEVICE != "cuda":
        MODEL = MODEL.to(DEVICE)
    MODEL.eval()
    server = ThreadingHTTPServer((args.host, args.port), QwenOpenAIHandler)
    print(f"Serving {MODEL_ID} at http://{args.host}:{args.port}/v1", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
