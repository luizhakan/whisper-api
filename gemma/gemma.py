from transformers import AutoProcessor, Gemma3ForConditionalGeneration
import requests
import torch

model_id = "google/gemma-3-4b-pt"
url = "https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/bee.jpg"
model = Gemma3ForConditionalGeneration.from_pretrained(model_id).eval()
processor = AutoProcessor.from_pretrained(model_id)

prompt = "Me diga quanto é 2 + 2"
model_inputs = processor(text=prompt, return_tensors="pt")

input_len = model_inputs["input_ids"].shape[-1]

with torch.inference_mode():
    generation = model.generate(**model_inputs, max_new_tokens=100, do_sample=False)
    generation = generation[0][input_len:]

decoded = processor.decode(generation, skip_special_tokens=True)
print(decoded)
