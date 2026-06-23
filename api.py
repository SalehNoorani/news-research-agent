import os
import psycopg2
from dotenv import load_dotenv
from openai import OpenAI
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-website.com"],
    allow_methods=["POST"],
    allow_headers=["*"],
)

class Query(BaseModel):
    question: str

def get_embedding(text):
    response = client.embeddings.create(
        model="openai/text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding

def search_posts(query, limit=5):
    embedding = get_embedding(query)
    cur.execute("""
        SELECT title, content, published_at
        FROM posts
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """, (embedding, limit))
    return cur.fetchall()

def build_answer(question, posts):
    context = ""
    for title, content, date in posts:
        context += f"### {title} ({date:%Y-%m-%d})\n{content[:600]}\n\n"

    prompt = f"""You are a crypto news assistant.
Answer the question below using ONLY the articles provided.
Cite article titles when making claims.
If the articles don't contain relevant info, say so.

Question: {question}

Articles:
{context}"""

    response = client.chat.completions.create(
        model="deepseek/deepseek-v4-flash",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1000
    )
    return response.choices[0].message.content

@app.post("/ask")
def ask(query: Query):
    posts = search_posts(query.question)
    answer = build_answer(query.question, posts)
    return {"answer": answer}