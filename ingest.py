import os

import voyageai

from anthropic import Anthropic





def find_article(text):
    lines = text.splitlines()
    header = lines[1]
    words = header.split()
    return words[-1]

def load_corpus(folder):
    documents = []
    for filename in os.listdir (folder):
        if filename.endswith(".txt"):
            path = os.path.join(folder, filename)
            with open(path, "r") as f:
                text = f.read()
            documents.append({"source": filename, "text": text})
    return documents
    


def dot_product(a, b):
    total = 0
    for i in range(len(a)):
        total = total + a[i] * b[i] 
    return total

def magnitude(a):
    total = 0
    for n in a:
        total = total + n * n 
    return total ** 0.5

def cosine_similarity(a, b):
    result = (dot_product(a, b ) / (magnitude(a) * magnitude(b)))
    return result


documents = load_corpus("corpus")

all_chunks = []
for doc in documents:
    all_chunks.append({"source": doc["source"], "text": doc["text"], "article": find_article(doc["text"])})

print(f"Total chunks: {len(all_chunks)}")
print(all_chunks[0])



client = voyageai.Client(api_key=os.environ["VOYAGE_API_KEY"])

texts = []
for chunk in all_chunks:
    texts.append(chunk["text"])

result = client.embed(texts, model="voyage-3", input_type="document")

for i in range(len(all_chunks)):
    all_chunks[i]["vector"] = result.embeddings[i]

print("Embedded", len(all_chunks), "chunks")
print("First vector length:", len(all_chunks[0]["vector"]))

for chunk in all_chunks:
    print(chunk["source"], chunk["article"])


question = "How many days of annual leave am I entitled to?"
query_result = client.embed([question], model="voyage-3", input_type="query")
question_vector = query_result.embeddings[0]

best_score = -1
best_chunk = None
for chunk in all_chunks:
    score = cosine_similarity(question_vector, chunk["vector"])
    if score > best_score:
        best_score = score
        best_chunk = chunk

print(best_chunk["source"], best_chunk["article"])
print(best_score)
if best_score < 0.5:
    print('Not confident enough — please confirm with HR.')

else:
    claude_client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    prompt = f"article text : {best_chunk['text']}\n\n question : {question}\n\n Cite this article number at the end of your answer in the format : [article {best_chunk['article']}] " 

    response = claude_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        messages=[
            {"role": "user", "content": prompt}
        ],
    )

    print(response.content[0].text)

