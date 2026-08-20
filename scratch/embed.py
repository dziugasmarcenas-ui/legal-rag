import os
import voyageai

client = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"]) 

result = client.embed(
    ["I want to take maternity leave."],
    model="voyage-3",
    input_type="document",
)

vector = result.embeddings[0]
print(f"Got a vector with {len(vector)} numbers")
print(vector[:5])