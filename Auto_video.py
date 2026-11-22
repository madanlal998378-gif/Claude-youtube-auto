import os
import json
import asyncio
import subprocess
import requests
import anthropic
import edge_tts
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

topic = os.environ["VIDEO_TOPIC"]
lang = os.environ.get("VIDEO_LANG", "Hindi")

# 1. Claude se Script, Visual Keyword aur SEO banwana
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
prompt = f"""
You are a viral YouTube Shorts creator using the 11 YouTube Agent Skills (strong 3-second hook, retention pacing, high-CTR title, SEO).
Topic: {topic}
Language for spoken script: {lang}

Return ONLY valid JSON with:
- "script": 45-second engaging spoken narration (around 90-110 words, plain text only, no emojis or stage directions)
- "search_keyword": 2-word English keyword for stock background video (e.g. "technology dark", "nature mountains", "money business")
- "title": Catchy YouTube Shorts title under 60 chars with #Shorts
- "description": 2-line hook description with relevant hashtags
- "tags": List of 10 SEO tags
"""

msg = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1000,
    messages=[{"role": "user", "content": prompt}]
)
data = json.loads(msg.content.text.strip().removeprefix("```json").removesuffix("```"))

# 2. Free AI Voiceover + Subtitles (.vtt) banana
voice = "hi-IN-MadhurNeural" if lang.lower() == "hindi" else "en-US-AndrewNeural"

async def make_voice():
    communicate = edge_tts.Communicate(data["script"], voice)
    await communicate.save("voice.mp3")

asyncio.run(make_voice())

# 3. Pexels se Free Vertical HD Video Download karna
headers = {"Authorization": os.environ["PEXELS_API_KEY"]}
res = requests.get(
    f"https://pexels.com{data['search_keyword']}&orientation=portrait&per_page=1",
    headers=headers
).json()

video_url = res["videos"][0]["video_files"][0]["link"]
with open("bg.mp4", "wb") as f:
    f.write(requests.get(video_url).content)

# 4. FFmpeg se Background Video + Voiceover ko jodkar Final Short banana
subprocess.run([
    "ffmpeg", "-y", "-stream_loop", "-1", "-i", "bg.mp4", "-i", "voice.mp3",
    "-map", "0:v:0", "-map", "1:a:0",
    "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
    "-c:v", "libx264", "-preset", "fast", "-c:a", "aac", "-shortest", "final_short.mp4"
], check=True)

# 5. YouTube par Upload karna (Private draft mode mein)
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
        "title": data["title"],
        "description": data["description"],
        "tags": data["tags"],
        "categoryId": "22"
    },
    "status": {"privacyStatus": "private"}
}

media = MediaFileUpload("final_short.mp4", chunksize=-1, resumable=True)
response = youtube.videos().insert(part="snippet,status", body=body, media_body=media).execute()
print("Video Ban Gaya aur Upload Ho Gaya! Video ID:", response["id"])

