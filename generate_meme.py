import base64
import json
import os
import urllib.request
from datetime import date

from openai import OpenAI
from PIL import Image


def is_disabled_today(config):
    today = date.today().isoformat()
    for r in config.get("disabled_ranges", []):
        if r["start"] <= today <= r["end"]:
            return True
    return False


def write_status(send: bool):
    with open("send_today.json", "w") as f:
        json.dump({"send": send, "date": date.today().isoformat()}, f)


def generate_scene_prompt(client):
    with open("reference.png", "rb") as f:
        ref_image = base64.b64encode(f.read()).decode("utf-8")

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{ref_image}"},
                },
                {
                    "type": "text",
                    "text": (
                        "You generate prompts for DALL-E 3 to create a funny meme image.\n\n"
                        "Use the image above as a reference for the composition and layout only — "
                        "two characters, the dominant one on the left and the overwhelmed one on the right.\n\n"
                        "The meme always has the same setup: two characters, one physically "
                        "dominating/overpowering the other. The overpowered character needs to look very scared, overwhelmed, or tired. They should be inside of a ball or near a ball of any kind.\n"
                        "- The dominant character has a speech bubble pointing directly at them "
                        "that says EXACTLY: \"GET OUT OF THE BALLS EVAN\"\n"
                        "- The overwhelmed character has a speech bubble pointing directly at them "
                        "that says EXACTLY: \"MY PRODUCTIVITY\"\n"
                        "Both speech bubbles must be white with black text, clearly legible, large "
                        "enough to read easily, and each bubble's tail must point unambiguously to "
                        "its speaker. Place the characters on opposite sides of the image so the "
                        "bubbles do not overlap.\n\n"
                        "Each time, invent a completely new random combination of:\n"
                        "- Art style (e.g. renaissance oil painting, 1990s anime, pixel art, watercolor, "
                        "noir comic, children's book illustration, Soviet propaganda poster, etc.)\n"
                        "- Setting (e.g. underwater tea party, medieval jousting tournament, Wall Street "
                        "trading floor, outer space, ancient Roman colosseum, a Costco, etc.)\n"
                        "- Character types that fit the setting\n\n"
                        "Write only the DALL-E image prompt, nothing else. Be specific and vivid."
                    ),
                },
            ],
        }]
    )
    return response.choices[0].message.content


def main():
    with open("config.json") as f:
        config = json.load(f)

    if is_disabled_today(config):
        print(f"Sending disabled today ({date.today().isoformat()}), skipping.")
        write_status(False)
        return

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    print("Generating scene prompt...")
    prompt = generate_scene_prompt(client)
    print(f"Prompt: {prompt}\n")

    print("Generating image...")
    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        quality="standard",
        n=1,
    )

    image_url = response.data[0].url
    urllib.request.urlretrieve(image_url, "/tmp/meme_raw.png")

    img = Image.open("/tmp/meme_raw.png").convert("RGB")
    img.save("meme.jpg", "JPEG", quality=85)
    print("Saved meme.jpg")

    write_status(True)


if __name__ == "__main__":
    main()
