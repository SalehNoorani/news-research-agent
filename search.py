import os
import psycopg2
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)

conn = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT"),
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD")
)
cur = conn.cursor()

def search(query, limit=5):
    response = client.embeddings.create(
        model="openai/text-embedding-3-small",
        input=query
    )
    embedding = response.data[0].embedding

    cur.execute("""
        SELECT title, category, published_at,
               1 - (embedding <=> %s::vector) AS similarity
        FROM posts
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """, (embedding, embedding, limit))

    results = cur.fetchall()
    for title, category, date, score in results:
        print(f"[{score:.2f}] {title} ({date:%Y-%m-%d})")

if __name__ == "__main__":
    search("institutional investors buying bitcoin") # Or any other query you want to test