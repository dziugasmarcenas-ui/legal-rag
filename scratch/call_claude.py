import os
from anthropic import Anthropic

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

response = client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=200,
    messages=[
        {"role": "user", "content": "how long is maternal holiday?"}
    ],
)

print(response.content[0].text)






