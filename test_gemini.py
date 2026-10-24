import os

from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
model = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
print("Model:", model)

response = client.models.generate_content(
    model=model,
    contents="Say hello in one short sentence.",
)

print("Text:", repr(response.text))
print("Finish reason:", response.candidates[0].finish_reason if response.candidates else "no candidates")
print("Prompt feedback:", response.prompt_feedback)