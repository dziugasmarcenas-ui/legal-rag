import os

def load_corpus(folder):
    documents = []
    for filename in os.listdir (folder):
        if filename.endswith(".txt"):
            path = os.path.join(folder, filename)
            with open(path, "r") as f:
                text = f.read()
            documents.append({"source": filename, "text": text})
    return documents

def find_article(text):
    lined_text = text.splitlines()
    the_line = lined_text[1]
    article_number = the_line.split()[-1]
    return article_number
    


def dot_product (a, b):
    total = 0
    for i in range(len(a)):
        total = total + a[i] * b[i]
    return total

print(dot_product([1, 2], [3, 4]))