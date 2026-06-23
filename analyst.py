import os
import psycopg2
from datetime import datetime, timedelta
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

def get_recent_posts(days=7):
    since = datetime.now() - timedelta(days=days)
    cur.execute("""
        SELECT title, category, content, published_at
        FROM posts
        WHERE published_at >= %s
        ORDER BY published_at DESC
    """, (since,))
    return cur.fetchall()

def build_context(posts):
    context = ""
    for title, category, content, date in posts:
        context += f"### {title} ({date:%Y-%m-%d})\nTags: {category}\n{content[:500]}\n\n"
    return context

def generate_analysis(posts):
    context = build_context(posts)
    prompt = f"""You are a crypto market analyst. Based ONLY on the news articles below, write a weekly analysis report.

Rules:
- Only make claims supported by the articles below
- Cite the article title when making a claim
- No price predictions
- Identify key narratives, trends, and notable events
- Format as a clean markdown article with sections

Articles:
{context}"""

    response = client.chat.completions.create(
        model="deepseek/deepseek-v4-flash",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000
    )
    return response.choices[0].message.content

if __name__ == "__main__":
    posts = get_recent_posts(days=7)
    print(f"Analyzing {len(posts)} posts from the last 7 days...")
    analysis = generate_analysis(posts)

    filename = f"analysis-{datetime.now().strftime('%Y-%m-%d')}.md"
    with open(filename, "w") as f:
        f.write(analysis)
    print(f"Saved to {filename}")