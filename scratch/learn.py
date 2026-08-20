def magnitude(a):
    total = 0
    for m in a:
        total = total + (m ** 2)
    return (total ** 0.5) 

def dot_product (a, b):
    total = 0
    for i in range(len(a)):
        total = total + a[i] * b[i]
    return total

def cosine_similarity(a, b):
   return (dot_product(a, b) / (magnitude(a) * magnitude(b)))

print(cosine_similarity([3, 4], [3, 4]))