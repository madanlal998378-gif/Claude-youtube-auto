import os
import json
import requests
import anthropic
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# 1. Inputs lena
topic = os.environ["VIDEO_TOPIC"]
video_url = os.environ["VIDEO_URL"]

# 2. Video file download karna
print("Video download ho raha hai...")
r = requests.get(video_url, stream=True)
with open("video.mp4", "wb") as f:
    for chunk in r.iter_content(chunk_size=8192):
        f.write(chunk)

# 3. Claude se 11 YouTube Skills ke hisab se SEO metadata banwana
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
prompt = f"""
You are a YouTube growth expert using the 11 YouTube Agent Skills (21 hook formulas, title-thumbnail alignment, retention engineering, and YouTube SEO).
Topic: {topic}

Return ONLY valid JSON with:
- "title": High-CTR YouTube title (under 65 chars)
- "description": Engaging description with a strong 2-line hook, summary, and hashtags
- "tags": List of 12 high-ranking tags
"""

msg = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=800,
    messages=[{"role": "user", "content": prompt}]
)

seo = json.loads(msg.content[0].text.strip().removeprefix("```json").removesuffix("```"))

# 4. YouTube par Upload karna (Private mode mein taaki aap Studio app se check kar sakein)
creds = Credentials(
    token=None,
    refresh_token=os.environ["YT_REFRESH_TOKEN"],
    token_uri="https://googleapis.com",
    client_id=os.environ["YT_CLIENT_ID"],
    client_secret=os.environ["YT_CLIENT_SECRET"],
)
youtube = build("youtube", "v3", credentials=creds)

body = {
    "snippet": {
        "title": seo["title"],
        "description": seo["description"],
        "tags": seo["tags"],
        "categoryId": "22"
    },
    "status": {
        "privacyStatus": "private"
    }
}

media = MediaFileUpload("video.mp4", chunksize=-1, resumable=True)
request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
response = request.execute()
print("Upload Successful! Video ID:", response["id"])
