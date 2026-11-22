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

# 1. Claude (11 YouTube Skills) se Script + 5 Alag Visual Keywords + SEO banwana
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
prompt = f"""
You are a viral YouTube Shorts creator using the 11 YouTube Agent Skills (strong 3-second hook, fast visual pacing, high-CTR title, SEO).
Topic: {topic}
Language for spoken script: {lang}

Return ONLY valid JSON with:
- "script": 45-second engaging spoken narration (around 90-105 words, plain sentences, no emojis)
- "keywords": List of 5 distinct 2-word English keywords for stock background clips matching each part of the story
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

# 2. Free AI Voiceover + Word-by-Word Timing (.vtt) banana
voice = "hi-IN-MadhurNeural" if lang.lower() == "hindi" else "en-US-AndrewNeural"

async def make_voice_and_subs():
    communicate = edge_tts.Communicate(data["script"], voice)
    submaker = edge_tts.SubMaker()
    with open("voice.mp3", "wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                submaker.feed(chunk)
    with open("subs.vtt", "w", encoding="utf-8") as sub_file:
        sub_file.write(submaker.get_srt())

asyncio.run(make_voice_and_subs())

# 3. Pexels se 5 Alag Vertical HD Clips Download aur Trim (4 sec each) karna
headers = {"Authorization": os.environ["PEXELS_API_KEY"]}
clip_files = []

for i, kw in enumerate(data["keywords"][:5]):
    res = requests.get(
        f"https://pexels.com{kw}&orientation=portrait&per_page=1",
        headers=headers
    ).json()
    if res.get("videos"):
        v_url = res["videos"]["video_files"]["link"]
        raw_name = f"raw_{i}.mp4"
        clip_name = f"clip_{i}.mp4"
        with open(raw_name, "wb") as f:
            f.write(requests.get(v_url).content)
        # Har clip ko 1080x1920 size aur 4 second ka banana
        subprocess.run([
            "ffmpeg", "-y", "-i", raw_name, "-t", "4",
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30",
            "-an", "-c:v", "libx264", "-preset", "fast", clip_name
        ], check=True)
        clip_files.append(clip_name)

# Sabhi 5 clips ko ek line mein jodna (loop ke saath)
with open("concat.txt", "w") as f:
    for _ in range(3):
        for c in clip_files:
            f.write(f"file '{c}'\n")

subprocess.run([
    "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "concat.txt",
    "-c", "copy", "merged_bg.mp4"
], check=True)

# 4. Bold Subtitles + Voiceover ko Final Short mein Jodna
subtitle_style = (
    "FontName=DejaVu Sans,FontSize=18,PrimaryColour=&H0000FFFF,"
    "OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=65"
)

subprocess.run([
    "ffmpeg", "-y", "-i", "merged_bg.mp4", "-i", "voice.mp3",
    "-vf", f"subtitles=subs.vtt:force_style='{subtitle_style}'",
    "-map", "0:v:0", "-map", "1:a:0",
    "-c:v", "libx264", "-preset", "fast", "-c:a", "aac", "-shortest", "final_short.mp4"
], check=True)

# 5. YouTube par Upload karna (Private Draft)
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
print("High-Retention Short Ready & Uploaded! Video ID:", response["id"])


