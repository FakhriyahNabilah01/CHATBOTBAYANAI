import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

from openai import OpenAI
client = OpenAI()

def embed_query(text: str):
    resp = client.embeddings.create(
        model="text-embedding-3-large",
        input=text
    )
    return resp.data[0].embedding