import os
import re
import psycopg2
from datetime import datetime
from dotenv import load_dotenv
from github import Github, Auth
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"), #Remember to place your OpenRouter or OpenAI API key in the .env file
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

def parse_frontmatter(content):
    match = re.match(r'^---\n(.*?)\n---\n(.*)', content, re.DOTALL)
    if not match:
        return {}, content
    fm_raw, body = match.group(1), match.group(2)
    fm = {}
    for line in fm_raw.splitlines():
        if ':' in line:
            key, _, val = line.partition(':')
            fm[key.strip()] = val.strip().strip('"')
    return fm, body.strip()

def get_embedding(text):
    response = client.embeddings.create(
        model="openai/text-embedding-3-small",
        input=text[:8000]
    )
    return response.data[0].embedding

def ingest():
    g = Github(auth=Auth.Token(os.getenv("GITHUB_TOKEN")))
    repo = g.get_repo("GitHubUserName/RepoName")  # Replace with your repository details
    files = repo.get_contents("src/content/blog")

    for file in files:
        if not file.name.endswith(".md") and not file.name.endswith(".mdx"):
            continue

        cur.execute("SELECT id FROM posts WHERE filename = %s", (file.name,))
        if cur.fetchone():
            print(f"Skipping (already ingested): {file.name}")
            continue

        content = file.decoded_content.decode("utf-8")
        fm, body = parse_frontmatter(content)

        title = fm.get("title", "")
        category = ", ".join(re.findall(r'\w+', fm.get("tags", "")))
        published_at = fm.get("publishedAt") or fm.get("date")
        try:
            published_at = datetime.fromisoformat(published_at)
        except:
            published_at = None

        text_to_embed = f"{title}\n\n{body}"
        embedding = get_embedding(text_to_embed)

        cur.execute("""
            INSERT INTO posts (filename, title, content, category, published_at, embedding)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (file.name, title, body, category, published_at, embedding))
        conn.commit()
        print(f"Ingested: {file.name}")

    cur.close()
    conn.close()
    print("Done.")

if __name__ == "__main__":
    ingest()