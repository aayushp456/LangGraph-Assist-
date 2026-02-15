import os
from openai import OpenAI


# Check for OpenRouter API key presence before initializing client
openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
if not openrouter_api_key:
    raise RuntimeError(
        "No OpenRouter API key found. Please set OPENROUTER_API_KEY."
    )

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=openrouter_api_key
)
default_model = "openai/gpt-oss-120b:free"
provider = "OpenRouter"

# Print/log provider and model information
print(f"[routing_agent] Using provider: {provider}, model: {default_model}")
def routing_agent(ticket_text: str):
    system_prompt = """
    You are a support routing agent.
    Categories:
    - FAQ
    - ESCALATE
    - SUMMARIZE
    Return JSON: {"category": "...", "confidence": 0-1}
    """
    resp = client.chat.completions.create(
        model=default_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": ticket_text}
        ],
        response_format={"type": "json_object"}
    )
    return resp.choices[0].message.content

if __name__ == "__main__":
    test_message = "I need help resetting my password"
    print(routing_agent(test_message))